"""Audit physical block inventory, bounds, XML faces and engineering provenance.

Uses original IFC and a separate selection implementation; imports no production
block extractor, representation selector or writer.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.guid
import numpy as np
from lxml import etree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.semantic_audit import inventory

NS = {"gml": "http://www.opengis.net/gml/3.2", "core": "http://www.opengis.net/citygml/3.0", "bldg": "http://www.opengis.net/citygml/building/3.0"}
ID = "{" + NS["gml"] + "}id"
TOLERANCE = 1e-6


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(source, gml, links_path):
    source, gml, links_path = map(Path, (source, gml, links_path))
    model = ifcopenshell.open(str(source))
    root = ET.fromstring(gml.read_bytes(), ET.XMLParser(resolve_entities=False, no_network=True))
    groups = json.loads(links_path.read_text())
    issues, findings = [], []
    def check(condition, code, **context):
        if not condition:
            issues.append({"code": code, **context})
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("convert-back-units", False)
    buildings = inventory(model)
    check(Counter(b["source_building_global_id"] for b in groups) == Counter(buildings.keys()), "building_inventory")
    check(Counter(n.get(ID) for n in root.findall("./core:cityObjectMember/bldg:Building", NS)) ==
          Counter("b_" + ifcopenshell.guid.expand(g) for g in buildings), "xml_building_inventory")
    original_ops = [] if model.schema == "IFC2X3" else json.loads(json.dumps([op.get_info(recursive=True) for op in model.by_type("IfcCoordinateOperation")]))
    original_crs = [] if model.schema == "IFC2X3" else json.loads(json.dumps([crs.get_info(recursive=True) for crs in model.by_type("IfcProjectedCRS")]))
    for building_guid, descendants in buildings.items():
        matches = [b for b in groups if b["source_building_global_id"] == building_guid]
        if len(matches) != 1:
            continue
        group = matches[0]
        building = model.by_guid(building_guid)
        elements = [e for e in descendants if not e.is_a("IfcVirtualElement")]
        if building.Representation:
            elements.append(building)
        expected, omitted, clouds = {}, {}, []
        for element in elements:
            guid = element.GlobalId
            check(bool(guid) and guid not in expected and guid not in omitted, "source_identity_ambiguity", step_id=element.id())
            record = {"ifc_global_id": guid, "step_id": element.id(), "ifc_class": element.is_a(), "name": element.Name}
            if not element.Representation:
                omitted[guid] = {**record, "reason": "No source representation; not an exported semantic feature"}
                continue
            representations = list(element.Representation.Representations)
            descriptions = [{"step_id": r.id(), "ifc_class": r.is_a(), "identifier": r.RepresentationIdentifier,
                "representation_type": r.RepresentationType, "context_step_id": r.ContextOfItems.id(),
                "context_type": r.ContextOfItems.ContextType, "item_step_ids": [i.id() for i in r.Items]} for r in representations]
            labels = [r.RepresentationIdentifier for r in representations]
            if labels and all(label == "Annotation" for label in labels):
                omitted[guid] = {**record, "reason": "Annotation-only source representation; excluded from physical bounding block",
                                 "representations": descriptions}
                continue
            selected = [r for r in representations if r.RepresentationIdentifier == "Body"]
            if not selected:
                selected = [r for r in representations if r.RepresentationIdentifier == "Body-FallBack"]
            check(bool(selected), "unsupported_physical_representation", ifc_global_id=guid)
            count = 0
            for rep in selected:
                try:
                    shape = ifcopenshell.geom.create_shape(settings, element, repr=rep)
                    points = np.array(shape.geometry.verts).reshape(-1, 3)
                    check(len(points) > 0 and np.isfinite(points).all(), "invalid_source_vertices", ifc_global_id=guid)
                    if not len(points) or not np.isfinite(points).all():
                        continue
                    clouds.append(points)
                    count += len(points)
                except Exception as exc:
                    check(False, "source_geometry_failure", ifc_global_id=guid, error=str(exc))
            expected[guid] = {**record, "vertex_count": count, "selected": [r.id() for r in selected], "representations": descriptions}
        contributors = group["contributors"]
        check(Counter(c["ifc_global_id"] for c in contributors) == Counter(expected.keys()), "contributor_inventory", building=building_guid)
        check(Counter((o["ifc_global_id"], o["reason"]) for o in group["omitted"]) ==
              Counter((g, r["reason"]) for g, r in omitted.items()), "omission_inventory", building=building_guid)
        for actual in [*contributors, *group["omitted"]]:
            guid = actual["ifc_global_id"]
            reference = expected.get(guid, omitted.get(guid))
            if reference is None:
                continue
            check(all(actual.get(k) == reference[k] for k in ("step_id", "ifc_class", "name")), "source_identity", ifc_global_id=guid)
            if "representations" in reference:
                selection = actual.get("representation_selection", {})
                check(selection.get("policy") == "explicit_body_with_annotation_omissions_v1" and
                      selection.get("source_representations") == reference["representations"] and
                      selection.get("selected_step_ids") == reference.get("selected", []), "representation_provenance", ifc_global_id=guid)
                selected_ids = reference.get("selected", [])
                expected_level = next((r["identifier"] for r in reference["representations"] if r["step_id"] in selected_ids), None)
                check(selection.get("status") == ("selected" if selected_ids else "annotation_only") and
                      (not selected_ids or selection.get("selection_level") == expected_level), "selection_status", ifc_global_id=guid)
                excluded = [{**r, "reason": "Not selected by physical Body precedence" if selected_ids else "Explicit Annotation representation"}
                            for r in reference["representations"] if r["step_id"] not in selected_ids]
                check(selection.get("excluded_representations") == excluded, "excluded_representation_provenance", ifc_global_id=guid)
            if guid in expected:
                check(actual.get("vertex_count") == reference["vertex_count"], "vertex_count", ifc_global_id=guid)
                check(actual.get("role") == "aggregated_into_bounding_block" and actual.get("semantic_feature_preserved") is False,
                      "contribution_role", ifc_global_id=guid)
        policy = group.get("coordinate_provenance")
        if original_ops or policy is not None:
            check(isinstance(policy, dict) and policy.get("operation_applied") is False and
                  policy.get("source_input_sha256") == sha(source) and
                  policy.get("original_coordinate_operations") == original_ops and
                  policy.get("original_projected_crs") == original_crs and
                  policy.get("output_srs_name") == "urn:ifc-citygml:crs:local-engineering-metres", "engineering_provenance", building=building_guid)
            description = root.find("gml:description", NS)
            check(description is not None and "has not been applied" in (description.text or ""), "engineering_notice", building=building_guid)
        if not clouds:
            check(False, "no_source_geometry", building=building_guid)
            continue
        points = np.vstack(clouds)
        bounds = np.array([points.min(axis=0), points.max(axis=0)])
        check(np.array_equal(np.asarray(group["source_bounds_m"]), bounds), "source_bounds_provenance", building=building_guid)
        check(np.array_equal(np.asarray(group["output_bounds_m"]), bounds), "unsupported_output_transform", building=building_guid)
        identifier = "b_" + ifcopenshell.guid.expand(building_guid)
        features = root.xpath('//*[@gml:id=$id]', namespaces=NS, id=identifier)
        if len(features) != 1:
            check(False, "xml_building_identity", building=building_guid)
            continue
        solids = features[0].findall("./core:lod1Solid/gml:Solid", NS)
        check(len(solids) == 1 and solids[0].get("srsName") == "urn:ifc-citygml:crs:local-engineering-metres", "xml_frame", building=building_guid)
        positions = features[0].findall("./core:lod1Solid/gml:Solid/gml:exterior/gml:Shell/gml:surfaceMember/gml:Polygon/gml:exterior/gml:LinearRing/gml:posList", NS)
        corner_bits = list(itertools.product((0, 1), repeat=3))
        corners = np.array([[bounds[bit[a], a] for a in range(3)] for bit in corner_bits])
        expected_faces = Counter(frozenset(i for i, bits in enumerate(corner_bits) if bits[axis] == side) for axis in range(3) for side in (0, 1))
        actual_faces, errors = [], []
        for position in positions:
            ring = np.array([float(v) for v in position.text.split()]).reshape(-1, 3)
            if ring.shape != (5, 3) or not np.array_equal(ring[0], ring[-1]):
                check(False, "block_ring", building=building_guid)
                continue
            distances = np.max(np.abs(ring[:-1, None, :] - corners[None, :, :]), axis=2)
            indices = distances.argmin(axis=1)
            errors.extend(distances.min(axis=1).tolist())
            actual_faces.append(frozenset(indices.tolist()))
            adjacent = all(sum(a != b for a, b in zip(corner_bits[indices[i]], corner_bits[indices[(i + 1) % 4]])) == 1 for i in range(4))
            check(adjacent, "block_face_cycle", building=building_guid)
            normal = np.cross(ring[1] - ring[0], ring[2] - ring[1])
            check(np.dot(normal, ring[:-1].mean(axis=0) - bounds.mean(axis=0)) > 0, "block_face_orientation", building=building_guid)
        check(Counter(actual_faces) == expected_faces, "block_face_inventory", building=building_guid)
        error = max(errors, default=float("inf"))
        check(error <= TOLERANCE, "xml_corner_coordinates", building=building_guid, max_error_m=error)
        findings.append({"building": building_guid, "physical_contributors": len(expected), "omitted": len(omitted),
                         "annotation_only_omissions": sum("representations" in r for r in omitted.values()),
                         "mixed_products": sum(any(r["identifier"] == "Annotation" for r in e["representations"]) for e in expected.values()),
                         "source_bounds_m": bounds.tolist(), "xml_max_corner_error_m": error if np.isfinite(error) else None,
                         "source_vertex_count": len(points)})
    return {"status": "failed" if issues else "passed", "input": str(source.resolve()), "input_sha256": sha(source),
            "gml": str(gml.resolve()), "gml_sha256": sha(gml), "links": str(links_path.resolve()), "links_sha256": sha(links_path),
            "audit_source_sha256": sha(__file__), "xml_tolerance_m": TOLERANCE, "buildings": findings, "issues": issues,
            "scope": "Physical representation inventory and bounded AABB serialization in engineering metres; not a building volume or geographic accuracy claim"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("input", "gml", "links", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.input, args.gml, args.links)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "buildings": result["buildings"], "issue_count": len(result["issues"])}))
    raise SystemExit(0 if result["status"] == "passed" else 2)


if __name__ == "__main__":
    main()
