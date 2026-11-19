"""Independent research audit of the local source-surface profile, not a converter.

Reads original IFC relationships, tessellates afresh and reads actual XML and the
sidecar. Does not import production extraction, mapping or writer functions.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.guid
import ifcopenshell.util.element
from lxml import etree as ET
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NS = {"gml": "http://www.opengis.net/gml/3.2", "core": "http://www.opengis.net/citygml/3.0",
      "bldg": "http://www.opengis.net/citygml/building/3.0", "con": "http://www.opengis.net/citygml/construction/3.0"}
# Normative evaluation subset, separately reviewed in docs/SEMANTIC_MAPPING.md.
CONSTRUCTIVE = ("IfcWall", "IfcSlab", "IfcRoof", "IfcBeam", "IfcColumn", "IfcMember", "IfcPlate",
                "IfcFooting", "IfcPile", "IfcStair", "IfcStairFlight", "IfcCurtainWall")
ID = "{" + NS["gml"] + "}id"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(model):
    """Traverse forward IFC relationships, independently of get_decomposition."""
    children = defaultdict(list)
    for kind, parent, offspring in (("IfcRelAggregates", "RelatingObject", "RelatedObjects"),
            ("IfcRelNests", "RelatingObject", "RelatedObjects"),
            ("IfcRelContainedInSpatialStructure", "RelatingStructure", "RelatedElements"),
            ("IfcRelVoidsElement", "RelatingBuildingElement", "RelatedOpeningElement"),
            ("IfcRelFillsElement", "RelatingOpeningElement", "RelatedBuildingElement")):
        for relation in model.by_type(kind):
            targets = getattr(relation, offspring)
            children[getattr(relation, parent).id()].extend(targets if isinstance(targets, tuple) else [targets])
    buildings = {}
    for building in model.by_type("IfcBuilding"):
        pending, visited, elements = list(children[building.id()]), set(), []
        while pending:
            entity = pending.pop()
            if entity.id() in visited:
                continue
            visited.add(entity.id())
            pending.extend(children[entity.id()])
            if entity.is_a("IfcElement") and not entity.is_a("IfcFeatureElement"):
                elements.append(entity)
        buildings[building.GlobalId] = elements
    return buildings


def audit(source, gml, links_path, expected_path=None):
    source, gml, links_path = map(Path, (source, gml, links_path))
    model = ifcopenshell.open(str(source))
    if model.schema not in {"IFC4", "IFC2X3"}:
        raise ValueError("Audit currently covers IFC4/IFC2X3 local source surfaces")
    root = ET.fromstring(gml.read_bytes(), ET.XMLParser(resolve_entities=False, no_network=True))
    links = json.loads(links_path.read_text())
    issues, records, omissions = [], [], []
    def check(condition, code, **context):
        if not condition:
            issues.append({"code": code, **context})
    nodes = defaultdict(list)
    for node in root.xpath("//*[@gml:id]", namespaces=NS):
        nodes[node.get(ID)].append(node)
    check(all(len(v) == 1 for v in nodes.values()), "duplicate_xml_id")
    by_building = inventory(model)
    source_operations = [] if model.schema == "IFC2X3" else json.loads(json.dumps([op.get_info(recursive=True) for op in model.by_type("IfcCoordinateOperation")]))
    source_crs = [] if model.schema == "IFC2X3" else json.loads(json.dumps([crs.get_info(recursive=True) for crs in model.by_type("IfcProjectedCRS")]))
    linked_buildings = [b["source_building_global_id"] for b in links]
    check(Counter(linked_buildings) == Counter(by_building.keys()), "building_inventory_mismatch")
    seen_features, expected_feature_count = [], 0
    check(Counter(n.get(ID) for n in root.findall(".//bldg:Building", NS)) ==
          Counter("b_" + ifcopenshell.guid.expand(g) for g in by_building), "xml_building_inventory")
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("convert-back-units", False)
    for building_guid, elements in by_building.items():
        link_groups = [b for b in links if b["source_building_global_id"] == building_guid]
        if len(link_groups) != 1:
            continue
        group = link_groups[0]
        coordinate_provenance = group.get("coordinate_provenance")
        if source_operations or coordinate_provenance is not None:
            check(isinstance(coordinate_provenance, dict), "missing_unapplied_map_provenance", building=building_guid)
            if isinstance(coordinate_provenance, dict):
                check(coordinate_provenance.get("operation_applied") is False and
                      coordinate_provenance.get("source_input_sha256") == sha(source) and
                      coordinate_provenance.get("original_coordinate_operations") == source_operations and
                      coordinate_provenance.get("original_projected_crs") == source_crs and
                      coordinate_provenance.get("output_srs_name") == "urn:ifc-citygml:crs:local-engineering-metres",
                      "unapplied_map_metadata_mismatch", building=building_guid)
            description = root.find("gml:description", NS)
            check(description is not None and "has not been applied" in (description.text or ""), "missing_engineering_frame_notice", building=building_guid)
        building_id = "b_" + ifcopenshell.guid.expand(building_guid)
        check(group["citygml_id"] == building_id, "building_id_provenance", building=building_guid)
        check(len(nodes.get(building_id, [])) == 1 and nodes[building_id][0].tag == "{" + NS["bldg"] + "}Building", "xml_building_identity", building=building_guid)
        guids = [e.GlobalId for e in elements]
        check(all(guids) and len(guids) == len(set(guids)), "ambiguous_source_identity", building=building_guid)
        expected, excluded = {}, {}
        for entity in elements:
            target = "Door" if entity.is_a("IfcDoor") else "Window" if entity.is_a("IfcWindow") else (
                "BuildingConstructiveElement" if any(entity.is_a(c) for c in CONSTRUCTIVE) else None)
            if target is None or not entity.Representation:
                reason = "Outside declared constructive/filling profile" if target is None else "No source representation"
                excluded[entity.GlobalId] = reason
                omissions.append({"building": building_guid, "ifc_global_id": entity.GlobalId,
                                 "ifc_class": entity.is_a(), "reason": reason})
            else:
                expected[entity.GlobalId] = (entity, target)
        expected_feature_count += len(expected)
        actual = group["element_links"]
        check(Counter(e["ifc_global_id"] for e in actual) == Counter(expected.keys()), "selected_inventory_mismatch", building=building_guid)
        actual_omissions = [(e["ifc_global_id"], e["reason"]) for e in group["omitted"]]
        check(Counter(actual_omissions) == Counter(excluded.items()), "omission_inventory_mismatch", building=building_guid)
        source_elements = {e.GlobalId: e for e in elements}
        for omission in group["omitted"]:
            source_element = source_elements.get(omission["ifc_global_id"])
            check(source_element is not None and omission.get("ifc_class") == source_element.is_a()
                  and omission.get("step_id") == source_element.id(), "omission_source_identity", building=building_guid)
        for link in actual:
            guid = link["ifc_global_id"]
            if guid not in expected:
                continue
            entity, target = expected[guid]
            identifier = "e_" + ifcopenshell.guid.expand(guid)
            seen_features.append(identifier)
            context = {"ifc_global_id": guid, "building": building_guid}
            check(link["citygml_id"] == identifier, "element_id_provenance", **context)
            check(link["ifc_class"] == entity.is_a() and link["step_id"] == entity.id(), "source_identity", **context)
            check(link["target_class"] == target, "sidecar_target_class", **context)
            if len(nodes.get(identifier, [])) != 1:
                check(False, "missing_xml_feature", **context)
                continue
            node = nodes[identifier][0]
            prefix = "bldg" if target == "BuildingConstructiveElement" else "con"
            check(node.tag == "{" + NS[prefix] + "}" + target, "xml_target_class", **context)
            code = node.find(prefix + ":class", NS)
            check(code is not None and code.text == entity.is_a() and code.get("codeSpace") == "urn:ifc-citygml:codelist:ifc-entity", "source_class_code", **context)
            hosts = set()
            for fill in model.by_type("IfcRelFillsElement"):
                if fill.RelatedBuildingElement == entity:
                    for void in model.by_type("IfcRelVoidsElement"):
                        if void.RelatedOpeningElement == fill.RelatingOpeningElement:
                            hosts.add(void.RelatingBuildingElement.GlobalId)
            check(len(hosts) <= 1, "ambiguous_source_host", **context)
            host = next(iter(hosts), None)
            check(link["host_global_id"] == host, "host_provenance", **context)
            hosted = host in expected and expected[host][1] == "BuildingConstructiveElement"
            if target == "BuildingConstructiveElement":
                association = "building_constructive_element"
                correct_parent = node.getparent().tag == "{" + NS["bldg"] + "}buildingConstructiveElement" and node.getparent().getparent().get(ID) == building_id
            elif hosted:
                association = "source_host_construction_filling"
                correct_parent = node.getparent().tag == "{" + NS["con"] + "}filling" and node.getparent().getparent().get(ID) == "e_" + ifcopenshell.guid.expand(host)
            else:
                association = "standalone_filling_no_selected_host; building membership retained in provenance"
                correct_parent = node.getparent().tag == "{" + NS["core"] + "}cityObjectMember" and node.getparent().getparent() == root
            check(correct_parent and link["association"] == association, "host_association", **context)
            check(node.find("con:isStructuralElement", NS) is None, "unsupported_structural_inference", **context)
            psets = json.loads(json.dumps(ifcopenshell.util.element.get_psets(entity), default=str, allow_nan=False))
            check(link["source_property_sets"] == psets, "property_provenance", **context)
            opening_relations = []
            for void in model.by_type("IfcRelVoidsElement"):
                if void.RelatingBuildingElement == entity:
                    opening = void.RelatedOpeningElement
                    filling_ids = sorted(f.RelatedBuildingElement.GlobalId for f in model.by_type("IfcRelFillsElement") if f.RelatingOpeningElement == opening)
                    opening_relations.append((opening.GlobalId, opening.id(), filling_ids))
            actual_openings = [(o["opening_global_id"], o["opening_step_id"], sorted(o["filling_global_ids"])) for o in link["opening_relations"]]
            check(sorted(actual_openings) == sorted(opening_relations), "opening_provenance", **context)
            try:
                shape = ifcopenshell.geom.create_shape(settings, entity)
                vertices = np.asarray(shape.geometry.verts, dtype=np.float64).reshape(-1, 3)
                triangles = np.asarray(shape.geometry.faces, dtype=np.int64).reshape(-1, 3)
                original = vertices[triangles]
                multi = node.find("core:lod2MultiSurface/gml:MultiSurface", NS)
                check(multi is not None and multi.get("srsName") == "urn:ifc-citygml:crs:local-engineering-metres", "unsupported_coordinate_frame", **context)
                positions = node.findall("core:lod2MultiSurface/gml:MultiSurface/gml:surfaceMember/gml:Polygon/gml:exterior/gml:LinearRing/gml:posList", NS)
                rings = [np.array([float(v) for v in p.text.split()]).reshape(-1, 3) for p in positions]
                check(all(r.shape == (4, 3) and np.array_equal(r[0], r[-1]) for r in rings), "triangle_ring_structure", **context)
                same = len(rings) == len(original) and all(np.array_equal(r[:-1], t) for r, t in zip(rings, original))
                check(same, "source_triangle_coordinates_or_order", **context)
                fingerprint = hashlib.sha256(np.ascontiguousarray(original, dtype="<f8").tobytes()).hexdigest()
                check(fingerprint == link["source_triangle_coordinate_sha256"], "triangle_fingerprint", **context)
                records.append({**context, "name": entity.Name, "ifc_class": entity.is_a(), "target_class": target,
                                "host_global_id": host, "association": association, "triangles": len(original), "exact_geometry": same})
            except Exception as exc:
                check(False, "source_geometry_audit_error", error=str(exc), **context)
    xml_features = root.xpath("//bldg:BuildingConstructiveElement | //con:Door | //con:Window", namespaces=NS)
    check(Counter(n.get(ID) for n in xml_features) == Counter(seen_features), "unlinked_xml_features")
    if expected_path:
        expected_fixture = json.loads(Path(expected_path).read_text())
        observed = {r["name"]: {k: r[k] for k in ("ifc_class", "target_class", "association", "host_global_id")} for r in records}
        check(len(observed) == len(records), "fixture_duplicate_names")
        check(observed == expected_fixture["features"], "authored_fixture_expectations")
        check(Counter((o["ifc_global_id"], o["reason"]) for o in omissions) == Counter((o["ifc_global_id"], o["reason"]) for o in expected_fixture["omissions"]), "authored_fixture_omissions")
    return {"status": "failed" if issues else "passed", "input": str(source.resolve()), "input_sha256": sha(source),
            "gml": str(gml.resolve()), "links": str(links_path.resolve()),
            "expected_annotations": str(Path(expected_path).resolve()) if expected_path else None,
            "expected_annotations_sha256": sha(expected_path) if expected_path else None,
            "gml_sha256": sha(gml), "links_sha256": sha(links_path), "audit_source_sha256": sha(__file__),
            "mapping_spec_sha256": sha(ROOT / "docs/SEMANTIC_MAPPING.md"),
            "expected_features": expected_feature_count, "exported_features": len(xml_features),
            "selected_features": len(records), "triangles_checked": sum(r["triangles"] for r in records),
            "by_target_class": dict(Counter(r["target_class"] for r in records)),
            "by_association": dict(Counter(r["association"] for r in records)),
            "omission_reasons": dict(Counter(o["reason"] for o in omissions)),
            "features": records, "omissions": omissions, "issues": issues,
            "scope": "Agreement with declared source mapping and fresh IfcOpenShell tessellation; not independent real-building semantic truth"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--gml", type=Path, required=True)
    parser.add_argument("--links", type=Path, required=True)
    parser.add_argument("--expected", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.input, args.gml, args.links, args.expected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "selected_features", "triangles_checked", "omission_reasons")}))
    raise SystemExit(0 if result["status"] == "passed" else 2)


if __name__ == "__main__":
    main()
