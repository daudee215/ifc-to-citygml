from __future__ import annotations

import numpy as np
from lxml import etree as ET

from .common import transform_points

NS = {
    "core": "http://www.opengis.net/citygml/3.0",
    "bldg": "http://www.opengis.net/citygml/building/3.0",
    "gml": "http://www.opengis.net/gml/3.2",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}
SCHEMA_URL = "https://schemas.opengis.net/citygml/building/3.0/building.xsd"
# Outward oriented faces: bottom, top, south, east, north, west.
FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
         (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


def tag(prefix: str, name: str) -> str:
    return f"{{{NS[prefix]}}}{name}"


def child(parent, prefix: str, name: str, text: str | None = None, **attrs):
    node = ET.SubElement(parent, tag(prefix, name), **attrs)
    if text is not None:
        node.text = text
    return node


def corners(bounds: list) -> np.ndarray:
    (x0, y0, z0), (x1, y1, z1) = bounds
    return np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                     [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], dtype=float)


def format_points(points: np.ndarray) -> str:
    return " ".join(format(float(value), ".15g") for value in points.flat)


def create_document(extraction: dict, profile: dict) -> tuple[bytes, list[dict]]:
    root = ET.Element(tag("core", "CityModel"), nsmap=NS)
    root.set(tag("gml", "id"), "citymodel_" + extraction["input_sha256"][:16])
    root.set(tag("xsi", "schemaLocation"), f"{NS['bldg']} {SCHEMA_URL}")
    child(root, "gml", "description",
          "Research pilot: simplified bounding blocks. Coordinates are "
          + profile["coordinate_mode"] + "; not verified geographic building locations.")
    source_links = []
    for building in extraction["buildings"]:
        # IFC compressed GUIDs may contain '$', which is not an XML NCName.
        import ifcopenshell.guid
        identifier = "b_" + ifcopenshell.guid.expand(building["source_building_global_id"])
        member = child(root, "core", "cityObjectMember")
        feature = child(member, "bldg", "Building")
        feature.set(tag("gml", "id"), identifier)
        child(feature, "gml", "description", "Derived axis-aligned bounding block; element semantics and openings omitted.")
        child(feature, "gml", "name", building["name"] or "Unnamed IFC building")
        prop = child(feature, "core", "lod1Solid")
        solid = child(prop, "gml", "Solid", srsName=profile["srs_name"], srsDimension="3")
        solid.set(tag("gml", "id"), identifier + "_solid")
        shell = child(child(solid, "gml", "exterior"), "gml", "Shell")
        points = transform_points(corners(building["bounds_m"]), profile)
        for index, face in enumerate(FACES):
            polygon = child(child(shell, "gml", "surfaceMember"), "gml", "Polygon")
            polygon.set(tag("gml", "id"), f"{identifier}_face_{index}")
            ring = child(child(polygon, "gml", "exterior"), "gml", "LinearRing")
            child(ring, "gml", "posList", format_points(points[[*face, face[0]]]), srsDimension="3")
        source_links.append({
            "citygml_id": identifier, "source_building_global_id": building["source_building_global_id"],
            "operation": "derive_axis_aligned_bounding_block_in_ifc_world_frame_then_apply_output_transform",
            "source_bounds_m": building["bounds_m"],
            "output_bounds_m": [points.min(axis=0).tolist(), points.max(axis=0).tolist()],
            "block_dimensions_before_transform_m": (np.diff(np.array(building["bounds_m"]), axis=0)[0]).tolist(),
            "contributors": building["contributors"], "omitted": building["omitted"],
            "information_loss": ["element-level geometry", "wall/roof boundary semantics", "openings", "interiors", "selected properties"],
        })
    return ET.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8"), source_links
