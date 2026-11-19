"""Generate actual IFC building fixtures from known analytic dimensions.

Generated fixtures are project-authored synthetic data, not Torino buildings.
Geometry spans 12 x 8 x 6 m, with site/building/storey placement offsets.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import uuid

import ifcopenshell
import ifcopenshell.guid

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_NAMESPACE = uuid.UUID("5ce1ad25-7d6d-46d7-a28d-df6d993004c8")


def make_fixture(path: Path, millimetres: bool = False, yaw: float = 0,
                 schema: str = "IFC4") -> dict:
    model = ifcopenshell.file(schema=schema)
    factor = 1000.0 if millimetres else 1.0

    def entity(name, **kwargs):
        return model.create_entity(name, **kwargs)

    def point(values):
        return entity("IfcCartesianPoint", Coordinates=tuple(float(v) * factor for v in values))

    def direction(values):
        return entity("IfcDirection", DirectionRatios=tuple(float(v) for v in values))

    def axis(values=(0, 0, 0), angle=0):
        return entity("IfcAxis2Placement3D", Location=point(values), Axis=direction((0, 0, 1)),
                      RefDirection=direction((math.cos(math.radians(angle)), math.sin(math.radians(angle)), 0)))

    def place(parent=None, offset=(0, 0, 0), angle=0):
        return entity("IfcLocalPlacement", PlacementRelTo=parent, RelativePlacement=axis(offset, angle))

    organisation = entity("IfcOrganization", Name="IFC-to-CityGML research fixtures")
    person = entity("IfcPerson", FamilyName="Synthetic")
    actor = entity("IfcPersonAndOrganization", ThePerson=person, TheOrganization=organisation)
    application = entity("IfcApplication", ApplicationDeveloper=organisation, Version="0.1.0",
                         ApplicationFullName="IFC-to-CityGML fixture generator", ApplicationIdentifier="IFCCG")
    history = entity("IfcOwnerHistory", OwningUser=actor, OwningApplication=application,
                     ChangeAction="ADDED", LastModifiedDate=1735689600, CreationDate=1735689600)

    def rooted(name, key, **kwargs):
        guid = ifcopenshell.guid.compress(uuid.uuid5(FIXTURE_NAMESPACE, key).hex)
        return entity(name, GlobalId=guid, OwnerHistory=history, **kwargs)

    context = entity("IfcGeometricRepresentationContext", ContextIdentifier="Model", ContextType="Model",
                     CoordinateSpaceDimension=3, Precision=1e-6 * factor, WorldCoordinateSystem=axis())
    unit = entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE", Prefix="MILLI" if millimetres else None)
    units = entity("IfcUnitAssignment", Units=[unit])
    project = rooted("IfcProject", "project", Name="Synthetic IFC conversion pilot", UnitsInContext=units,
                     RepresentationContexts=[context])
    site = rooted("IfcSite", "site", Name="Local engineering fixture", CompositionType="ELEMENT",
                  ObjectPlacement=place(offset=(100, 200, 10), angle=yaw))
    building = rooted("IfcBuilding", "building", Name="Synthetic 12 x 8 x 6 m building", CompositionType="ELEMENT",
                      ObjectPlacement=place(site.ObjectPlacement, (5, 7, 1)))
    storey = rooted("IfcBuildingStorey", "storey", Name="Fixture storey", CompositionType="ELEMENT", Elevation=2 * factor,
                    ObjectPlacement=place(building.ObjectPlacement, (0, 0, 2)))
    for key, parent, child in (("project_site", project, site), ("site_building", site, building),
                               ("building_storey", building, storey)):
        rooted("IfcRelAggregates", key, RelatingObject=parent, RelatedObjects=[child])

    def body(width, depth, height):
        profile_axis = entity("IfcAxis2Placement2D", Location=point((width / 2, depth / 2)))
        profile = entity("IfcRectangleProfileDef", ProfileType="AREA", Position=profile_axis,
                         XDim=width * factor, YDim=depth * factor)
        solid = entity("IfcExtrudedAreaSolid", SweptArea=profile, Position=axis(),
                       ExtrudedDirection=direction((0, 0, 1)), Depth=height * factor)
        rep = entity("IfcShapeRepresentation", ContextOfItems=context, RepresentationIdentifier="Body",
                     RepresentationType="SweptSolid", Items=[solid])
        return entity("IfcProductDefinitionShape", Representations=[rep])

    elements = []
    dimensions = [
        ("floor", "IfcSlab", (12, 8, 0.2), (0, 0, 0)),
        ("roof", "IfcSlab", (12, 8, 0.2), (0, 0, 5.8)),
        ("south", "IfcWall", (12, 0.2, 5.6), (0, 0, 0.2)),
        ("north", "IfcWall", (12, 0.2, 5.6), (0, 7.8, 0.2)),
        ("west", "IfcWall", (0.2, 7.6, 5.6), (0, 0.2, 0.2)),
        ("east", "IfcWall", (0.2, 7.6, 5.6), (11.8, 0.2, 0.2)),
    ]
    for key, kind, dims, offset in dimensions:
        kwargs = {"Name": key, "ObjectPlacement": place(storey.ObjectPlacement, offset), "Representation": body(*dims)}
        if kind == "IfcSlab":
            kwargs["PredefinedType"] = "BASESLAB" if key == "floor" else "ROOF"
        elements.append(rooted(kind, key, **kwargs))
    door = rooted("IfcDoor", "door", Name="Exterior fixture door", ObjectPlacement=place(storey.ObjectPlacement, (1, 0.025, 0.2)),
                  Representation=body(1, 0.15, 2.1), OverallHeight=2.1 * factor, OverallWidth=1 * factor)
    opening = rooted("IfcOpeningElement", "opening", Name="Door void", ObjectPlacement=place(elements[2].ObjectPlacement, (1, 0, 0)),
                     Representation=body(1, 0.2, 2.1))
    rooted("IfcRelVoidsElement", "wall_void", RelatingBuildingElement=elements[2], RelatedOpeningElement=opening)
    rooted("IfcRelFillsElement", "void_door", RelatingOpeningElement=opening, RelatedBuildingElement=door)
    rooted("IfcRelContainedInSpatialStructure", "containment", RelatedElements=[*elements, door], RelatingStructure=storey)
    model.header.file_name.name = path.name
    model.header.file_name.time_stamp = "2026-11-02T00:00:00"
    model.header.file_name.author = ("IFC-to-CityGML research project",)
    model.header.file_name.organization = ("Synthetic fixtures",)
    path.parent.mkdir(parents=True, exist_ok=True)
    model.write(str(path))
    # Independent analytic dimensions and known nested offsets, not extracted mesh values.
    if yaw == 0:
        bounds = [[105.0, 207.0, 13.0], [117.0, 215.0, 19.0]]
    elif yaw == 90:
        bounds = [[85.0, 205.0, 13.0], [93.0, 217.0, 19.0]]
    else:
        bounds = None
    return {"provenance_type": "synthetic_fixture", "license": "CC0-1.0",
            "ifc_schema": schema, "length_unit": "millimetre" if millimetres else "metre",
            "building_dimensions_m": [12.0, 8.0, 6.0], "expected_ifc_world_bounds_m": bounds,
            "expected_bounding_volume_m3": 576.0, "expected_door_count": 1,
            "site_yaw_degrees": yaw, "not_a_real_torino_building": True}


def main():
    folder = ROOT / "data" / "raw" / "fixtures"
    manifest = []
    for name, millimetres, yaw, schema in (
        ("building_m", False, 0, "IFC4"), ("building_mm", True, 0, "IFC4"),
        ("building_rotated", False, 90, "IFC4"), ("building_ifc2x3", False, 0, "IFC2X3"),
    ):
        path = folder / (name + ".ifc")
        expected = make_fixture(path, millimetres, yaw, schema)
        path.with_suffix(".expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
        manifest.append({"path": path.relative_to(ROOT).as_posix(), **expected})
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(manifest)} IFC building fixtures in {folder}")


if __name__ == "__main__":
    main()
