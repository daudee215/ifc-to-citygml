import hashlib
import json

import ifcopenshell
import ifcopenshell.geom
from lxml import etree as ET
import numpy as np
import pytest

from ifc_citygml.common import load_profile
from ifc_citygml.georeferencing import prepare_profile
from ifc_citygml.pipeline import convert
from ifc_citygml.citygml_writer import NS
from tests.test_georeferencing import mapped_fixture
from scripts.semantic_audit import audit


@pytest.mark.parametrize("millimetres", [False, True])
@pytest.mark.parametrize("profile", ["engineering-block", "engineering-exterior", "engineering-source"])
def test_explicit_engineering_frame_keeps_units_local_coordinates_and_complete_metadata(tmp_path, profile, millimetres):
    source, target = tmp_path / "mapped.ifc", tmp_path / "engineering.gml"
    mapped_fixture(source, millimetres, "EPSG:3763")
    original_bytes = source.read_bytes()
    model = ifcopenshell.open(str(source))
    operation = model.by_type("IfcMapConversion")[0]
    report = convert(source, target, profile)
    assert source.read_bytes() == original_bytes
    assert report["status"] == "passed"
    policy = report["profile"]["georeferencing"]
    assert policy["operation_applied"] is False
    assert policy["original_coordinate_operations"] == json.loads(json.dumps([operation.get_info(recursive=True)]))
    assert policy["source_input_sha256"] == hashlib.sha256(original_bytes).hexdigest()
    assert "geographic position not established" in policy["accuracy_status"]
    assert all(link["coordinate_provenance"] == policy for link in report["source_links"])
    root = ET.fromstring(target.read_bytes())
    assert "has not been applied" in root.find("gml:description", NS).text
    assert all(node.get("srsName") == "urn:ifc-citygml:crs:local-engineering-metres" for node in root.xpath('//*[@srsName]'))
    assert any("Engineering coordinates only" in w for w in report["validation"]["quality_warnings"])
    points = np.array([float(v) for node in root.findall(".//gml:posList", NS) for v in node.text.split()]).reshape(-1, 3)
    np.testing.assert_allclose(points.min(axis=0), [105, 207, 13], atol=1e-10, rtol=0)
    np.testing.assert_allclose(points.max(axis=0), [117, 215, 19], atol=1e-10, rtol=0)
    if profile == "engineering-source":
        assert report["extraction"]["serialization_fidelity"]["unmodified_source_coordinates"]
        settings = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)
        settings.set("convert-back-units", False)
        for link in report["source_links"][0]["element_links"]:
            shape = ifcopenshell.geom.create_shape(settings, model.by_guid(link["ifc_global_id"]))
            vertices = np.array(shape.geometry.verts).reshape(-1, 3)
            faces = np.array(shape.geometry.faces).reshape(-1, 3)
            node = root.xpath('//*[@gml:id=$id]', namespaces=NS, id=link["citygml_id"])[0]
            positions = node.findall("./core:lod2MultiSurface/gml:MultiSurface/gml:surfaceMember/gml:Polygon/gml:exterior/gml:LinearRing/gml:posList", NS)
            rings = np.array([np.array([float(v) for v in p.text.split()]).reshape(-1, 3)[:-1] for p in positions])
            np.testing.assert_array_equal(rings, vertices[faces])


def test_opt_in_does_not_weaken_default_or_geographic_profiles(tmp_path):
    source = tmp_path / "mapped.ifc"
    mapped_fixture(source, crs="EPSG:3763")
    for profile in ("block", "exterior", "source"):
        with pytest.raises(ValueError, match="IfcMapConversion"):
            convert(source, tmp_path / (profile + ".gml"), profile)
    with pytest.raises(ValueError, match="height datum"):
        convert(source, tmp_path / "map.gml", "map")


@pytest.mark.parametrize("corruption", [None, "drop_metadata", "claim_applied", "change_offset"])
def test_source_audit_checks_retained_original_map_metadata(tmp_path, corruption):
    source, target = tmp_path / "mapped.ifc", tmp_path / "engineering.gml"
    mapped_fixture(source, crs="EPSG:3763")
    convert(source, target, "engineering-source")
    sidecar = target.with_suffix(".source_links.json")
    links = json.loads(sidecar.read_text())
    if corruption == "drop_metadata":
        del links[0]["coordinate_provenance"]
    elif corruption == "claim_applied":
        links[0]["coordinate_provenance"]["operation_applied"] = True
    elif corruption == "change_offset":
        links[0]["coordinate_provenance"]["original_coordinate_operations"][0]["Eastings"] += 1
    sidecar.write_text(json.dumps(links))
    result = audit(source, target, sidecar)
    assert result["status"] == ("passed" if corruption is None else "failed"), result["issues"]


def test_non_identity_world_context_is_rejected_until_placement_is_validated(tmp_path):
    source = tmp_path / "mapped.ifc"
    mapped_fixture(source, crs="EPSG:3763")
    model = ifcopenshell.open(str(source))
    model.by_type("IfcGeometricRepresentationContext", include_subtypes=False)[0].WorldCoordinateSystem.Location.Coordinates = (1., 0., 0.)
    model.write(str(source))
    with pytest.raises(ValueError, match="WorldCoordinateSystem"):
        prepare_profile(load_profile("engineering-source"), source)


@pytest.mark.parametrize("change", ["translation", "crs"])
def test_engineering_policy_rejects_unlabelled_crs_or_extra_transforms(tmp_path, change):
    profile = load_profile("engineering-source")
    if change == "translation":
        profile["transform"]["translation_m"] = [100, 0, 0]
    else:
        profile["srs_name"] = "urn:ifc-citygml:crs:misleading-map-frame"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(profile))
    with pytest.raises(ValueError):
        load_profile(path)
