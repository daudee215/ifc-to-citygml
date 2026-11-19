"""Post-evaluation topology and interface localisation; not a formal certificate."""
import math
import numpy as np
from shapely.geometry import MultiPoint,Polygon
from shapely import union_all
from ifc_citygml_v3.native import components
from ifc_citygml_lab.metrics import mesh_statistics

def signed_winding(point,mesh):
    tri=np.asarray(mesh['vertices'])[np.asarray(mesh['triangles'],int)]-np.asarray(point);a,b,c=tri[:,0],tri[:,1],tri[:,2]
    la,lb,lc=[np.linalg.norm(x,axis=1) for x in [a,b,c]]
    numerator=np.einsum('ij,ij->i',a,np.cross(b,c));denominator=la*lb*lc+np.einsum('ij,ij->i',a,b)*lc+np.einsum('ij,ij->i',b,c)*la+np.einsum('ij,ij->i',c,a)*lb
    return float(np.sum(2*np.arctan2(numerator,denominator))/(4*math.pi))

def material_contains(point,meshes):return abs(sum(signed_winding(point,m) for m in meshes))>.5

def topology(mesh):
    # Weld equal coordinates only. Do not collapse small but positive source gaps.
    vertices=[];lookup={};faces=[]
    for f in mesh['triangles']:
        face=[]
        for i in f:
            point=tuple(mesh['vertices'][i])
            if point not in lookup:lookup[point]=len(vertices);vertices.append(point)
            face.append(lookup[point])
        faces.append(face)
    welded={'vertices':vertices,'triangles':faces};edges={};directions={}
    for f in faces:
        for a,b in zip(f,[*f[1:],f[0]]):
            key=tuple(sorted((a,b)));edges[key]=edges.get(key,0)+1;directions[key]=directions.get(key,0)+(1 if a<b else -1)
    closed=all(n==2 for n in edges.values());oriented=all(n==0 for n in directions.values());shells=components(welded);stats=[]
    for shell in shells:
        used=sorted({i for face in shell['triangles'] for i in face});remap={i:j for j,i in enumerate(used)}
        compact={'vertices':[shell['vertices'][i] for i in used],'triangles':[[remap[i] for i in face] for face in shell['triangles']]}
        stats.append(mesh_statistics(compact))
    return {'closed_edge_incidence':closed,'consistent_edge_orientation':oriented,'surface_shells':len(shells),'euler':sum(s['euler'] for s in stats),
        'surface_betti_1_if_closed_oriented':2*len(shells)-sum(s['euler'] for s in stats) if closed and oriented else None,
        'positive_oriented_shells':sum(s['signed_volume_m3']>0 for s in stats),'negative_oriented_shells':sum(s['signed_volume_m3']<0 for s in stats),
        'scope':'Combinatorial oriented surface indicators; no self-intersection or complete material/void homology proof; negative shells require containment interpretation'}

def contact_interface_exposure(source,extraction,relations):
    elements={e['ifc_global_id']:e for b in source['buildings'] for e in b['elements']};rows=[]
    for r in relations:
        if r['relation']!='face_contact' or r['source'] not in elements or r['target'] not in elements:continue
        a=np.asarray(elements[r['source']]['vertices']);b=np.asarray(elements[r['target']]['vertices']);origin=(a.mean(0)+b.mean(0))/2;axis=np.asarray(r['axis']);a-=origin;b-=origin
        if np.mean(a@axis)>np.mean(b@axis):a,b=b,a
        h1=float((a@axis).max());h2=float((b@axis).min());height=(h1+h2)/2
        epsilon=max(1e-9,r.get('coordinate_roundoff_indicator_m',1e-11)*4)
        u=np.cross(axis,[0,0,1])
        if np.linalg.norm(u)<1e-8:u=np.cross(axis,[0,1,0])
        u/=np.linalg.norm(u);w=np.cross(axis,u)
        def project(v):return np.column_stack([v@u,v@w])
        pa=MultiPoint(project(a[np.abs(a@axis-h1)<=epsilon])).convex_hull;pb=MultiPoint(project(b[np.abs(b@axis-h2)<=epsilon])).convex_hull;interface=pa.intersection(pb)
        if interface.area<=1e-12:continue
        exposed=[]
        for building in extraction['buildings']:
            for c in building['components']:
                v=np.asarray(c['vertices'])-origin
                for face,sid in zip(c['triangles'],c['triangle_source_ids']):
                    source_record=building['sources'].get(sid,building['sources'].get(str(sid)))
                    if source_record['ifc_global_id'] not in [r['source'],r['target']]:continue
                    tri=v[face]
                    if np.abs(tri@axis-height).max()>epsilon:continue
                    polygon=Polygon(project(tri))
                    if polygon.area>1e-14:exposed.append(polygon.intersection(interface))
        area=union_all(exposed).area if exposed else 0.
        rows.append({'source':r['source'],'target':r['target'],'shared_support_area_m2':interface.area,'exposed_output_interface_area_m2':area,
            'exposed_fraction':area/interface.area,'plane_distance_tolerance_m':epsilon,'interpretation':'Potential unresolved material interface' if area>1e-8 else 'No exposed interface detected',
            'scope':'Post-evaluation finite-precision diagnostic; exposure can also reflect a genuine microscopic source gap, so source intent is not inferred'})
    return rows
