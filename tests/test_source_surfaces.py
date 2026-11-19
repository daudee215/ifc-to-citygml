import hashlib
import json

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.guid
from lxml import etree as ET
import numpy as np
import pytest

from ifc_citygml.common import ROOT
from ifc_citygml.citygml_writer import NS, tag
from ifc_citygml.pipeline import convert
from scripts.generate_fixtures import make_fixture

CON = "http://www.opengis.net/citygml/construction/3.0"
PROFILE = ROOT / "config/source_surfaces_profile.json"


@pytest.mark.parametrize("millimetres,yaw,schema", [(False, 0, "IFC4"), (True, 0, "IFC4"), (False, 90, "IFC4"), (False, 0, "IFC2X3")])
def test_source_tessellations_and_native_filling_relationships_roundtrip(tmp_path, millimetres, yaw, schema):
    source, output = tmp_path / "source.ifc", tmp_path / "source.gml"
    make_fixture(source, millimetres, yaw, schema)
    report = convert(source, output, PROFILE)
    assert report["status"] == "passed"
    assert report["validation"]["independent_surface_validation"] == "passed"
    assert report["extraction"]["serialization_fidelity"]["unmodified_source_coordinates"]
    assert report["extraction"]["serialization_fidelity"]["exact_transformed_float64_rings"]
    root = ET.fromstring(output.read_bytes())
    assert len(root.findall(".//bldg:BuildingConstructiveElement", NS)) == 6
    doors = root.findall(f".//{{{CON}}}Door")
    assert len(doors) == 1 and doors[0].getparent().tag == f"{{{CON}}}filling"
    model = ifcopenshell.open(str(source))
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    source_links = report["source_links"][0]["element_links"]
    assert len(source_links) == 7
    for link in source_links:
        shape = ifcopenshell.geom.create_shape(settings, model.by_guid(link["ifc_global_id"]))
        points = np.asarray(shape.geometry.verts).reshape(-1, 3)
        triangles = np.asarray(shape.geometry.faces).reshape(-1, 3)
        expected = points[triangles]
        feature = root.xpath("//*[@gml:id=$identifier]", namespaces=NS, identifier=link["citygml_id"])[0]
        positions = feature.findall("./core:lod2MultiSurface/gml:MultiSurface/gml:surfaceMember/gml:Polygon/gml:exterior/gml:LinearRing/gml:posList", NS)
        actual = np.array([np.array([float(v) for v in p.text.split()]).reshape(-1, 3)[:-1] for p in positions])
        np.testing.assert_array_equal(actual, expected)
        assert hashlib.sha256(np.ascontiguousarray(expected, dtype="<f8").tobytes()).hexdigest() == link["source_triangle_coordinate_sha256"]
    door_link = next(link for link in source_links if link["target_class"] == "Door")
    wall_link = next(link for link in source_links if link["ifc_global_id"] == door_link["host_global_id"])
    assert wall_link["opening_relations"][0]["filling_global_ids"] == [door_link["ifc_global_id"]]
    assert doors[0].getparent().getparent().get(tag("gml", "id")) == wall_link["citygml_id"]


def test_open_source_wall_is_preserved_without_generated_caps_and_orphan_door_is_explicit(tmp_path):
    source, output = tmp_path / "open.ifc", tmp_path / "open.gml"
    make_fixture(source)
    model = ifcopenshell.open(str(source))
    wall = next(w for w in model.by_type("IfcWall") if w.Name == "south")
    for void in list(wall.HasOpenings):
        model.remove(void)
    points = [model.create_entity("IfcCartesianPoint", Coordinates=p) for p in
              ((0.0, 0.0, 0.0), (12.0, 0.0, 0.0), (12.0, 0.0, 5.6), (0.0, 0.0, 5.6))]
    loop = model.create_entity("IfcPolyLoop", Polygon=points)
    bound = model.create_entity("IfcFaceOuterBound", Bound=loop, Orientation=True)
    face = model.create_entity("IfcFace", Bounds=[bound])
    faces = model.create_entity("IfcConnectedFaceSet", CfsFaces=[face])
    surface = model.create_entity("IfcFaceBasedSurfaceModel", FbsmFaces=[faces])
    representation = model.create_entity("IfcShapeRepresentation", ContextOfItems=model.by_type("IfcGeometricRepresentationContext")[0],
        RepresentationIdentifier="Body", RepresentationType="SurfaceModel", Items=[surface])
    wall.Representation = model.create_entity("IfcProductDefinitionShape", Representations=[representation])
    model.write(str(source))
    report = convert(source, output, PROFILE)
    assert report["validation"]["independent_surface_validation"] == "passed"
    assert report["validation"]["independent_general_solid_validation"] == "failed"
    elements = report["extraction"]["buildings"][0]["elements"]
    source_wall = next(e for e in elements if e["ifc_global_id"] == wall.GlobalId)
    assert len(source_wall["triangles"]) == 2  # Only the input plane; no cap or guessed volume.
    links = report["source_links"][0]["element_links"]
    door = next(e for e in links if e["target_class"] == "Door")
    assert door["host_global_id"] is None
    assert door["association"].startswith("standalone_filling_no_selected_host")
    root = ET.fromstring(output.read_bytes())
    node = root.find(f"./core:cityObjectMember/{{{CON}}}Door", NS)
    assert node is not None


def test_source_native_properties_and_known_load_bearing_flag_are_retained(tmp_path):
    source, output = tmp_path / "properties.ifc", tmp_path / "properties.gml"
    make_fixture(source)
    model = ifcopenshell.open(str(source))
    wall = model.by_type("IfcWall")[0]
    prop = model.create_entity("IfcPropertySingleValue", Name="LoadBearing", NominalValue=model.create_entity("IfcBoolean", False))
    pset = model.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), Name="Pset_WallCommon", HasProperties=[prop])
    model.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[wall], RelatingPropertyDefinition=pset)
    model.write(str(source))
    report = convert(source, output, PROFILE)
    link = next(e for e in report["source_links"][0]["element_links"] if e["ifc_global_id"] == wall.GlobalId)
    assert link["source_property_sets"]["Pset_WallCommon"]["LoadBearing"] is False
    root = ET.fromstring(output.read_bytes())
    node = root.xpath("//*[@gml:id=$identifier]", namespaces=NS, identifier=link["citygml_id"])[0]
    assert link["load_bearing"] is False
    # IFC LoadBearing does not by itself establish CityGML's stricter definition
    # of collapse-critical structural membership.
    assert node.find(f"{{{CON}}}isStructuralElement") is None


def test_window_uses_native_filling_class_and_source_wall_host(tmp_path):
    source, output = tmp_path / "window.ifc", tmp_path / "window.gml"
    make_fixture(source)
    model = ifcopenshell.open(str(source))
    door = model.by_type("IfcDoor")[0]
    old_opening = model.by_type("IfcOpeningElement")[0]
    wall = next(w for w in model.by_type("IfcWall") if w.Name == "south")
    def placement(parent, xyz):
        axis = model.create_entity("IfcAxis2Placement3D", Location=model.create_entity("IfcCartesianPoint", Coordinates=xyz))
        return model.create_entity("IfcLocalPlacement", PlacementRelTo=parent, RelativePlacement=axis)
    opening = model.create_entity("IfcOpeningElement", GlobalId=ifcopenshell.guid.new(), Name="Fixture window opening",
        ObjectPlacement=placement(wall.ObjectPlacement, (3.0, 0.0, 0.0)), Representation=old_opening.Representation)
    window = model.create_entity("IfcWindow", GlobalId=ifcopenshell.guid.new(), Name="Full-height fixture window",
        ObjectPlacement=placement(model.by_type("IfcBuildingStorey")[0].ObjectPlacement, (3.0, 0.025, 0.2)),
        Representation=door.Representation, OverallHeight=2.1, OverallWidth=1.0)
    model.create_entity("IfcRelVoidsElement", GlobalId=ifcopenshell.guid.new(), RelatingBuildingElement=wall, RelatedOpeningElement=opening)
    model.create_entity("IfcRelFillsElement", GlobalId=ifcopenshell.guid.new(), RelatingOpeningElement=opening, RelatedBuildingElement=window)
    container = model.by_type("IfcRelContainedInSpatialStructure")[0]
    container.RelatedElements = (*container.RelatedElements, window)
    model.write(str(source))
    report = convert(source, output, PROFILE)
    root = ET.fromstring(output.read_bytes())
    node = root.find(f".//{{{CON}}}Window")
    assert node is not None and node.getparent().tag == f"{{{CON}}}filling"
    link = next(e for e in report["source_links"][0]["element_links"] if e["target_class"] == "Window")
    assert link["host_global_id"] == wall.GlobalId
    assert node.find(f"{{{CON}}}class").text == "IfcWindow"
