"""Write source-attributed triangulated thematic surfaces and an envelope view."""
from collections import defaultdict

import ifcopenshell.guid
from lxml import etree as ET
import numpy as np

from .citygml_writer import NS, child, tag, format_points, SCHEMA_URL
from .common import transform_points

CON = "http://www.opengis.net/citygml/construction/3.0"
XLINK = "http://www.w3.org/1999/xlink"


def create_exterior_document(extraction, profile):
    namespaces = {**NS, "con": CON, "xlink": XLINK}
    root = ET.Element(tag("core", "CityModel"), nsmap=namespaces)
    root.set(tag("gml", "id"), "citymodel_" + extraction["input_sha256"][:16])
    root.set(tag("xsi", "schemaLocation"), f"{NS['bldg']} {SCHEMA_URL}")
    child(root, "gml", "description", "Selected material-union outer shells with source-attributed heuristic thematic surfaces; local/synthetic coordinates.")
    links = []
    for building in extraction["buildings"]:
        identifier = "b_" + ifcopenshell.guid.expand(building["source_building_global_id"])
        feature = child(child(root, "core", "cityObjectMember"), "bldg", "Building")
        feature.set(tag("gml", "id"), identifier)
        child(feature, "gml", "name", building["name"] or "Unnamed IFC building")
        groups = defaultdict(list)
        component_ids = []
        for index, component in enumerate(building["components"]):
            points = transform_points(np.array(component["vertices"]), profile)
            polygon_ids = []
            for number, (face, source_id, semantic) in enumerate(zip(component["triangles"], component["triangle_source_ids"], component["triangle_semantics"])):
                polygon_id = f"{identifier}_c{index}_t{number}"
                groups[(source_id, semantic)].append((polygon_id, points[[*face, face[0]]]))
                polygon_ids.append(polygon_id)
            component_ids.append(polygon_ids)
        group_nodes, surface_links = {}, []
        # Host construction surfaces precede their filling surfaces.
        order = sorted(groups, key=lambda key: (key[1] in ("DoorSurface", "WindowSurface"),
                                                building["sources"][key[0]]["ifc_global_id"], key[1]))
        for source_id, semantic in order:
            source = building["sources"][source_id]
            source_guid = source["ifc_global_id"]
            surface_id = "s_" + ifcopenshell.guid.expand(source_guid) + "_" + semantic
            host = next((node for (sid, kind), node in group_nodes.items()
                         if building["sources"][sid]["ifc_global_id"] == source["host_global_id"] and kind == "WallSurface"), None)
            if semantic in ("DoorSurface", "WindowSurface") and host is not None:
                parent = ET.SubElement(host, f"{{{CON}}}fillingSurface")
                association = "host_wall_fillingSurface"
            else:
                parent = child(feature, "core", "boundary")
                association = "building_boundary"
            thematic = ET.SubElement(parent, f"{{{CON}}}{semantic}")
            thematic.set(tag("gml", "id"), surface_id)
            child(thematic, "gml", "name", source["name"] or semantic)
            multi = child(child(thematic, "core", "lod2MultiSurface"), "gml", "MultiSurface",
                          srsName=profile["srs_name"], srsDimension="3")
            for polygon_id, ring in groups[(source_id, semantic)]:
                polygon = child(child(multi, "gml", "surfaceMember"), "gml", "Polygon")
                polygon.set(tag("gml", "id"), polygon_id)
                linear = child(child(polygon, "gml", "exterior"), "gml", "LinearRing")
                child(linear, "gml", "posList", format_points(ring), srsDimension="3")
            group_nodes[(source_id, semantic)] = thematic
            surface_links.append({"citygml_id": surface_id, "ifc_global_id": source_guid,
                                  "ifc_class": source["ifc_class"], "target_class": semantic,
                                  "triangle_count": len(groups[(source_id, semantic)]), "association": association,
                                  "host_global_id": source["host_global_id"],
                                  "classification_evidence": "Source class, exposed union geometry and normal/height heuristic"})
        multi = child(child(feature, "core", "lod2MultiSurface"), "gml", "MultiSurface",
                      srsName=profile["srs_name"], srsDimension="3")
        for number, polygon_ids in enumerate(component_ids):
            composite = child(child(multi, "gml", "surfaceMember"), "gml", "CompositeSurface")
            composite.set(tag("gml", "id"), f"{identifier}_component_{number}")
            for polygon_id in polygon_ids:
                member = child(composite, "gml", "surfaceMember")
                member.set(f"{{{XLINK}}}href", "#" + polygon_id)
        links.append({"citygml_id": identifier, "source_building_global_id": building["source_building_global_id"],
                      "operation": "selected_material_union_outer_shells", "surface_links": surface_links,
                      "enclosure_status": building["enclosure_status"], "removed_enclosed_cavities": building["removed_enclosed_cavities"],
                      "removed_nested_positive_components": building["removed_nested_positive_components"],
                      "information_loss": ["enclosed interior cavities", "unselected element classes", "full IFC property sets", "interior spatial hierarchy"],
                      "source_bounds_m": building["bounds_m"]})
    return ET.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8"), links
