from __future__ import annotations

import json

import ifcopenshell
import ifcopenshell.validate
from lxml import etree as ET
import numpy as np
import pytest

from scripts.generate_fixtures import make_fixture
from ifc_citygml.common import load_profile
from ifc_citygml.citygml_writer import NS, tag
from ifc_citygml.pipeline import ConversionFailure, convert
from ifc_citygml.validation import validate_document
from ifc_citygml.cli import main


@pytest.mark.parametrize("millimetres,yaw,schema", [
    (False, 0, "IFC4"), (True, 0, "IFC4"), (False, 90, "IFC4"), (False, 0, "IFC2X3"),
])
def test_known_ifc_building_converts_with_correct_units_and_placements(tmp_path, millimetres, yaw, schema):
    source, target = tmp_path / "input.ifc", tmp_path / "output.gml"
    expected = make_fixture(source, millimetres, yaw, schema)
    model = ifcopenshell.open(str(source))
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(model, logger, express_rules=True)
    assert not logger.statements, str(logger.statements)
    report = convert(source, target)
    assert report["status"] == "passed"
    assert report["validation"]["schema_valid"]
    solid = report["validation"]["geometry"][0]
    assert solid["volume_m3"] == pytest.approx(576, abs=1e-7)
    np.testing.assert_allclose(solid["bounds_m"], expected["expected_ifc_world_bounds_m"], atol=1e-7, rtol=0)
    assert report["extraction"]["length_unit_to_metre"] == (0.001 if millimetres else 1)
    assert len(report["source_links"][0]["contributors"]) == 7
    doors = [e for e in report["source_links"][0]["contributors"] if e["ifc_class"] == "IfcDoor"]
    assert len(doors) == 1 and doors[0]["semantic_feature_preserved"] is False
    assert "openings" in report["source_links"][0]["information_loss"]


@pytest.fixture
def pilot_gml(tmp_path):
    source, target = tmp_path / "input.ifc", tmp_path / "output.gml"
    make_fixture(source)
    convert(source, target)
    return target.read_bytes()


def test_output_is_deterministic(tmp_path):
    source = tmp_path / "input.ifc"
    make_fixture(source)
    first = convert(source, tmp_path / "one.gml")
    second = convert(source, tmp_path / "two.gml")
    assert first["output_sha256"] == second["output_sha256"]


def test_output_transform_is_applied_once_and_volume_scales_cubically(tmp_path):
    source, config = tmp_path / "input.ifc", tmp_path / "profile.json"
    make_fixture(source, millimetres=True)
    profile = load_profile()
    profile["coordinate_mode"] = "synthetic_transform"
    profile["srs_name"] = "urn:ifc-citygml:crs:synthetic-test-metres"
    profile["transform"] = {"translation_m": [395000, 4980000, 220], "yaw_degrees": 90, "scale": 2}
    config.write_text(json.dumps(profile), encoding="utf-8")
    report = convert(source, tmp_path / "output.gml", config)
    solid = report["validation"]["geometry"][0]
    np.testing.assert_allclose(solid["bounds_m"], [[394570, 4980210, 246], [394586, 4980234, 258]], atol=1e-7, rtol=0)
    assert solid["volume_m3"] == pytest.approx(4608, abs=1e-5)


@pytest.mark.parametrize("mutation", ["reverse_face", "missing_face", "nan", "bowtie", "duplicate_id", "wrong_namespace", "unresolved_reference"])
def test_damaged_gml_is_rejected(pilot_gml, mutation):
    root = ET.fromstring(pilot_gml)
    positions = root.find(".//gml:posList", NS)
    tokens = positions.text.split()
    if mutation == "reverse_face":
        coords = np.array([float(v) for v in tokens]).reshape(-1, 3)[::-1]
        positions.text = " ".join(str(v) for v in coords.flat)
    elif mutation == "missing_face":
        member = root.find(".//gml:surfaceMember", NS)
        member.getparent().remove(member)
    elif mutation == "nan":
        tokens[0] = "NaN"
        positions.text = " ".join(tokens)
    elif mutation == "bowtie":
        coords = np.array([float(v) for v in tokens]).reshape(-1, 3)
        positions.text = " ".join(str(v) for v in coords[[0, 2, 1, 3, 0]].flat)
    elif mutation == "duplicate_id":
        root.find(".//gml:Polygon", NS).set(tag("gml", "id"), root.get(tag("gml", "id")))
    elif mutation == "wrong_namespace":
        root.find(".//bldg:Building", NS).tag = "{http://www.opengis.net/citygml/building/2.0}Building"
    else:
        root.find(".//gml:surfaceMember", NS).set("{http://www.w3.org/1999/xlink}href", "#absent")
    assert validate_document(ET.tostring(root))["status"] == "failed"


def test_geometry_failure_does_not_write_apparently_valid_output(tmp_path):
    source, target = tmp_path / "input.ifc", tmp_path / "output.gml"
    make_fixture(source)
    model = ifcopenshell.open(str(source))
    # An impossible rectangle creates a genuine geometry extraction failure.
    for rectangle in model.by_type("IfcRectangleProfileDef"):
        rectangle.XDim = 0.0
    model.write(str(source))
    with pytest.raises(ConversionFailure):
        convert(source, target)
    assert not target.exists()
    report = json.loads(target.with_suffix(".report.json").read_text())
    assert report["status"] == "failed" and report["output_written"] is False
    assert report["extraction"]["failures"]


def test_map_conversion_requires_implemented_georeferencing(tmp_path):
    source = tmp_path / "mapped.ifc"
    make_fixture(source)
    model = ifcopenshell.open(str(source))
    context = model.by_type("IfcGeometricRepresentationContext")[0]
    crs = model.create_entity("IfcProjectedCRS", Name="EPSG:25832")
    model.create_entity("IfcMapConversion", SourceCRS=context, TargetCRS=crs,
                        Eastings=395000.0, Northings=4980000.0, OrthogonalHeight=220.0)
    model.write(str(source))
    with pytest.raises(ValueError, match="IfcMapConversion"):
        convert(source, tmp_path / "output.gml")


def test_pilot_refuses_unverified_epsg_labelling(tmp_path):
    profile = load_profile()
    profile["srs_name"] = "urn:ogc:def:crs:EPSG::25832"
    config = tmp_path / "profile.json"
    config.write_text(json.dumps(profile))
    with pytest.raises(ValueError, match="unverified EPSG"):
        load_profile(config)


def test_cli_reports_invalid_xml_as_nonzero(tmp_path):
    source, report = tmp_path / "broken.gml", tmp_path / "validation.json"
    source.write_text("<broken>")
    assert main(["validate", str(source), "--report", str(report)]) == 2
    assert json.loads(report.read_text())["status"] == "failed"


def test_input_cannot_be_overwritten(tmp_path):
    source = tmp_path / "input.ifc"
    make_fixture(source)
    original = source.read_bytes()
    with pytest.raises(ValueError, match="differ"):
        convert(source, source)
    assert source.read_bytes() == original
