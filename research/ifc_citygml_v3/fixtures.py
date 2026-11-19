"""Fresh mechanisms and corrected analytical references, registered before runs."""
from pathlib import Path
import json,math,random,uuid
import numpy as np
import ifcopenshell,ifcopenshell.guid
import ifcopenshell.util.unit
import ifcopenshell.util.placement
from shapely.geometry import Polygon,mapping
from shapely import union_all
from ifc_citygml.common import digest,write_json
from ifc_citygml_lab.fixtures import create_case,FAMILIES,reference_mesh
from .references import corrected_expected

MECHANISMS=['ordinary','tilted','faceted_encoding','logical_connection','geometric_connection','conflicting_connection','protected_gap','party_wall']
NAMESPACE=uuid.UUID('86f1a882-85b9-4970-a591-1841e8eb9768')
def gid(key):return ifcopenshell.guid.compress(uuid.uuid5(NAMESPACE,key).hex)

def add_connection(model,kind,key):
    elements=sorted(model.by_type('IfcWall'),key=lambda e:e.id())
    if len(elements)!=2:raise ValueError('Connection fixture expects two walls')
    a,b=elements;geometry=None
    if kind!='logical_connection':
        scale=ifcopenshell.util.unit.calculate_unit_scale(model);va=a.Representation.Representations[0].Items[0];vb=b.Representation.Representations[0].Items[0]
        pa=np.asarray(ifcopenshell.util.placement.get_local_placement(a.ObjectPlacement));pb=np.asarray(ifcopenshell.util.placement.get_local_placement(b.ObjectPlacement))
        world_mid=(pa[:3,3]+pa[:3,:3]@np.array([va.SweptArea.XDim,0,0])+pb[:3,3])/2
        world_normal=pa[:3,0]
        def plane(element,mat,shift):
            point=mat[:3,:3].T@(world_mid-mat[:3,3]);point[0]+=shift/scale
            normal=mat[:3,:3].T@world_normal;ref=mat[:3,:3].T@pa[:3,1]
            return model.create_entity('IfcPlane',Position=model.create_entity('IfcAxis2Placement3D',Location=model.create_entity('IfcCartesianPoint',Coordinates=tuple(float(v) for v in point)),
                Axis=model.create_entity('IfcDirection',DirectionRatios=tuple(float(v) for v in normal)),RefDirection=model.create_entity('IfcDirection',DirectionRatios=tuple(float(v) for v in ref))))
        geometry=model.create_entity('IfcConnectionSurfaceGeometry',SurfaceOnRelatingElement=plane(a,pa,0),SurfaceOnRelatedElement=plane(b,pb,.01 if kind=='conflicting_connection' else 0))
    model.create_entity('IfcRelConnectsElements',GlobalId=gid(key+'/connection'),RelatingElement=a,RelatedElement=b,ConnectionGeometry=geometry)

def faceted_encoding(model):
    for element in model.by_type('IfcWall'):
        rep=element.Representation.Representations[0];solid=rep.Items[0]
        if not solid.is_a('IfcExtrudedAreaSolid') or not solid.SweptArea.is_a('IfcRectangleProfileDef'):continue
        w,d,h=solid.SweptArea.XDim,solid.SweptArea.YDim,solid.Depth
        vertices=[(0,0,0),(w,0,0),(w,d,0),(0,d,0),(0,0,h),(w,0,h),(w,d,h),(0,d,h)]
        points=[model.create_entity('IfcCartesianPoint',Coordinates=tuple(float(x) for x in p)) for p in vertices];faces=[]
        for indices in [[0,3,2,1],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7],[4,5,6,7]]:
            loop=model.create_entity('IfcPolyLoop',Polygon=[points[i] for i in indices]);bound=model.create_entity('IfcFaceOuterBound',Bound=loop,Orientation=True);faces.append(model.create_entity('IfcFace',Bounds=[bound]))
        rep.Items=[model.create_entity('IfcFacetedBrep',Outer=model.create_entity('IfcClosedShell',CfsFaces=faces))];rep.RepresentationType='Brep'

def prepare(folder,partition='development',count=80):
    folder=Path(folder)
    if folder.exists():raise FileExistsError('Registered suites are immutable')
    folder.mkdir(parents=True);rng=random.Random(71358 if partition=='development' else 93171);cases=[]
    write_json(folder/'PLAN.json',{'partition':partition,'count':count,'generator_sha256':digest(Path(__file__)),'mechanisms':MECHANISMS,
        'policy':'No holdout outcomes enter tuning; source and reference facts fixed before run','related_controls_not_independent_buildings':True})
    for i in range(count):
        mechanism=MECHANISMS[i%len(MECHANISMS)];family=FAMILIES[(i//len(MECHANISMS))%len(FAMILIES)]
        if mechanism in ['logical_connection','geometric_connection','conflicting_connection','protected_gap','party_wall']:family='gap_pair'
        elif mechanism=='faceted_encoding':family=['u_shape','courtyard','passage'][i//8%3]
        scale=rng.uniform(.65,1.75);building=rng.uniform(-180,180);contents=rng.uniform(-180,180)
        gap=(4e-8/scale if mechanism in ['logical_connection','geometric_connection','conflicting_connection'] else rng.choice([1e-9,.002,.2])/scale if mechanism=='protected_gap' else 0)
        translation=(395000,4982000,200) if i%3==0 else (100,200,10)
        path=folder/f'v3_{partition}_{i:04}_{mechanism}.ifc';record=create_case(path,family,building,contents,i%2==1,scale=scale,gap=gap,translation=translation)
        expected=corrected_expected(json.loads(path.with_suffix('.expected.json').read_text()));model=ifcopenshell.open(str(path))
        if mechanism=='faceted_encoding':faceted_encoding(model)
        elif mechanism in ['logical_connection','geometric_connection','conflicting_connection']:add_connection(model,mechanism,path.stem)
        elif mechanism=='party_wall':
            building_entity=model.by_type('IfcBuilding')[0];walls=sorted(model.by_type('IfcWall'),key=lambda e:e.id());project=model.by_type('IfcProject')[0]
            other=model.create_entity('IfcBuilding',GlobalId=gid(path.stem+'/other'),Name='Independent adjoining building',CompositionType='ELEMENT',ObjectPlacement=building_entity.ObjectPlacement)
            model.by_type('IfcRelContainedInSpatialStructure')[0].RelatedElements=[walls[0]]
            model.create_entity('IfcRelContainedInSpatialStructure',GlobalId=gid(path.stem+'/contain'),RelatingStructure=other,RelatedElements=[walls[1]])
            model.create_entity('IfcRelAggregates',GlobalId=gid(path.stem+'/aggregate'),RelatingObject=project,RelatedObjects=[other]);expected['expected_components']=2;expected['expected_euler_sum']=4
            # Per-building material targets retain both sides of the party wall.
            # A single aggregate-union reference would wrongly omit that interface.
            vertices=[];faces=[]
            for x in [0.,6.]:
                rv,rf=reference_mesh([{'kind':'box','box':(x,0,0,6,8,6)}],'rectangle',1.);shift=len(vertices);vertices.extend(rv);faces.extend([[j+shift for j in face] for face in rf])
            angle=math.radians(building+contents);R=np.array([[math.cos(angle),-math.sin(angle),0],[math.sin(angle),math.cos(angle),0],[0,0,1]])
            expected['reference_mesh']={'vertices':(np.asarray(vertices)*scale@R.T+np.asarray(translation)).tolist(),'triangles':faces,'method':'Separate per-building cell boundaries; party-wall interfaces retained'}
        elif mechanism=='tilted':
            angle=math.radians(rng.uniform(8,27));R=np.array([[math.cos(angle),0,math.sin(angle)],[0,1,0],[-math.sin(angle),0,math.cos(angle)]])
            b=model.by_type('IfcBuilding')[0];axis=b.ObjectPlacement.RelativePlacement;old=np.asarray(ifcopenshell.util.placement.get_axis2placement(axis));rot=R@old[:3,:3]
            axis.Axis=model.create_entity('IfcDirection',DirectionRatios=tuple(float(v) for v in rot[:,2]));axis.RefDirection=model.create_entity('IfcDirection',DirectionRatios=tuple(float(v) for v in rot[:,0]))
            vertices=np.asarray(expected['reference_mesh']['vertices']);vertices=(vertices-np.asarray(translation))@R.T+np.asarray(translation);expected['reference_mesh']['vertices']=vertices.tolist()
            projections=[Polygon(vertices[f,:2]) for f in expected['reference_mesh']['triangles'] if Polygon(vertices[f,:2]).area>1e-12];footprint=union_all(projections)
            expected['footprint']=mapping(footprint);expected['area_m2']=footprint.area;expected['z_bounds_m']=[float(vertices[:,2].min()),float(vertices[:,2].max())]
        model.write(str(path));expected['mechanism']=mechanism;expected['reference_intent']='Declared plane contact' if mechanism=='geometric_connection' else 'Unmodified analytic material arrangement'
        if mechanism=='geometric_connection':
            # Declared target closes the registered microgap through a bounded source-plane projection.
            target_path=folder/(path.stem+'.contact_target.ifc');target=create_case(target_path,'gap_pair',building,contents,i%2==1,scale=scale,gap=0,translation=translation)
            target_expected=corrected_expected(json.loads(target_path.with_suffix('.expected.json').read_text()));expected['reference_mesh']=target_expected['reference_mesh'];expected['expected_components']=1;expected['expected_euler_sum']=2
            expected['acceptance']['maximum_relative_volume_error']=1e-6
        write_json(path.with_suffix('.expected.json'),expected)
        record.update(input_sha256=digest(path),expected_sha256=digest(path.with_suffix('.expected.json')),mechanism=mechanism,partition=partition)
        cases.append(record)
    manifest={'partition':partition,'cases':cases,'reference_revision':'v3_unscaled_arrangement','description':'Fresh seeds and source encoding/connection/placement mechanisms; related analytical controls'}
    write_json(folder/'manifest.json',manifest);return manifest
