"""Author semantic specimens independently of the converter/original fixtures."""
import json
from pathlib import Path
import uuid

import ifcopenshell
import ifcopenshell.guid

NAMESPACE = uuid.UUID("ab402017-1286-46ca-83d1-40157619f06e")


def make_case(path: Path, schema="IFC4"):
    model = ifcopenshell.file(schema=schema)
    def create(kind, **attrs):
        return model.create_entity(kind, **attrs)
    def guid(key):
        return ifcopenshell.guid.compress(uuid.uuid5(NAMESPACE, key).hex)
    org = create("IfcOrganization", Name="Project-authored semantic evaluation")
    person = create("IfcPerson", FamilyName="Controlled specimen")
    actor = create("IfcPersonAndOrganization", ThePerson=person, TheOrganization=org)
    app = create("IfcApplication", ApplicationDeveloper=org, Version="1.0", ApplicationFullName="Independent semantic specimen author", ApplicationIdentifier="SEMTEST")
    history = create("IfcOwnerHistory", OwningUser=actor, OwningApplication=app, ChangeAction="ADDED", CreationDate=1793577600)
    def rooted(kind, key, **attrs):
        return create(kind, GlobalId=guid(key), OwnerHistory=history, **attrs)
    def point(xyz):
        return create("IfcCartesianPoint", Coordinates=tuple(float(x) for x in xyz))
    def axis(xyz=(0, 0, 0)):
        return create("IfcAxis2Placement3D", Location=point(xyz))
    def placement(xyz, parent=None):
        return create("IfcLocalPlacement", PlacementRelTo=parent, RelativePlacement=axis(xyz))
    context = create("IfcGeometricRepresentationContext", ContextType="Model", CoordinateSpaceDimension=3, Precision=1e-7, WorldCoordinateSystem=axis())
    units = create("IfcUnitAssignment", Units=[create("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")])
    project = rooted("IfcProject", "project", Name="Semantic specimens, not a real building", RepresentationContexts=[context], UnitsInContext=units)
    buildings = [rooted("IfcBuilding", f"building_{i}", Name=f"Specimen building {i}", CompositionType="ELEMENT", ObjectPlacement=placement((i * 100, 0, 0))) for i in (0, 1)]
    rooted("IfcRelAggregates", "buildings", RelatingObject=project, RelatedObjects=buildings)
    contained = [[], []]
    features, omissions, entities = {}, [], {}
    def body(dims=(1, 1, 1)):
        width, depth, height = map(float, dims)
        profile = create("IfcRectangleProfileDef", ProfileType="AREA", XDim=width, YDim=depth,
                         Position=create("IfcAxis2Placement2D", Location=point((width / 2, depth / 2))))
        solid = create("IfcExtrudedAreaSolid", SweptArea=profile, Position=axis(),
                       ExtrudedDirection=create("IfcDirection", DirectionRatios=(0., 0., 1.)), Depth=height)
        shape = create("IfcShapeRepresentation", ContextOfItems=context, RepresentationIdentifier="Body", RepresentationType="SweptSolid", Items=[solid])
        return create("IfcProductDefinitionShape", Representations=[shape])
    def element(name, kind, target, building=0, represented=True, host=None, dims=(1, 1, 1), xyz=None):
        attrs = dict(Name=name, ObjectPlacement=placement(xyz or (len(contained[building]) * 5, 0, 0), buildings[building].ObjectPlacement))
        if represented:
            attrs["Representation"] = body(dims)
        if kind in {"IfcRoof", "IfcStair"} and schema == "IFC2X3":
            attrs["ShapeType"] = "NOTDEFINED"
        if kind in {"IfcFooting", "IfcPile"}:
            attrs["PredefinedType"] = "NOTDEFINED"
        entity = rooted(kind, name, **attrs)
        entities[name] = entity
        contained[building].append(entity)
        if target is None or not represented:
            omissions.append({"ifc_global_id": entity.GlobalId, "reason": "Outside declared constructive/filling profile" if target is None else "No source representation"})
        else:
            association = "building_constructive_element" if target == "BuildingConstructiveElement" else (
                "source_host_construction_filling" if host and host[1] else "standalone_filling_no_selected_host; building membership retained in provenance")
            features[name] = {"ifc_class": kind, "target_class": target, "association": association,
                              "host_global_id": guid(host[0]) if host else None}
        return entity
    # Expected target classes are authored explicitly; no production rule is imported.
    specimens = [("wall", "IfcWall"), ("slab", "IfcSlab"), ("roof", "IfcRoof"), ("beam", "IfcBeam"),
                 ("column", "IfcColumn"), ("member", "IfcMember"), ("plate", "IfcPlate"), ("footing", "IfcFooting"),
                 ("pile", "IfcPile"), ("stair", "IfcStair"), ("flight", "IfcStairFlight"), ("curtain", "IfcCurtainWall"),
                 ("subclass", "IfcWallStandardCase")]
    for name, kind in specimens:
        element(name, kind, "BuildingConstructiveElement", dims=(4, .3, 3) if name == "wall" else (1, 1, 1))
    element("unrepresented_host", "IfcWall", "BuildingConstructiveElement", represented=False)
    element("proxy_host", "IfcBuildingElementProxy", None)
    element("furniture", "IfcFurnishingElement", None)
    element("door_hosted", "IfcDoor", "Door", host=("wall", True), dims=(.8, .1, 2), xyz=(.5, .1, 0))
    element("window_hosted", "IfcWindow", "Window", host=("wall", True), dims=(.6, .1, .6), xyz=(2., .1, 1.))
    element("door_orphan", "IfcDoor", "Door", building=1)
    element("window_proxy_host", "IfcWindow", "Window", host=("proxy_host", False))
    element("door_unrepresented_host", "IfcDoor", "Door", host=("unrepresented_host", False))
    element("second_building_wall", "IfcWall", "BuildingConstructiveElement", building=1)
    for name, host, opening_xyz, dims in (("door_hosted", "wall", (.5, 0, 0), (.8, .3, 2)),
            ("window_hosted", "wall", (2, 0, 1), (.6, .3, .6)),
            ("window_proxy_host", "proxy_host", (0, 0, 0), (.2, .2, .2)),
            ("door_unrepresented_host", "unrepresented_host", (0, 0, 0), (.2, .2, .2))):
        opening = rooted("IfcOpeningElement", name + "_opening", Name=name + " void",
                         ObjectPlacement=placement(opening_xyz, entities[host].ObjectPlacement), Representation=body(dims))
        rooted("IfcRelVoidsElement", name + "_void", RelatingBuildingElement=entities[host], RelatedOpeningElement=opening)
        rooted("IfcRelFillsElement", name + "_fill", RelatingOpeningElement=opening, RelatedBuildingElement=entities[name])
    for i, building in enumerate(buildings):
        rooted("IfcRelContainedInSpatialStructure", f"containment_{i}", RelatingStructure=building, RelatedElements=contained[i])
    prop = create("IfcPropertySingleValue", Name="LoadBearing", NominalValue=create("IfcBoolean", wrappedValue=False))
    pset = rooted("IfcPropertySet", "wall_pset", Name="Pset_WallCommon", HasProperties=[prop])
    rooted("IfcRelDefinesByProperties", "wall_property_relation", RelatedObjects=[entities["wall"]], RelatingPropertyDefinition=pset)
    model.header.file_name.name = path.name
    model.header.file_name.time_stamp = "2026-11-02T00:00:00"
    model.header.file_name.author = ("IFC-to-CityGML semantic evaluation",)
    path.parent.mkdir(parents=True, exist_ok=True)
    model.write(str(path))
    expected = {"schema": schema, "provenance": "Project-authored controlled semantic specimens; no converter-derived expectations",
                "license": "CC0-1.0", "not_a_real_building": True, "features": features, "omissions": omissions}
    path.with_suffix(".expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    return expected


if __name__ == "__main__":
    for schema in ("IFC4", "IFC2X3"):
        path = Path(__file__).resolve().parents[1] / "data/raw/semantic_cases" / (schema.lower() + ".ifc")
        expected = make_case(path, schema)
        print(f"{schema}: {len(expected['features'])} expected features, {len(expected['omissions'])} expected omissions")
