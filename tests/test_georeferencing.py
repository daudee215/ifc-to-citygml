import ifcopenshell
import numpy as np
import pytest

from ifc_citygml.common import ROOT
from ifc_citygml.pipeline import convert
from ifc_citygml.georeferencing import prepare_profile
from ifc_citygml.common import load_profile
from scripts.generate_fixtures import make_fixture


def mapped_fixture(path, millimetres=False, crs="EPSG:7415"):
    # Write the mapped model to a fresh path. Immediate replacement of a newly
    # read IFC can race Windows file scanners and is unrelated to conversion.
    unmapped = path.with_name(path.stem + "_unmapped.ifc")
    make_fixture(unmapped, millimetres=millimetres)
    model = ifcopenshell.open(str(unmapped))
    metre = model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    target = model.create_entity("IfcProjectedCRS", Name=crs, MapUnit=metre)
    model.create_entity("IfcMapConversion", SourceCRS=model.by_type("IfcGeometricRepresentationContext")[0],
        TargetCRS=target, Eastings=120000.0, Northings=450000.0, OrthogonalHeight=220.0,
        XAxisAbscissa=0.0, XAxisOrdinate=1.0, Scale=0.001 if millimetres else 1.0)
    model.write(str(path))


@pytest.mark.parametrize("millimetres", [False, True])
def test_ifc_map_conversion_preserves_units_rotation_and_height(tmp_path, millimetres):
    if not (ROOT / "tools/val3dity/val3dity.exe").exists():
        pytest.skip("External validator unavailable")
    source, target = tmp_path / "mapped.ifc", tmp_path / "mapped.gml"
    mapped_fixture(source, millimetres)
    report = convert(source, target, ROOT / "config/map_conversion_profile.json")
    assert report["validation"]["independent_general_solid_validation"] == "passed"
    from ifc_citygml.external_validation import geometry_adapter
    geometry, _ = geometry_adapter(target.read_bytes())
    vertices = np.array(geometry["vertices"])
    np.testing.assert_allclose(vertices.min(axis=0), [119785, 450105, 233], atol=1e-7, rtol=0)
    np.testing.assert_allclose(vertices.max(axis=0), [119793, 450117, 239], atol=1e-7, rtol=0)
    assert report["profile"]["srs_name"] == "urn:ogc:def:crs:EPSG::7415"
    assert report["profile"]["georeferencing"]["accuracy_status"].startswith("metadata_transform_only")


def test_two_dimensional_crs_does_not_establish_height_datum(tmp_path):
    source = tmp_path / "mapped.ifc"
    mapped_fixture(source, crs="EPSG:32632")
    with pytest.raises(ValueError, match="height datum"):
        prepare_profile(load_profile(ROOT / "config/map_conversion_profile.json"), source)


def test_missing_map_conversion_is_not_identity_mapping(tmp_path):
    source = tmp_path / "unmapped.ifc"
    make_fixture(source)
    with pytest.raises(ValueError, match="exactly one"):
        prepare_profile(load_profile(ROOT / "config/map_conversion_profile.json"), source)
