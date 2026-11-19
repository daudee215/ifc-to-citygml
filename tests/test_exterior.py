from pathlib import Path
import json

from lxml import etree as ET
import numpy as np
import pytest

from ifc_citygml.common import ROOT
from ifc_citygml.citygml_writer import NS
from ifc_citygml.external_validation import geometry_adapter
from ifc_citygml.pipeline import convert
from ifc_citygml.validation import validate_document
from scripts.generate_fixtures import make_fixture


@pytest.mark.parametrize("millimetres,yaw,schema", [
    (False, 0, "IFC4"), (True, 0, "IFC4"), (False, 90, "IFC4"), (False, 0, "IFC2X3")])
def test_exterior_preserves_known_opening_and_surface_geometry(tmp_path, millimetres, yaw, schema):
    if not (ROOT / "tools/val3dity/val3dity.exe").exists():
        pytest.skip("Pinned external validator not installed")
    source, target = tmp_path / "building.ifc", tmp_path / "building.gml"
    make_fixture(source, millimetres, yaw, schema)
    report = convert(source, target, ROOT / "config/exterior_profile.json")
    assert report["status"] == "passed"
    assert report["validation"]["independent_surface_validation"] == "passed"
    assert report["validation"]["independent_general_solid_validation"] == "passed"
    building = report["extraction"]["buildings"][0]
    assert building["outer_shell_volume_m3"] == pytest.approx(575.9475, abs=1e-6)
    assert building["semantic_surface_areas_m2"]["RoofSurface"] == pytest.approx(96, abs=1e-6)
    assert building["semantic_surface_areas_m2"]["GroundSurface"] == pytest.approx(96, abs=1e-6)
    assert building["semantic_surface_areas_m2"]["DoorSurface"] == pytest.approx(2.1, abs=1e-6)
    assert len(building["removed_enclosed_cavities"]) == 1
    doors = [s for s in report["source_links"][0]["surface_links"] if s["target_class"] == "DoorSurface"]
    assert len(doors) == 1 and doors[0]["association"] == "host_wall_fillingSurface"
    target_geometry, adapter = geometry_adapter(target.read_bytes())
    assert adapter["lossless_exported_ring_check"]
    assert adapter["polygon_count"] == sum(len(c["triangles"]) for c in building["components"])
    assert target_geometry["CityObjects"]


def test_detailed_dangling_reference_is_rejected(tmp_path):
    if not (ROOT / "tools/val3dity/val3dity.exe").exists():
        pytest.skip("Pinned external validator not installed")
    source, target = tmp_path / "building.ifc", tmp_path / "building.gml"
    make_fixture(source)
    convert(source, target, ROOT / "config/exterior_profile.json")
    root = ET.fromstring(target.read_bytes())
    member = root.find("./core:cityObjectMember/bldg:Building/core:lod2MultiSurface//gml:CompositeSurface/gml:surfaceMember", NS)
    member.set("{http://www.w3.org/1999/xlink}href", "#missing_polygon")
    assert validate_document(ET.tostring(root))["status"] == "failed"


def test_external_adapter_retains_precision_and_orientation():
    source = ROOT / "results/citygml/building_m.gml"
    if not source.exists():
        pytest.skip("Run the documented block pilot first")
    adapted, evidence = geometry_adapter(source.read_bytes())
    assert evidence["lossless_exported_ring_check"]
    assert evidence["primitive_types"] == ["Solid"]
    assert len(adapted["vertices"]) == 8
    assert evidence["polygon_count"] == 6


def test_interior_detached_door_is_not_exported_as_exterior(tmp_path):
    import ifcopenshell
    import ifcopenshell.guid
    source, target = tmp_path / "building.ifc", tmp_path / "building.gml"
    make_fixture(source)
    model = ifcopenshell.open(str(source))
    door = model.by_type("IfcDoor")[0]
    position = model.create_entity("IfcAxis2Placement3D", Location=model.create_entity("IfcCartesianPoint", Coordinates=(4.0, 4.0, 0.3)))
    placement = model.create_entity("IfcLocalPlacement", PlacementRelTo=model.by_type("IfcBuildingStorey")[0].ObjectPlacement,
                                    RelativePlacement=position)
    interior = model.create_entity("IfcDoor", GlobalId=ifcopenshell.guid.new(), Name="Detached interior door", ObjectPlacement=placement,
        Representation=door.Representation, OverallHeight=2.1, OverallWidth=1.0)
    containment = model.by_type("IfcRelContainedInSpatialStructure")[0]
    containment.RelatedElements = (*containment.RelatedElements, interior)
    model.write(str(source))
    report = convert(source, target, ROOT / "config/exterior_profile.json")
    links = report["source_links"][0]
    assert len(links["removed_nested_positive_components"]) == 1
    assert all(link["ifc_global_id"] != interior.GlobalId for link in links["surface_links"])
