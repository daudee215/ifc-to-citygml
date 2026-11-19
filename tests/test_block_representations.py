import json
import copy

import ifcopenshell
import ifcopenshell.guid
import ifcopenshell.util.element
import numpy as np
import pytest
from lxml import etree as ET

from scripts.generate_fixtures import make_fixture
from tests.test_georeferencing import mapped_fixture
from ifc_citygml.pipeline import ConversionFailure, convert
from scripts.block_audit import audit, NS


def save_variant(model, path):
    variant = path.with_name(path.stem + "_variant.ifc")
    model.write(str(variant))
    return variant


def add_annotation(model, product=None):
    context = model.by_type("IfcGeometricRepresentationContext", include_subtypes=False)[0]
    line = model.create_entity("IfcPolyline", Points=[model.create_entity("IfcCartesianPoint", Coordinates=p)
        for p in ((10000., 10000., 0.), (20000., 10000., 0.))])
    curves = model.create_entity("IfcGeometricCurveSet", Elements=[line])
    rep = model.create_entity("IfcShapeRepresentation", ContextOfItems=context,
        RepresentationIdentifier="Annotation", RepresentationType="GeometricSet", Items=[curves])
    if product is None:
        original = model.by_type("IfcDoor")[0]
        product = model.create_entity("IfcBuildingElementProxy", GlobalId=ifcopenshell.guid.new(),
            OwnerHistory=original.OwnerHistory, Name="Explicit annotation-only proxy", ObjectPlacement=original.ObjectPlacement,
            Representation=model.create_entity("IfcProductDefinitionShape", Representations=[rep]))
        rel = model.by_type("IfcRelContainedInSpatialStructure")[0]
        rel.RelatedElements = (*rel.RelatedElements, product)
    else:
        product.Representation.Representations = (*product.Representation.Representations, rep)
    return product, rep


@pytest.mark.parametrize("schema", ["IFC4", "IFC2X3"])
def test_annotation_only_product_is_accounted_for_without_inflating_block(tmp_path, schema):
    source, output = tmp_path / "annotation.ifc", tmp_path / "block.gml"
    make_fixture(source, schema=schema)
    model = ifcopenshell.open(str(source))
    annotation, rep = add_annotation(model)
    source = save_variant(model, source)
    original = source.read_bytes()
    report = convert(source, output, "block")
    assert source.read_bytes() == original
    assert report["status"] == "passed"
    block = report["extraction"]["buildings"][0]
    np.testing.assert_array_equal(block["bounds_m"], [[105, 207, 13], [117, 215, 19]])
    assert len(block["contributors"]) == 7
    omitted = next(o for o in block["omitted"] if o["ifc_global_id"] == annotation.GlobalId)
    assert "Annotation-only" in omitted["reason"]
    assert omitted["step_id"] == annotation.id() and omitted["ifc_class"] == "IfcBuildingElementProxy"
    assert omitted["representation_selection"]["selected_step_ids"] == []
    assert omitted["representation_selection"]["source_representations"][0]["step_id"] == rep.id()
    assert report["source_links"][0]["omitted"] == block["omitted"]


def test_mixed_product_keeps_body_and_excludes_distant_annotation(tmp_path):
    source, output = tmp_path / "mixed.ifc", tmp_path / "block.gml"
    mapped_fixture(source, crs="EPSG:3763")
    model = ifcopenshell.open(str(source))
    wall = model.by_type("IfcWall")[0]
    body = wall.Representation.Representations[0]
    _, annotation = add_annotation(model, wall)
    source = save_variant(model, source)
    original = source.read_bytes()
    report = convert(source, output, "engineering-block")
    assert source.read_bytes() == original
    np.testing.assert_array_equal(report["extraction"]["buildings"][0]["bounds_m"], [[105, 207, 13], [117, 215, 19]])
    contribution = next(c for c in report["source_links"][0]["contributors"] if c["ifc_global_id"] == wall.GlobalId)
    selection = contribution["representation_selection"]
    assert selection["selected_step_ids"] == [body.id()]
    assert selection["excluded_representations"][0]["step_id"] == annotation.id()
    assert report["source_links"][0]["coordinate_provenance"]["operation_applied"] is False


def test_proxy_with_a_physical_body_is_not_dropped_by_product_class(tmp_path):
    source, output = tmp_path / "physical_proxy.ifc", tmp_path / "block.gml"
    make_fixture(source)
    model = ifcopenshell.open(str(source))
    template = model.by_type("IfcDoor")[0]
    definition = model.create_entity("IfcProductDefinitionShape", Representations=list(template.Representation.Representations))
    proxy = model.create_entity("IfcBuildingElementProxy", GlobalId=ifcopenshell.guid.new(), OwnerHistory=template.OwnerHistory,
        Name="Physical proxy with Body and Annotation", ObjectPlacement=template.ObjectPlacement, Representation=definition)
    contained = model.by_type("IfcRelContainedInSpatialStructure")[0]
    contained.RelatedElements = (*contained.RelatedElements, proxy)
    add_annotation(model, proxy)
    source = save_variant(model, source)
    report = convert(source, output, "block")
    block = report["extraction"]["buildings"][0]
    assert len(block["contributors"]) == 8
    assert not any(o["ifc_global_id"] == proxy.GlobalId for o in block["omitted"])
    contribution = next(c for c in block["contributors"] if c["ifc_global_id"] == proxy.GlobalId)
    assert contribution["representation_selection"]["selection_level"] == "Body"
    result = audit(source, output, output.with_suffix(".source_links.json"))
    assert result["status"] == "passed", result["issues"]


@pytest.mark.parametrize("identifier", ["Axis", "FootPrint", "Reference", None, "annotation"])
def test_unrecognised_or_nonbody_geometry_is_not_silently_called_an_annotation(tmp_path, identifier):
    source, output = tmp_path / "unsupported.ifc", tmp_path / "block.gml"
    make_fixture(source)
    model = ifcopenshell.open(str(source))
    _, representation = add_annotation(model)
    representation.RepresentationIdentifier = identifier
    source = save_variant(model, source)
    with pytest.raises(ConversionFailure):
        convert(source, output, "block")
    report = json.loads(output.with_suffix(".report.json").read_text())
    assert any("No supported physical" in f["reason"] for f in report["extraction"]["failures"])
    assert not output.exists()


def test_invalid_body_does_not_fall_back_to_valid_alternate_or_ignore_failure(tmp_path):
    source, output = tmp_path / "bad_body.ifc", tmp_path / "block.gml"
    make_fixture(source)
    model = ifcopenshell.open(str(source))
    door = model.by_type("IfcDoor")[0]
    body = door.Representation.Representations[0]
    fallback = ifcopenshell.util.element.copy_deep(model, body)
    fallback.RepresentationIdentifier = "Body-FallBack"
    body.Items[0].SweptArea.XDim = 0.
    door.Representation.Representations = (body, fallback)
    add_annotation(model, door)
    source = save_variant(model, source)
    with pytest.raises(ConversionFailure):
        convert(source, output, "block")
    assert not output.exists()


def test_declared_body_fallback_is_used_only_when_no_body_exists(tmp_path):
    source, output = tmp_path / "fallback.ifc", tmp_path / "block.gml"
    make_fixture(source)
    model = ifcopenshell.open(str(source))
    door = model.by_type("IfcDoor")[0]
    door.Representation.Representations[0].RepresentationIdentifier = "Body-FallBack"
    source = save_variant(model, source)
    report = convert(source, output, "block")
    contribution = next(c for c in report["source_links"][0]["contributors"] if c["ifc_global_id"] == door.GlobalId)
    assert contribution["representation_selection"]["selection_level"] == "Body-FallBack"


def test_valid_primary_body_takes_precedence_over_distant_fallback(tmp_path):
    source, output = tmp_path / "primary.ifc", tmp_path / "block.gml"
    make_fixture(source)
    model = ifcopenshell.open(str(source))
    door = model.by_type("IfcDoor")[0]
    body = door.Representation.Representations[0]
    fallback = ifcopenshell.util.element.copy_deep(model, body)
    fallback.RepresentationIdentifier = "Body-FallBack"
    fallback.Items[0].Position.Location.Coordinates = (10000., 0., 0.)
    door.Representation.Representations = (body, fallback)
    source = save_variant(model, source)
    report = convert(source, output, "block")
    np.testing.assert_array_equal(report["extraction"]["buildings"][0]["bounds_m"], [[105, 207, 13], [117, 215, 19]])
    result = audit(source, output, output.with_suffix(".source_links.json"))
    assert result["status"] == "passed", result["issues"]


def test_multiple_physical_bodies_are_all_retained(tmp_path):
    source, output = tmp_path / "two_bodies.ifc", tmp_path / "block.gml"
    make_fixture(source)
    model = ifcopenshell.open(str(source))
    door = model.by_type("IfcDoor")[0]
    body = door.Representation.Representations[0]
    additional = ifcopenshell.util.element.copy_deep(model, body)
    additional.Items[0].Position.Location.Coordinates = (20., 0., 0.)
    context = model.create_entity("IfcGeometricRepresentationContext", ContextIdentifier="Second physical view", ContextType="Model",
        CoordinateSpaceDimension=3, Precision=1e-6, WorldCoordinateSystem=body.ContextOfItems.WorldCoordinateSystem)
    additional.ContextOfItems = context
    project = model.by_type("IfcProject")[0]
    project.RepresentationContexts = (*project.RepresentationContexts, context)
    door.Representation.Representations = (body, additional)
    add_annotation(model, door)
    source = save_variant(model, source)
    report = convert(source, output, "block")
    np.testing.assert_array_equal(report["extraction"]["buildings"][0]["bounds_m"], [[105, 207, 13], [127, 215, 19]])
    contribution = next(c for c in report["source_links"][0]["contributors"] if c["ifc_global_id"] == door.GlobalId)
    assert contribution["representation_selection"]["selected_step_ids"] == [body.id(), additional.id()]
    result = audit(source, output, output.with_suffix(".source_links.json"))
    assert result["status"] == "passed", result["issues"]


@pytest.fixture(scope="module")
def audited_mixed_case(tmp_path_factory):
    folder = tmp_path_factory.mktemp("audited_block")
    source, output = folder / "source.ifc", folder / "block.gml"
    mapped_fixture(source, crs="EPSG:3763")
    model = ifcopenshell.open(str(source))
    add_annotation(model)
    add_annotation(model, model.by_type("IfcWall")[0])
    source = save_variant(model, source)
    convert(source, output, "engineering-block")
    return source, output


def test_independent_block_audit_accounts_for_annotations_and_mixed_geometry(audited_mixed_case):
    source, output = audited_mixed_case
    result = audit(source, output, output.with_suffix(".source_links.json"))
    assert result["status"] == "passed", result["issues"]
    building = result["buildings"][0]
    assert (building["physical_contributors"], building["annotation_only_omissions"], building["mixed_products"]) == (7, 1, 1)


@pytest.mark.parametrize("mutation,code", [
    ("omission", "omission_inventory"), ("extra_contributor", "contributor_inventory"),
    ("selected_rep", "representation_provenance"), ("excluded_rep", "excluded_representation_provenance"),
    ("vertices", "vertex_count"), ("bounds", "source_bounds_provenance"),
    ("corner", "xml_corner_coordinates"), ("reverse", "block_face_orientation"),
    ("face", "block_face_inventory"), ("frame", "xml_frame"), ("map", "engineering_provenance"),
    ("level", "selection_status"), ("status", "selection_status"), ("role", "contribution_role")])
def test_block_audit_rejects_corrupted_geometry_or_provenance(audited_mixed_case, tmp_path, mutation, code):
    source, output = audited_mixed_case
    links = json.loads(output.with_suffix(".source_links.json").read_text())
    root = ET.fromstring(output.read_bytes())
    group = links[0]
    if mutation == "omission":
        group["omitted"].pop()
    elif mutation == "extra_contributor":
        group["contributors"].append(copy.deepcopy(group["contributors"][0]))
    elif mutation == "selected_rep":
        group["contributors"][0]["representation_selection"]["selected_step_ids"] = []
    elif mutation == "excluded_rep":
        contributor = next(c for c in group["contributors"] if c["representation_selection"]["excluded_representations"])
        contributor["representation_selection"]["excluded_representations"] = []
    elif mutation == "vertices":
        group["contributors"][0]["vertex_count"] += 1
    elif mutation == "level":
        group["contributors"][0]["representation_selection"]["selection_level"] = "Body-FallBack"
    elif mutation == "status":
        group["omitted"][0]["representation_selection"]["status"] = "selected"
    elif mutation == "role":
        group["contributors"][0]["semantic_feature_preserved"] = True
    elif mutation == "bounds":
        group["source_bounds_m"][0][0] += 1
    elif mutation == "map":
        group["coordinate_provenance"]["operation_applied"] = True
    elif mutation == "frame":
        root.find(".//gml:Solid", NS).set("srsName", "urn:ogc:def:crs:EPSG::3763")
    elif mutation in ("corner", "reverse"):
        node = root.find(".//gml:posList", NS)
        points = np.array([float(v) for v in node.text.split()]).reshape(-1, 3)
        if mutation == "reverse":
            points = points[::-1]
        else:
            points[0, 0] += .01
            points[-1] = points[0]
        node.text = " ".join(str(v) for v in points.flat)
    elif mutation == "face":
        shell = root.find(".//gml:Shell", NS)
        shell.remove(shell[1])
        shell.append(copy.deepcopy(shell[0]))
    corrupted, sidecar = tmp_path / "bad.gml", tmp_path / "bad.links.json"
    corrupted.write_bytes(ET.tostring(root))
    sidecar.write_text(json.dumps(links))
    result = audit(source, corrupted, sidecar)
    assert result["status"] == "failed"
    assert code in {r["code"] for r in result["issues"]}
