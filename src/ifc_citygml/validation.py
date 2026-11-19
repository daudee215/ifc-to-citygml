"""Offline schemas/references and profile-specific geometry checks.

Blocks retain the original bounded convex-shell tests. Surface representations
require the independent validator, with closed-Solid diagnostics kept separate.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
from urllib.parse import urlsplit

from lxml import etree as ET
import numpy as np
from shapely.geometry import Polygon

from .common import SCHEMA_DIR, digest
from .citygml_writer import NS, tag


class CachedResolver(ET.Resolver):
    def __init__(self, files: dict[str, Path]):
        super().__init__()
        self.files = files

    def resolve(self, url, public_id, context):
        if url.startswith(("http://", "https://")):
            parts = urlsplit(url)
            canonical = "https://" + parts.netloc.lower() + parts.path
            if canonical not in self.files:
                raise OSError(f"Uncached schema dependency: {url}")
            return self.resolve_filename(str(self.files[canonical]), context)
        return None


def load_schema(schema_dir: Path | None = None) -> ET.XMLSchema:
    directory = schema_dir or SCHEMA_DIR
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    files = {}
    for entry in manifest["files"]:
        path = directory / entry["path"]
        if not path.resolve().is_relative_to(directory.resolve()) or digest(path) != entry["sha256"]:
            raise ValueError(f"Schema integrity check failed: {entry['path']}")
        files[entry["url"]] = path
    parser = ET.XMLParser(no_network=True, resolve_entities=False)
    parser.resolvers.add(CachedResolver(files))
    return ET.XMLSchema(ET.parse(str(files[manifest["entry_url"]]), parser))


def _check_solid(solid, tolerance: float) -> dict:
    errors, rings = [], []
    if solid.get("srsDimension") != "3" or not solid.get("srsName"):
        errors.append("Solid must declare a coordinate reference and dimension 3")
    if solid.findall(".//gml:interior", NS):
        errors.append("Interior rings/shells are outside the pilot validation profile")
    polygons = solid.findall("./gml:exterior/gml:Shell/gml:surfaceMember/gml:Polygon", NS)
    if len(polygons) != 6:
        errors.append("Pilot requires exactly six explicit polygon faces")
    for index, polygon in enumerate(polygons):
        positions = polygon.findall("./gml:exterior/gml:LinearRing/gml:posList", NS)
        try:
            if len(positions) != 1 or positions[0].get("srsDimension") != "3":
                raise ValueError("Requires one 3D posList")
            values = [float(v) for v in (positions[0].text or "").split()]
            points = np.array(values).reshape(-1, 3)
            if points.shape != (5, 3) or not np.isfinite(points).all():
                raise ValueError("Requires four finite vertices and a closing point")
            if not np.allclose(points[0], points[-1], atol=tolerance, rtol=0):
                raise ValueError("Ring is not closed")
            ring = points[:-1]
            normal = np.cross(ring[1] - ring[0], ring[2] - ring[0])
            length = np.linalg.norm(normal)
            if length <= tolerance ** 2:
                raise ValueError("Degenerate face")
            normal /= length
            if np.max(np.abs((ring - ring[0]) @ normal)) > tolerance:
                raise ValueError("Non-planar face")
            projection = np.delete(ring, np.argmax(np.abs(normal)), axis=1)
            shape = Polygon(projection)
            if not shape.is_valid or shape.area <= tolerance ** 2:
                raise ValueError("Self-intersecting or degenerate face")
            rings.append(ring)
        except (ValueError, IndexError) as exc:
            errors.append(f"Face {index}: {exc}")
    if errors or len(rings) != 6:
        return {"passed": False, "errors": errors}
    points = np.vstack(rings)
    origin = points.mean(axis=0)
    directed, undirected = Counter(), Counter()
    vertex_keys = set()
    volume = 0.0
    for index, ring in enumerate(rings):
        normal = np.cross(ring[1] - ring[0], ring[2] - ring[0])
        normal /= np.linalg.norm(normal)
        if np.max((points - ring[0]) @ normal) > tolerance:
            errors.append(f"Face {index}: inward orientation or non-convex shell")
        keys = [tuple(int(round(v / tolerance)) for v in p) for p in ring]
        vertex_keys.update(keys)
        for a, b in zip(keys, keys[1:] + keys[:1]):
            directed[(a, b)] += 1
            undirected[tuple(sorted((a, b)))] += 1
        local = ring - origin
        for i in range(1, len(local) - 1):
            volume += float(np.dot(local[0], np.cross(local[i], local[i + 1])) / 6)
    if len(vertex_keys) != 8 or len(undirected) != 12:
        errors.append("Expected eight unique vertices and twelve unique shell edges")
    for edge, count in undirected.items():
        a, b = edge
        if count != 2 or directed[(a, b)] != 1 or directed[(b, a)] != 1:
            errors.append("Shell edge does not have two opposite oriented incidences")
            break
    if volume <= tolerance ** 3:
        errors.append("Solid must have positive nonzero signed volume")
    return {"passed": not errors, "errors": errors, "face_count": 6,
            "unique_vertex_count": len(vertex_keys), "unique_edge_count": len(undirected),
            "volume_m3": volume, "bounds_m": [points.min(axis=0).tolist(), points.max(axis=0).tolist()]}


def validate_document(data: bytes, tolerance: float = 1e-6, schema_dir: Path | None = None) -> dict:
    if not 1e-9 <= tolerance <= 0.01:
        raise ValueError("Geometry tolerance must be between 1e-9 and 0.01 m")
    report = {"status": "failed", "schema_valid": False, "reference_errors": [],
              "geometry": [], "geometry_validator": "pilot_convex_six_face_shell_checks",
              "independent_general_solid_validation": "not_run",
              "scope": "CityGML 3.0 pilot blocks; no claim of general CityGML or ISO 19107 conformance"}
    parser = ET.XMLParser(no_network=True, resolve_entities=False)
    try:
        root = ET.fromstring(data, parser)
        if root.getroottree().docinfo.doctype:
            raise ValueError("DTD-bearing documents are not accepted")
        schema = load_schema(schema_dir)
        report["schema_manifest_sha256"] = digest((schema_dir or SCHEMA_DIR) / "manifest.json")
        report["schema_valid"] = schema.validate(root)
        report["schema_errors"] = [str(e) for e in schema.error_log]
    except (ET.Error, ValueError, OSError) as exc:
        report["schema_errors"] = [str(exc)]
        return report
    ids = root.xpath("//@gml:id", namespaces=NS)
    if len(ids) != len(set(ids)):
        report["reference_errors"].append("Duplicate gml:id")
    for href in root.xpath("//@xlink:href", namespaces={"xlink": "http://www.w3.org/1999/xlink"}):
        if not href.startswith("#") or href[1:] not in ids:
            report["reference_errors"].append(f"Unresolved or unsupported external reference: {href}")
    buildings = root.findall("./core:cityObjectMember/bldg:Building", NS)
    solids = root.findall(".//gml:Solid", NS)
    detailed = bool(buildings) and all(b.find("./core:lod2MultiSurface/gml:MultiSurface", NS) is not None for b in buildings)
    con = "http://www.opengis.net/citygml/construction/3.0"
    constructive = bool(root.findall(".//bldg:BuildingConstructiveElement", NS) or root.findall(f".//{{{con}}}Door") or root.findall(f".//{{{con}}}Window"))
    if root.tag != tag("core", "CityModel") or not buildings:
        report["reference_errors"].append("Requires CityModel with at least one Building")
    if not detailed and not constructive and len(solids) != len(buildings):
        report["reference_errors"].append("Requires exactly one solid per Building")
    if detailed or constructive:
        if solids:
            report["reference_errors"].append("Detailed profile cannot mix block solids with envelope surfaces")
        from .external_validation import validate_external
        if report["schema_valid"] and not report["reference_errors"]:
            try:
                external = validate_external(data, tolerance)
            except (ValueError, OSError, TimeoutError) as exc:
                external = {"status": "failed", "reason": str(exc)}
            report["external_validation"] = external
            report["independent_surface_validation"] = external["status"]
            report["independent_general_solid_validation"] = external.get("solid_diagnostic", {}).get("status", "not_run")
            report["geometry_validator"] = "val3dity_2.7.0_via_lossless_geometry_adapter"
            report["geometry"] = [{"passed": external["status"] == "passed", "method": report["geometry_validator"]}]
            report["scope"] = "Schema and declared MultiSurface independently validated; stronger Solid diagnostic reported separately. Semantic/exterior interpretation remains heuristic."
            report["quality_warnings"] = [] if report["independent_general_solid_validation"] == "passed" else [
                "Exported MultiSurface is not established as a valid closed Solid; inspect solid diagnostic before volume-dependent use"]
            if constructive:
                report["scope"] = "Source-preserving constructive/filling MultiSurfaces. Interior/open source geometry is retained; no exterior-envelope inference."
                report["quality_warnings"].append("Constructive profile retains source material surfaces and interiors; use the separate envelope profile for an exterior interpretation")
            report["status"] = "passed" if external["status"] == "passed" else "failed"
        return report
    for building in buildings:
        owned = building.findall("./core:lod1Solid/gml:Solid", NS)
        if len(owned) != 1:
            report["geometry"].append({"passed": False, "errors": ["Requires one explicit lod1Solid per Building"]})
        else:
            report["geometry"].append({"building_id": building.get(tag("gml", "id")),
                                       **_check_solid(owned[0], tolerance)})
    report["status"] = "passed" if (report["schema_valid"] and not report["reference_errors"]
        and report["geometry"] and all(g["passed"] for g in report["geometry"])) else "failed"
    if report["status"] == "passed":
        from .external_validation import validate_external
        external = validate_external(data, tolerance)
        report["external_validation"] = external
        report["independent_general_solid_validation"] = external["status"]
        if external["status"] == "failed":
            report["status"] = "failed"
    return report
