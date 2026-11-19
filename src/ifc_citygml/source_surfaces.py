"""Retain selected IFC tessellations as CityGML constructive/filling elements.

This profile preserves source surfaces and void geometry, including open meshes.
It performs no solid union, cavity filling, quantisation, hole repair or winding
repair. It makes no inference that a source face is a building exterior.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.guid
import ifcopenshell.util.element
import ifcopenshell.util.unit
from lxml import etree as ET
import numpy as np

from .common import digest, transform_points
from .citygml_writer import NS, child, tag, SCHEMA_URL
from .envelope import _host_guid

CON = "http://www.opengis.net/citygml/construction/3.0"
CLASS_CODES = "urn:ifc-citygml:codelist:ifc-entity"


def triangle_digest(vertices, triangles):
    payload = np.ascontiguousarray(vertices[triangles], dtype="<f8").tobytes()
    return hashlib.sha256(payload).hexdigest()


def extract_source_surfaces(path: Path, profile: dict) -> dict:
    model = ifcopenshell.open(str(path))
    if model.schema not in profile["supported_ifc_schemas"]:
        raise ValueError(f"Unsupported IFC schema: {model.schema}")
    if profile["coordinate_mode"] not in ("ifc_map_conversion", "engineering_with_map_provenance") and model.schema != "IFC2X3" and model.by_type("IfcMapConversion"):
        raise ValueError("IfcMapConversion requires the explicit georeferencing profile")
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("convert-back-units", False)
    buildings, failures, seen = [], [], set()
    for building in sorted(model.by_type("IfcBuilding"), key=lambda b: b.GlobalId or ""):
        elements, omitted = [], []
        for element in sorted(ifcopenshell.util.element.get_decomposition(building), key=lambda e: e.id()):
            if not element.is_a("IfcElement") or element.is_a("IfcFeatureElement"):
                continue
            record = {"ifc_global_id": element.GlobalId, "ifc_class": element.is_a(), "name": element.Name,
                      "step_id": element.id(), "host_global_id": _host_guid(element)}
            filling = next((c for c in profile["filling_ifc_classes"] if element.is_a(c)), None)
            constructive = any(element.is_a(c) for c in profile["constructive_ifc_classes"])
            if not constructive and not filling:
                omitted.append({**record, "reason": "Outside declared constructive/filling profile"})
                continue
            if not element.Representation:
                omitted.append({**record, "reason": "No source representation"})
                continue
            if not element.GlobalId or element.GlobalId in seen:
                failures.append({**record, "reason": "Missing/duplicate selected source GlobalId"})
                continue
            seen.add(element.GlobalId)
            try:
                shape = ifcopenshell.geom.create_shape(settings, element)
                vertices = np.asarray(shape.geometry.verts, dtype=float).reshape(-1, 3)
                triangles = np.asarray(shape.geometry.faces, dtype=np.int64).reshape(-1, 3)
                if not len(triangles) or not np.isfinite(vertices).all():
                    raise ValueError("No finite triangulated source geometry")
                normals = np.cross(vertices[triangles[:, 1]] - vertices[triangles[:, 0]],
                                   vertices[triangles[:, 2]] - vertices[triangles[:, 0]])
                if np.any(np.linalg.norm(normals, axis=1) == 0):
                    raise ValueError("Source contains zero-area triangles; source geometry is not altered automatically")
                psets = ifcopenshell.util.element.get_psets(element)
                # Keep source-native values; no guessed measure-unit conversion.
                psets = json.loads(json.dumps(psets, default=str, allow_nan=False))
                load_bearing = next((p.get("LoadBearing") for p in psets.values()
                                     if isinstance(p, dict) and isinstance(p.get("LoadBearing"), bool)), None)
                voids = [{"opening_global_id": rel.RelatedOpeningElement.GlobalId,
                          "opening_step_id": rel.RelatedOpeningElement.id(),
                          "filling_global_ids": [f.RelatedBuildingElement.GlobalId for f in rel.RelatedOpeningElement.HasFillings]}
                         for rel in getattr(element, "HasOpenings", ())]
                target_class = "Door" if filling == "IfcDoor" else "Window" if filling else "BuildingConstructiveElement"
                elements.append({**record, "target_class": target_class, "load_bearing": load_bearing,
                    "vertices": vertices.tolist(), "triangles": triangles.tolist(),
                    "source_triangle_coordinate_sha256": triangle_digest(vertices, triangles),
                    "source_surface_area_m2": float(np.linalg.norm(normals, axis=1).sum() / 2),
                    "opening_relations": voids, "source_property_sets": psets,
                    "property_unit_policy": "Source-native values; retain original IFC and explicit property units for interpretation",
                    "container_global_id": getattr(ifcopenshell.util.element.get_container(element), "GlobalId", None)})
            except Exception as exc:
                failures.append({**record, "building": building.GlobalId, "reason": str(exc)})
        if not elements:
            failures.append({"building": building.GlobalId, "reason": "No eligible constructive/filling geometry"})
        buildings.append({"source_building_global_id": building.GlobalId, "name": building.Name,
                          "elements": elements, "omitted": omitted})
    return {"status": "failed" if failures or not buildings else "passed", "input": str(path.resolve()),
            "input_sha256": digest(path), "ifc_schema": model.schema,
            "length_unit_to_metre": ifcopenshell.util.unit.calculate_unit_scale(model),
            "representation": "source_constructive_surfaces", "buildings": buildings, "failures": failures,
            "geometry_policy": "Unmodified source SI tessellations; open surfaces preserved; no exterior/closed-solid inference"}


def create_source_document(extraction, profile):
    root = ET.Element(tag("core", "CityModel"), nsmap={**NS, "con": CON})
    root.set(tag("gml", "id"), "citymodel_" + extraction["input_sha256"][:16])
    root.set(tag("xsi", "schemaLocation"), f"{NS['bldg']} {SCHEMA_URL}")
    child(root, "gml", "description", "Source-preserving constructive/filling surfaces; includes interior and open source meshes. No exterior envelope is inferred.")
    links, expected_rings = [], {}

    def write_element(parent, element):
        kind = element["target_class"]
        namespace = NS["bldg"] if kind == "BuildingConstructiveElement" else CON
        node = ET.SubElement(parent, f"{{{namespace}}}{kind}")
        identifier = "e_" + ifcopenshell.guid.expand(element["ifc_global_id"])
        node.set(tag("gml", "id"), identifier)
        child(node, "gml", "name", element["name"] or element["ifc_class"])
        multi = child(child(node, "core", "lod2MultiSurface"), "gml", "MultiSurface",
                      srsName=profile["srs_name"], srsDimension="3")
        vertices = transform_points(np.array(element["vertices"]), profile)
        for index, face in enumerate(element["triangles"]):
            polygon = child(child(multi, "gml", "surfaceMember"), "gml", "Polygon")
            polygon_id = f"{identifier}_t{index}"
            polygon.set(tag("gml", "id"), polygon_id)
            ring = child(child(polygon, "gml", "exterior"), "gml", "LinearRing")
            points = vertices[[*face, face[0]]]
            # 17 significant digits round-trip every finite IEEE float64 value.
            child(ring, "gml", "posList", " ".join(format(float(v), ".17g") for v in points.flat), srsDimension="3")
            expected_rings[polygon_id] = points[:-1].tolist()
        return node, identifier

    for building in extraction["buildings"]:
        building_id = "b_" + ifcopenshell.guid.expand(building["source_building_global_id"])
        feature = child(child(root, "core", "cityObjectMember"), "bldg", "Building")
        feature.set(tag("gml", "id"), building_id)
        child(feature, "gml", "name", building["name"] or "Unnamed IFC building")
        hosts, records = {}, []
        for element in building["elements"]:
            if element["target_class"] != "BuildingConstructiveElement":
                continue
            node, identifier = write_element(child(feature, "bldg", "buildingConstructiveElement"), element)
            hosts[element["ifc_global_id"]] = node
            records.append({"citygml_id": identifier, "association": "building_constructive_element", **element})
        for element in building["elements"]:
            if element["target_class"] == "BuildingConstructiveElement":
                continue
            host = hosts.get(element["host_global_id"])
            if host is not None:
                parent = ET.SubElement(host, f"{{{CON}}}filling")
                association = "source_host_construction_filling"
            else:
                parent = child(root, "core", "cityObjectMember")
                association = "standalone_filling_no_selected_host; building membership retained in provenance"
            _, identifier = write_element(parent, element)
            records.append({"citygml_id": identifier, "association": association, **element})
        # Derived-class code follows inherited filling properties in XSD order.
        for element in building["elements"]:
            if element["target_class"] == "BuildingConstructiveElement":
                child(hosts[element["ifc_global_id"]], "bldg", "class", element["ifc_class"], codeSpace=CLASS_CODES)
        for node in root.iter():
            if node.tag in (f"{{{CON}}}Door", f"{{{CON}}}Window") and node.find(f"{{{CON}}}class") is None:
                ET.SubElement(node, f"{{{CON}}}class", codeSpace=CLASS_CODES).text = "Ifc" + ET.QName(node).localname
        for record in records:
            # Coordinates are already in the extraction report; avoid duplication
            # in the source-link sidecar while retaining per-feature fingerprints.
            record.pop("vertices")
            record.pop("triangles")
        links.append({"citygml_id": building_id, "source_building_global_id": building["source_building_global_id"],
                      "operation": "preserve_source_constructive_and_filling_surfaces", "element_links": records,
                      "omitted": building["omitted"],
                      "information_loss": ["IFC parametric representation replaced by tessellation", "unselected IFC classes", "native IFC spatial hierarchy retained in provenance rather than fully mapped"]})
    data = ET.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    # Verify the serialized float64 coordinates and triangle order against source
    # geometry after the declared output transform, before any external adapter.
    actual_rings = {}
    for polygon in ET.fromstring(data).findall(".//gml:Polygon", NS):
        pos = polygon.find("./gml:exterior/gml:LinearRing/gml:posList", NS)
        actual_rings[polygon.get(tag("gml", "id"))] = np.array([float(v) for v in pos.text.split()]).reshape(-1, 3)[:-1].tolist()
    if actual_rings != expected_rings:
        raise ValueError("Source-to-GML coordinate/order fidelity check failed")
    fingerprint = hashlib.sha256(json.dumps(actual_rings, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
    extraction["serialization_fidelity"] = {"exact_transformed_float64_rings": True,
        "triangle_count": len(actual_rings), "ring_sha256": fingerprint,
        "unmodified_source_coordinates": profile["coordinate_mode"] in ("local_engineering", "engineering_with_map_provenance")}
    return data, links
