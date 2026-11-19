"""Analytical building families, real-gap controls and placement refactoring."""
from pathlib import Path
import math
import uuid
import ifcopenshell
import ifcopenshell.guid
from shapely import affinity,union_all
from shapely.geometry import box,Point,mapping
from ifc_citygml.common import write_json,digest

FAMILIES=['rectangle','l_shape','u_shape','courtyard','setback','gap_pair','passage','cantilever','gable_roof','hip_roof','multipart','slab_opening','cylinder']
ID=uuid.UUID('42c75cad-0aa0-4829-8ae5-aad293238e01')

def reference_mesh(parts,family,scale):
    """Independent cell-boundary construction, not IFC tessellation or Manifold."""
    vertices=[];faces=[];lookup={}
    def face(points):
        ids=[]
        for point in points:
            key=tuple(float(v) for v in point)
            if key not in lookup:lookup[key]=len(vertices);vertices.append(key)
            ids.append(lookup[key])
        for i in range(1,len(ids)-1):faces.append([ids[0],ids[i],ids[i+1]])
    if family in {'gable_roof','hip_roof'}:
        v=[(0,0,0),(12,0,0),(12,8,0),(0,8,0),(0,0,3),(12,0,3),(12,8,3),(0,8,3)]
        v.extend([(0,4,6),(12,4,6)] if family=='gable_roof' else [(4,4,6),(8,4,6)])
        for f in [[0,3,2,1],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7],[4,5,9,8],[8,9,6,7],[4,8,7],[5,6,9]]:face([[c*scale for c in v[i]] for i in f])
    elif family=='cylinder':
        n=512;r=4*scale;h=6*scale
        bottom=[(r+r*math.cos(2*math.pi*i/n),r+r*math.sin(2*math.pi*i/n),0) for i in range(n)]
        top=[(x,y,h) for x,y,z in bottom]
        for i in range(n):
            j=(i+1)%n;face([bottom[i],bottom[j],top[j],top[i]])
            face([(r,r,0),bottom[j],bottom[i]]);face([(r,r,h),top[i],top[j]])
    else:
        boxes=[p['box'] for p in parts if p['kind']=='box']
        if family=='slab_opening':boxes=[tuple(c*scale for c in p) for p in [(0,0,0,12,3,1.5),(0,7,0,12,3,1.5),(0,3,0,3,4,1.5),(9,3,0,3,4,1.5)]]
        axes=[sorted({v for b in boxes for v in (b[k],b[k]+b[k+3])}) for k in range(3)]
        occupied=set()
        for i in range(len(axes[0])-1):
            for j in range(len(axes[1])-1):
                for k in range(len(axes[2])-1):
                    p=[(axes[d][a]+axes[d][a+1])/2 for d,a in enumerate([i,j,k])]
                    if any(all(b[d]<p[d]<b[d]+b[d+3] for d in range(3)) for b in boxes):occupied.add((i,j,k))
        for i,j,k in sorted(occupied):
            x,X=axes[0][i:i+2];y,Y=axes[1][j:j+2];z,Z=axes[2][k:k+2]
            v=[(x,y,z),(X,y,z),(X,Y,z),(x,Y,z),(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)]
            for neighbour,quad in [((i,j,k-1),[0,3,2,1]),((i,j,k+1),[4,5,6,7]),((i,j-1,k),[0,1,5,4]),((i+1,j,k),[1,2,6,5]),((i,j+1,k),[2,3,7,6]),((i-1,j,k),[3,0,4,7])]:
                if neighbour not in occupied:face([v[a] for a in quad])
    return vertices,faces

def specification(family,scale=1.,gap=0.):
    shapes={
      'rectangle':[(0,0,0,12,8,6)],'l_shape':[(0,0,0,12,3,6),(0,3,0,3,5,6)],
      'u_shape':[(0,0,0,3,8,6),(9,0,0,3,8,6),(3,0,0,6,3,6)],
      'courtyard':[(0,0,0,12,3,6),(0,7,0,12,3,6),(0,3,0,3,4,6),(9,3,0,3,4,6)],
      'setback':[(0,0,0,12,8,3),(3,2,3,6,4,3)],
      'gap_pair':[(0,0,0,6,8,6),(6+gap,0,0,6,8,6)],
      'passage':[(0,0,0,3,8,6),(9,0,0,3,8,6),(3,0,3,6,8,3)],
      'cantilever':[(3,2,0,6,4,3),(0,0,3,12,8,3)],
      'gable_roof':[(0,0,0,12,8,3)],'hip_roof':[(0,0,0,12,8,3)],
      'multipart':[(0,0,0,5,8,6),(7,0,0,5,8,6)],
      'slab_opening':[],'cylinder':[]}
    boxes=shapes[family];parts=[{'kind':'box','box':tuple(v*scale for v in values),'ifc_class':'IfcWall'} for values in boxes]
    if family in {'gable_roof','hip_roof'}:parts.append({'kind':family,'scale':scale,'ifc_class':'IfcRoof'})
    if family=='slab_opening':parts.append({'kind':'ring','scale':scale,'ifc_class':'IfcSlab'})
    if family=='cylinder':parts.append({'kind':'cylinder','scale':scale,'ifc_class':'IfcWall'})
    if family=='slab_opening':footprint=box(0,0,12,10).difference(box(3,3,9,7));volume=144*scale**3
    elif family=='cylinder':footprint=Point(4,4).buffer(4,quad_segs=1024);volume=math.pi*16*6*scale**3
    else:
        footprint=union_all([box(x,y,x+w,y+d) for x,y,z,w,d,h in boxes]);volume=sum(w*d*h for x,y,z,w,d,h in boxes)*scale**3
        if family=='gable_roof':volume+=144*scale**3
        if family=='hip_roof':volume+=112*scale**3
    footprint=affinity.scale(footprint,scale,scale,origin=(0,0))
    components=2 if family=='multipart' or family=='gap_pair' and gap>0 else 1
    euler=0 if family in {'courtyard','slab_opening'} else 2*components
    return parts,footprint,volume,components,euler

def create_case(path,family,building_yaw=0.,contents_yaw=0.,millimetres=False,scale=1.,gap=0.,translation=(100,200,10),group=None):
    path=Path(path);parts,footprint,volume,components,euler=specification(family,scale,gap)
    f=ifcopenshell.file(schema='IFC4');factor=1000. if millimetres else 1.
    def e(kind,**kw):return f.create_entity(kind,**kw)
    def point(values):return e('IfcCartesianPoint',Coordinates=tuple(float(v)*factor for v in values))
    def direction(values):return e('IfcDirection',DirectionRatios=tuple(float(v) for v in values))
    def axis(offset=(0,0,0),yaw=0):
        a=math.radians(yaw);return e('IfcAxis2Placement3D',Location=point(offset),Axis=direction((0,0,1)),RefDirection=direction((math.cos(a),math.sin(a),0)))
    def rooted(kind,key,**kw):return e(kind,GlobalId=ifcopenshell.guid.compress(uuid.uuid5(ID,path.stem+'/'+key).hex),**kw)
    context=e('IfcGeometricRepresentationContext',ContextIdentifier='Model',ContextType='Model',CoordinateSpaceDimension=3,Precision=1e-9*factor,WorldCoordinateSystem=axis())
    unit=e('IfcSIUnit',UnitType='LENGTHUNIT',Name='METRE',Prefix='MILLI' if millimetres else None)
    project=rooted('IfcProject','project',Name='Independent analytical expansion fixture',RepresentationContexts=[context],UnitsInContext=e('IfcUnitAssignment',Units=[unit]))
    building=rooted('IfcBuilding','building',Name=family,CompositionType='ELEMENT',ObjectPlacement=e('IfcLocalPlacement',RelativePlacement=axis(translation,building_yaw)))
    rooted('IfcRelAggregates','project_building',RelatingObject=project,RelatedObjects=[building]);members=[]
    def ring(points):return e('IfcPolyline',Points=[point(p) for p in points])
    for i,part in enumerate(parts):
        offset=(0,0,0);kind=part['kind'];representation='SweptSolid'
        if kind=='box':
            x,y,z,w,d,h=part['box'];offset=(x,y,z)
            profile=e('IfcRectangleProfileDef',ProfileType='AREA',Position=e('IfcAxis2Placement2D',Location=point((w/2,d/2))),XDim=w*factor,YDim=d*factor)
            solid=e('IfcExtrudedAreaSolid',SweptArea=profile,Position=axis(),ExtrudedDirection=direction((0,0,1)),Depth=h*factor)
        elif kind=='ring':
            outer=[(0,0),(12,0),(12,10),(0,10),(0,0)];inner=[(3,3),(3,7),(9,7),(9,3),(3,3)]
            profile=e('IfcArbitraryProfileDefWithVoids',ProfileType='AREA',OuterCurve=ring([(x*scale,y*scale) for x,y in outer]),InnerCurves=[ring([(x*scale,y*scale) for x,y in inner])])
            solid=e('IfcExtrudedAreaSolid',SweptArea=profile,Position=axis(),ExtrudedDirection=direction((0,0,1)),Depth=1.5*scale*factor)
        elif kind=='cylinder':
            profile=e('IfcCircleProfileDef',ProfileType='AREA',Position=e('IfcAxis2Placement2D',Location=point((4*scale,4*scale))),Radius=4*scale*factor)
            solid=e('IfcExtrudedAreaSolid',SweptArea=profile,Position=axis(),ExtrudedDirection=direction((0,0,1)),Depth=6*scale*factor)
        else:
            vertices=[(0,0,3),(12,0,3),(12,8,3),(0,8,3)]+([(0,4,6),(12,4,6)] if kind=='gable_roof' else [(4,4,6),(8,4,6)])
            vertices=[point([v*scale for v in p]) for p in vertices]
            faces=[[0,3,2,1],[0,1,5,4],[4,5,2,3],[0,4,3],[1,2,5]]
            shell=e('IfcClosedShell',CfsFaces=[e('IfcFace',Bounds=[e('IfcFaceOuterBound',Bound=e('IfcPolyLoop',Polygon=[vertices[v] for v in face]),Orientation=True)]) for face in faces])
            solid=e('IfcFacetedBrep',Outer=shell);representation='Brep'
        a=math.radians(contents_yaw);x,y,z=offset;offset=(math.cos(a)*x-math.sin(a)*y,math.sin(a)*x+math.cos(a)*y,z)
        placement=e('IfcLocalPlacement',PlacementRelTo=building.ObjectPlacement,RelativePlacement=axis(offset,contents_yaw))
        rep=e('IfcShapeRepresentation',ContextOfItems=context,RepresentationIdentifier='Body',RepresentationType=representation,Items=[solid])
        members.append(rooted(part['ifc_class'],f'part{i}',Name=f'Analytical {kind} {i}',ObjectPlacement=placement,Representation=e('IfcProductDefinitionShape',Representations=[rep])))
    rooted('IfcRelContainedInSpatialStructure','containment',RelatedElements=members,RelatingStructure=building)
    f.header.file_name.name=path.name;f.header.file_name.time_stamp='2026-11-03T00:00:00';f.header.file_name.author=('IFC to CityGML research project',)
    path.parent.mkdir(parents=True,exist_ok=True);f.write(str(path))
    footprint=affinity.translate(affinity.rotate(footprint,building_yaw+contents_yaw,origin=(0,0)),translation[0],translation[1])
    maxheight=1.5*scale if family=='slab_opening' else 6*scale
    expected={'case':path.stem,'family':family,'shape_family':family,'building_yaw':building_yaw,'contents_yaw':contents_yaw,'scale':scale,'gap_m':gap*scale,
        'units':'millimetre' if millimetres else 'metre','translation_m':list(translation),'group':group or path.stem,
        'footprint':mapping(footprint),'area_m2':footprint.area,'volume_m3':volume,'holes':sum(len(p.interiors) for p in ([footprint] if footprint.geom_type=='Polygon' else footprint.geoms)),
        'expected_components':components,'expected_euler_sum':euler,'z_bounds_m':[translation[2],translation[2]+maxheight],
        'reference_kind':'closed_form_prisms' if family!='cylinder' else 'analytical_cylinder_with_dense_independent_plan_reference',
        'acceptance':{'minimum_iou':.999 if family=='cylinder' else .999999,'maximum_boundary_distance_m':.005*scale if family=='cylinder' else 5e-6,
            'maximum_relative_volume_error':.001 if family=='cylinder' else 1e-6}}
    rv,rf=reference_mesh(parts,family,scale);angle=math.radians(building_yaw+contents_yaw);c,s=math.cos(angle),math.sin(angle)
    expected['reference_mesh']={'vertices':[[translation[0]+c*x-s*y,translation[1]+s*x+c*y,translation[2]+z] for x,y,z in rv],'triangles':rf,
        'method':'Independent analytical cell boundary or explicit roof polyhedron; cylinder sampled at 512 segments',
        'maximum_curve_chord_error_m':4*scale*(1-math.cos(math.pi/512)) if family=='cylinder' else 0.}
    write_json(path.with_suffix('.expected.json'),expected)
    return {'case':path.stem,'input':str(path.resolve()),'input_sha256':digest(path),'expected_sha256':digest(path.with_suffix('.expected.json')),
            'family':family,'group':expected['group'],'provenance':{'kind':'project_authored_analytic_control','licence':'CC0-1.0','independent_building':False}}

def prepare_suite(folder,kind='smoke',count=None):
    folder=Path(folder)
    if folder.exists() and any(folder.iterdir()):raise FileExistsError('Refuse to overwrite a registered suite')
    folder.mkdir(parents=True,exist_ok=True);cases=[];pairs=[]
    write_json(folder/'PLAN.json',{'suite':kind,'counts':{'gaps':48,'smoke':120,'development':count or 800,'locked':count or 400}[kind],
        'generator_sha256':digest(Path(__file__)),'settings':'Fixed deterministic design before fixture generation',
        'locked_policy':'No locked outcomes may be used to tune the evaluated backend; inspected cases must be relabelled development'})
    if kind=='gaps':
        for gap in [0,1e-9,1e-7,5e-7,2e-6,1e-3]:
            for yaw in [0,17,43,71]:
                for mm in [False,True]:
                    name=f'gap_{gap:g}_yaw{yaw}_{"mm" if mm else "m"}'.replace('.','p')
                    cases.append(create_case(folder/(name+'.ifc'),'gap_pair',contents_yaw=yaw,millimetres=mm,gap=gap,group=f'gap_{gap:g}_yaw{yaw}'))
    elif kind=='smoke':
        for family in FAMILIES:
            for outer in [0,37]:
                for inner in [0,23]:
                    for mm in [False,True]:
                        name=f'{family}_b{outer}_c{inner}_{"mm" if mm else "m"}'
                        cases.append(create_case(folder/(name+'.ifc'),family,outer,inner,mm,gap=.001 if family=='gap_pair' else 0,group=f'{family}_{outer}_{inner}'))
        for family in ['l_shape','u_shape','courtyard','setback']:
            for inner in [0,23]:
                for mm in [False,True]:
                    base=f'{family}_b37_c{inner}_{"mm" if mm else "m"}';name=base+'_refactored'
                    cases.append(create_case(folder/(name+'.ifc'),family,0,37+inner,mm,group=f'{family}_37_{inner}'))
                    pairs.append({'first':base,'second':name,'invariant':'Same physical world geometry, different placement hierarchy'})
    elif kind in {'development','locked'}:
        import random
        rng=random.Random(6308 if kind=='development' else 90417);count=count or (800 if kind=='development' else 400)
        for i in range(count):
            families=FAMILIES[:11] if kind=='development' else FAMILIES
            family=families[i%len(families)];outer=rng.uniform(-180,180);inner=rng.uniform(-180,180);scale=rng.uniform(.6,2.)
            translation=(100,200,10) if i%3 else (395000,4982000,200)
            name=f'{kind}_{i:04}_{family}'
            cases.append(create_case(folder/(name+'.ifc'),family,outer,inner,i%2==1,scale=scale,gap=rng.choice([1e-7,.001,.1]) if family=='gap_pair' else 0,translation=translation,group=f'{kind}_{i:04}'))
    else:raise ValueError('Unknown suite')
    manifest={'suite':kind,'cases':cases,'placement_pairs':pairs,'partition':'locked_evaluation' if kind=='locked' else 'development',
        'sampling_note':'Related parameterised controls; metamorphic and unit counterparts are not independent real buildings'}
    write_json(folder/'manifest.json',manifest);return manifest
