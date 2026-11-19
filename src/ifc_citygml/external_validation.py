"""Validate exact exported GML rings via a geometry-only CityJSON adapter."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from lxml import etree as ET

from .citygml_writer import NS, tag
from .validator_tools import probe_validator, validator_environment

XLINK = "{http://www.w3.org/1999/xlink}href"


def geometry_adapter(data: bytes, force_solids: bool = False) -> tuple[dict, dict]:
    root = ET.fromstring(data, ET.XMLParser(no_network=True, resolve_entities=False))
    lookup = {node.get(tag("gml", "id")): node for node in root.iter() if node.get(tag("gml", "id"))}
    vertices, vertex_index, objects, original_rings, rebuilt_rings = [], {}, {}, [], []

    def face(member):
        href = member.get(XLINK)
        polygon = lookup[href[1:]] if href else member.find("gml:Polygon", NS)
        if polygon is None:
            raise ValueError("Unsupported surface geometry in validator adapter")
        pos = polygon.find("./gml:exterior/gml:LinearRing/gml:posList", NS)
        values = [float(v) for v in (pos.text or "").split()]
        if len(values) % 3 or len(values) < 12:
            raise ValueError("Incomplete 3D ring")
        ring = [tuple(values[i:i + 3]) for i in range(0, len(values), 3)]
        if ring[0] != ring[-1]:
            raise ValueError("GML ring must close exactly for lossless validation adapter")
        ring = ring[:-1]
        indices = []
        for p in ring:
            if p not in vertex_index:
                vertex_index[p] = len(vertices)
                vertices.append(list(p))
            indices.append(vertex_index[p])
        original_rings.append([list(p) for p in ring])
        rebuilt_rings.append([vertices[i] for i in indices])
        return [indices]

    con = "http://www.opengis.net/citygml/construction/3.0"
    units = root.findall(".//bldg:BuildingConstructiveElement", NS) + root.findall(f".//{{{con}}}Door") + root.findall(f".//{{{con}}}Window")
    for unit in units:
        multi = unit.find("./core:lod2MultiSurface/gml:MultiSurface", NS)
        if multi is None:
            raise ValueError("Constructive/filling feature has no supported explicit surface geometry")
        surfaces = [face(member) for member in multi.findall("./gml:surfaceMember", NS)]
        primitive = "Solid" if force_solids else "MultiSurface"
        objects[unit.get(tag("gml", "id"))] = {"type": "GenericCityObject", "geometry": [
            {"type": primitive, "lod": "2", "boundaries": [surfaces] if force_solids else surfaces}]}
    for building in ([] if units else root.findall("./core:cityObjectMember/bldg:Building", NS)):
        identifier = building.get(tag("gml", "id"))
        solid = building.find("./core:lod1Solid/gml:Solid", NS)
        if solid is not None:
            shells = [solid.findall("./gml:exterior/gml:Shell/gml:surfaceMember", NS)]
            lod = "1"
        else:
            multi = building.find("./core:lod2MultiSurface/gml:MultiSurface", NS)
            if multi is None:
                raise ValueError("No supported building geometry")
            shells = [node.findall("./gml:surfaceMember", NS) for node in multi.findall("./gml:surfaceMember/gml:CompositeSurface", NS)]
            if not shells:
                raise ValueError("Detailed output must declare its closed components as CompositeSurface members")
            lod = "2"
        primitive = "Solid" if solid is not None or force_solids else "MultiSurface"
        geometries = []
        for shell in shells:
            faces = [face(member) for member in shell]
            geometries.append({"type": primitive, "lod": lod, "boundaries": [faces] if primitive == "Solid" else faces})
        objects[identifier] = {"type": "Building", "geometry": geometries}
    if not objects or not original_rings:
        raise ValueError("No geometry adapted")
    original_bytes = json.dumps(original_rings, separators=(",", ":"), allow_nan=False).encode()
    rebuilt_bytes = json.dumps(rebuilt_rings, separators=(",", ":"), allow_nan=False).encode()
    if original_bytes != rebuilt_bytes:
        raise ValueError("Geometry adapter changed exported rings")
    return {"type": "CityJSON", "version": "1.1", "CityObjects": objects, "vertices": vertices}, {
        "lossless_exported_ring_check": True, "ring_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "polygon_count": len(original_rings), "unique_vertex_count": len(vertices),
        "tested_interpretation": "forced_solid_diagnostic" if force_solids else "declared_target_geometry",
        "semantic_validation": "not performed; GenericCityObject preserves neutral per-feature geometry identities for constructive/filling input",
        "primitive_types": sorted({g["type"] for o in objects.values() for g in o["geometry"]})}


def validate_external(data: bytes, tolerance: float = 1e-6, force_solids: bool = False) -> dict:
    tool = probe_validator()
    if tool["status"] != "passed":
        return tool
    executable = Path(tool["executable"])
    adapted, correspondence = geometry_adapter(data, force_solids)
    environment, runtime_info = validator_environment()
    with tempfile.TemporaryDirectory(prefix="ifc_citygml_validation_") as temporary:
        folder = Path(temporary)
        source, report = folder / "geometry.city.json", folder / "report.json"
        source.write_text(json.dumps(adapted, allow_nan=False), encoding="utf-8")
        args = [str(executable), str(source), "--report", str(report), "--snap_tol", str(tolerance)]
        result = subprocess.run(args, capture_output=True, text=True, env=environment, timeout=120)
        # Different releases may append .json to the requested report name.
        candidates = [report, folder / "report.json.json"]
        actual = next((p for p in candidates if p.exists()), None)
        if actual is None:
            return {"status": "unavailable", "exit_code": result.returncode,
                    "reason": "Validator produced no report", "stderr": result.stderr[-2000:],
                    "stdout": result.stdout[-2000:], "adapter": correspondence}
        report_data = json.loads(actual.read_text(encoding="utf-8"))
    valid = report_data.get("validity", report_data.get("valid"))
    outcome = {"status": "passed" if valid is True else "failed", "tool": "val3dity", "version": tool["version"],
            "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(), "exit_code": result.returncode,
            "location_origin": tool["origin"], **runtime_info,
            "adapter": correspondence, "report": report_data}
    if not force_solids and "MultiSurface" in correspondence["primitive_types"]:
        outcome["solid_diagnostic"] = validate_external(data, tolerance, force_solids=True)
    return outcome
