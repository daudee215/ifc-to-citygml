"""Source relationship graph and bounded geometric evidence for convex items.

Geometric tests describe source correspondence, never surveyed physical intent.
"""
from itertools import combinations
import math
import ifcopenshell
import numpy as np
from shapely.geometry import MultiPoint

def explicit_graph(model):
    nodes={};edges=[]
    def node(entity):
        key=getattr(entity,'GlobalId',None) or 'step:'+str(entity.id())
        nodes[key]={'id':key,'step_id':entity.id(),'ifc_class':entity.is_a(),'name':getattr(entity,'Name',None)}
        return key
    specifications=[('IfcRelAggregates','RelatingObject','RelatedObjects','aggregates'),
        ('IfcRelNests','RelatingObject','RelatedObjects','nests'),
        ('IfcRelContainedInSpatialStructure','RelatingStructure','RelatedElements','contains'),
        ('IfcRelVoidsElement','RelatingBuildingElement','RelatedOpeningElement','voids'),
        ('IfcRelFillsElement','RelatingOpeningElement','RelatedBuildingElement','fills')]
    for kind,source,target,relation in specifications:
        for rel in model.by_type(kind):
            a=getattr(rel,source);targets=getattr(rel,target)
            if not isinstance(targets,(list,tuple)):targets=[targets]
            for b in targets:
                edges.append({'source':node(a),'target':node(b),'relation':relation,'evidence':'explicit_ifc',
                              'relationship_step_id':rel.id(),'relationship_global_id':rel.GlobalId})
    return {'nodes':list(nodes.values()),'edges':edges,'geometric_relations':[],
            'scope':'Explicit IFC relationships and geometric hypotheses remain separate; neither implies surveyed accuracy'}

def _axes(v,f):
    triangles=v[f];normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    lengths=np.linalg.norm(normals,axis=1);normals=normals[lengths>0]/lengths[lengths>0,None]
    edges=v[np.unique(np.sort(np.vstack([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1),axis=0)]
    directions=edges[:,1]-edges[:,0];directions/=np.linalg.norm(directions,axis=1)[:,None]
    def unique(values):
        result={}
        for a in values:
            if np.linalg.norm(a)<1e-12:continue
            a=a/np.linalg.norm(a);first=next((x for x in a if abs(x)>1e-12),1)
            if first<0:a=-a
            result.setdefault(tuple(np.round(a,11)),a)
        return np.array(list(result.values()))
    return normals,unique(normals),unique(directions)

def convex_planes(vertices,faces,tolerance=1e-11):
    v=np.asarray(vertices,float);f=np.asarray(faces,int);origin=v.mean(axis=0);local=v-origin
    normals,axes,edges=_axes(local,f)
    triangles=local[f];n=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]);length=np.linalg.norm(n,axis=1)
    if np.any(length==0):return None
    n/=length[:,None];offset=np.sum(n*triangles[:,0],axis=1)
    if np.max(local@n.T-offset)>tolerance:return None
    return {'origin':origin,'normals':n,'offsets':offset,'axes':axes,'edge_directions':edges}

def _face_witness(a,b,axis):
    # Midpoint of overlapping support-face projections; no nearest-vertex proxy.
    pa=a@axis;pb=b@axis;left,right=(a,b) if pa.mean()<pb.mean() else (b,a)
    pleft=left@axis;pright=right@axis;h1=pleft.max();h2=pright.min()
    if h2<h1-1e-10:return None,0.
    first=left[np.abs(pleft-h1)<1e-9];second=right[np.abs(pright-h2)<1e-9]
    u=np.cross(axis,[0,0,1])
    if np.linalg.norm(u)<1e-8:u=np.cross(axis,[0,1,0])
    u/=np.linalg.norm(u);w=np.cross(axis,u)
    def poly(points):return MultiPoint(np.column_stack([points@u,points@w])).convex_hull
    intersection=poly(first).intersection(poly(second))
    if intersection.area<=1e-14:return None,float(intersection.area)
    centroid=intersection.centroid
    return centroid.x*u+centroid.y*w+(h1+h2)/2*axis,float(intersection.area)

def convex_relation(first,second,tolerance=1e-11):
    a=np.asarray(first['vertices'],float);b=np.asarray(second['vertices'],float)
    origin=(a.mean(axis=0)+b.mean(axis=0))/2;a=a-origin;b=b-origin
    ca=convex_planes(a,first['triangles'],tolerance);cb=convex_planes(b,second['triangles'],tolerance)
    base={'source':first['ifc_global_id'],'target':second['ifc_global_id'],'evidence':'geometric_convex_separating_axes',
          'numerical_tolerance_m':tolerance,'physical_intent':'not independently established','certified_arithmetic':False}
    if ca is None or cb is None:return {**base,'relation':'unresolved_nonconvex','reason':'Convex separation test not applicable'}
    axes=[*ca['axes'],*cb['axes']]
    axes.extend(np.cross(u,v) for u in ca['edge_directions'] for v in cb['edge_directions'] if np.linalg.norm(np.cross(u,v))>1e-10)
    separation=-float('inf');best=None
    for raw in axes:
        axis=raw/np.linalg.norm(raw);aa=a@axis;bb=b@axis;gap=max(bb.min()-aa.max(),aa.min()-bb.max())
        if gap>separation:separation=float(gap);best=axis
    witness,area=_face_witness(a,b,best)
    if separation>tolerance:relation='separated'
    elif separation < -tolerance:relation='overlapping'
    elif area>1e-12:relation='face_contact'
    else:relation='lower_dimensional_contact'
    result={**base,'relation':relation,'separating_axis_gap_m':separation,'shared_support_area_m2':area,'axis':best.tolist()}
    if witness is not None and separation>tolerance:result['gap_witness_m']=(witness+origin).tolist()
    return result

def geometric_graph(elements,tolerance=1e-11,maximum_pairs=1000):
    relations=[];total=len(elements)*(len(elements)-1)//2
    if total>maximum_pairs:return {'relations':[],'status':'unresolved','reason':f'{total} pairs exceeds declared pair budget {maximum_pairs}'}
    for a,b in combinations(elements,2):relations.append(convex_relation(a,b,tolerance))
    # A pairwise gap witness may be occupied by a third material item.
    for relation in relations:
        if 'gap_witness_m' not in relation:continue
        point=np.array(relation['gap_witness_m']);covered=False;unresolved=False
        for element in elements:
            planes=convex_planes(element['vertices'],element['triangles'],tolerance)
            if planes is None:unresolved=True;continue
            # Boundary probes are ambiguous: the passage midpoint, for example,
            # can coincide with the underside of a legitimate third source.
            if np.max((point-planes['origin'])@planes['normals'].T-planes['offsets']) <= tolerance:covered=True
        relation['protected_gap_probe']=not covered and not unresolved
    return {'relations':relations,'status':'complete' if not any(r['relation'].startswith('unresolved') for r in relations) else 'unresolved',
            'method':'Floating point convex SAT and support-face witnesses; reported as numerical evidence, not a rigorous error certificate'}

def winding_contains(point,vertices,faces):
    triangles=np.asarray(vertices,float)[np.asarray(faces,int)]-np.asarray(point,float)
    a,b,c=triangles[:,0],triangles[:,1],triangles[:,2]
    la=np.linalg.norm(a,axis=1);lb=np.linalg.norm(b,axis=1);lc=np.linalg.norm(c,axis=1)
    numerator=np.einsum('ij,ij->i',a,np.cross(b,c))
    denominator=la*lb*lc+np.einsum('ij,ij->i',a,b)*lc+np.einsum('ij,ij->i',b,c)*la+np.einsum('ij,ij->i',c,a)*lb
    winding=float(np.sum(2*np.arctan2(numerator,denominator))/(4*math.pi))
    return abs(winding)>.5

def correspondence_checks(extraction,graph):
    components=[c for b in extraction['buildings'] for c in b['components']]
    source_components={}
    for number,(building,component) in enumerate((b,c) for b in extraction['buildings'] for c in b['components']):
        for sid in component['triangle_source_ids']:
            record=building['sources'].get(sid,building['sources'].get(str(sid)))
            source_components.setdefault(record['ifc_global_id'],set()).add(number)
    violations=[];unresolved=[]
    for relation in graph['relations']:
        if relation['relation']=='face_contact':
            a=source_components.get(relation['source'],set());b=source_components.get(relation['target'],set())
            if a and b and not a.intersection(b):violations.append({'kind':'false_disconnection','relation':relation})
            if not a or not b:unresolved.append({'kind':'source_not_exposed','relation':relation})
        if relation.get('protected_gap_probe'):
            if any(winding_contains(relation['gap_witness_m'],c['vertices'],c['triangles']) for c in components):violations.append({'kind':'gap_witness_filled','relation':relation})
        if relation['relation'] in {'lower_dimensional_contact','unresolved_nonconvex'}:unresolved.append(relation)
    return {'violations':violations,'unresolved':unresolved,'status':'failed' if violations else 'unresolved' if unresolved or graph['status']!='complete' else 'passed',
            'scope':'Checks exposed source contacts and finite protected-gap probes, not complete volumetric equivalence'}
