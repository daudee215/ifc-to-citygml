import json

from lxml import etree as ET
import pytest
import ifcopenshell
import ifcopenshell.validate

from ifc_citygml.pipeline import convert
from scripts.generate_semantic_cases import make_case
from scripts.semantic_audit import NS, audit


@pytest.mark.parametrize("schema", ["IFC4", "IFC2X3"])
def test_independently_authored_ifc_passes_schema_attribute_validation(tmp_path, schema):
    source = tmp_path / (schema + ".ifc")
    make_case(source, schema)
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(ifcopenshell.open(str(source)), logger)
    assert logger.statements == []


@pytest.fixture(scope="module")
def specimen(tmp_path_factory):
    folder = tmp_path_factory.mktemp("semantic_audit")
    source, output = folder / "specimen.ifc", folder / "specimen.gml"
    expected = make_case(source)
    convert(source, output, "source")
    return source, output, expected


def test_authored_expectations_cover_structural_classes_hosts_and_omissions(specimen):
    source, output, expected = specimen
    result = audit(source, output, output.with_suffix(".source_links.json"), source.with_suffix(".expected.json"))
    assert result["status"] == "passed", result["issues"]
    assert len(expected["features"]) == result["selected_features"] == 19
    assert result["expected_features"] == result["exported_features"] == 19
    assert result["by_target_class"] == {"BuildingConstructiveElement": 14, "Door": 3, "Window": 2}
    assert len(result["omissions"]) == 3
    assert result["by_association"]["source_host_construction_filling"] == 2
    assert result["by_association"]["standalone_filling_no_selected_host; building membership retained in provenance"] == 3


@pytest.mark.parametrize("mutation,expected_code", [
    ("xml_class", "xml_target_class"), ("class_code", "source_class_code"),
    ("host", "host_association"), ("geometry", "source_triangle_coordinates_or_order"),
    ("property", "property_provenance"), ("opening", "opening_provenance"),
    ("omission", "omission_inventory_mismatch"), ("omission_identity", "omission_source_identity"),
    ("missing_link", "selected_inventory_mismatch"), ("extra_xml", "unlinked_xml_features"),
    ("structural_inference", "unsupported_structural_inference"),
    ("source_identity", "source_identity"), ("building", "xml_building_identity"),
])
def test_audit_rejects_deliberately_corrupted_outputs(specimen, tmp_path, mutation, expected_code):
    source, output, _ = specimen
    root = ET.fromstring(output.read_bytes())
    links = json.loads(output.with_suffix(".source_links.json").read_text())
    wall = next(e for b in links for e in b["element_links"] if e["name"] == "wall")
    node = root.xpath("//*[@gml:id=$id]", namespaces=NS, id=wall["citygml_id"])[0]
    if mutation == "xml_class":
        node.tag = "{" + NS["con"] + "}Door"
    elif mutation == "class_code":
        node.find("bldg:class", NS).text = "IfcBeam"
    elif mutation == "host":
        door = root.find(".//con:filling/con:Door", NS)
        wrong_host = root.findall(".//bldg:BuildingConstructiveElement", NS)[1]
        wrong_host.append(door.getparent())
    elif mutation == "geometry":
        pos = node.find(".//gml:posList", NS)
        coordinates = pos.text.split()
        coordinates[2] = str(float(coordinates[2]) + .01)
        pos.text = " ".join(coordinates)
    elif mutation == "property":
        wall["source_property_sets"]["Pset_WallCommon"]["LoadBearing"] = True
    elif mutation == "opening":
        wall["opening_relations"] = []
    elif mutation == "omission":
        next(b for b in links if b["omitted"])["omitted"].pop()
    elif mutation == "omission_identity":
        next(b for b in links if b["omitted"])["omitted"][0]["ifc_class"] = "IfcDoor"
    elif mutation == "missing_link":
        group = next(b for b in links if wall in b["element_links"])
        group["element_links"].remove(wall)
    elif mutation == "extra_xml":
        extra = ET.SubElement(root, "{" + NS["con"] + "}Window")
        extra.set("{" + NS["gml"] + "}id", "unexpected_window")
    elif mutation == "structural_inference":
        ET.SubElement(node, "{" + NS["con"] + "}isStructuralElement").text = "true"
    elif mutation == "source_identity":
        wall["step_id"] += 1
    elif mutation == "building":
        root.find(".//bldg:Building", NS).tag = "{" + NS["con"] + "}Door"
    corrupted, sidecar = tmp_path / "bad.gml", tmp_path / "bad.source_links.json"
    corrupted.write_bytes(ET.tostring(root))
    sidecar.write_text(json.dumps(links))
    result = audit(source, corrupted, sidecar)
    assert result["status"] == "failed"
    assert expected_code in {issue["code"] for issue in result["issues"]}


def test_changed_authored_expectations_do_not_pass(specimen, tmp_path):
    source, output, expected = specimen
    expected["features"]["beam"]["target_class"] = "Door"
    changed = tmp_path / "wrong.expected.json"
    changed.write_text(json.dumps(expected))
    result = audit(source, output, output.with_suffix(".source_links.json"), changed)
    assert "authored_fixture_expectations" in {issue["code"] for issue in result["issues"]}
