"""Independent serialized geometry, analytic reference, and sampled 3D distances."""
import math
import numpy as np
from lxml import etree as ET
from shapely import union_all,set_precision
from shapely.geometry import Polygon,shape,mapping
import trimesh

NS={'gml':'http://www.opengis.net/gml/3.2','bldg':'http://www.opengis.net/citygml/building/3.0','core':'http://www.opengis.net/citygml/3.0'}

def mesh_from_rings(rings):
    vertices=[];faces=[];lookup={}
    for ring in rings:
        ids=[]
        for point in ring[:-1]:
            key=tuple(point)
            if key not in lookup:lookup[key]=len(vertices);vertices.append(key)
            ids.append(lookup[key])
        for j in range(1,len(ids)-1):faces.append([ids[0],ids[j],ids[j+1]])
    return {'vertices':vertices,'triangles':faces}

def read_geometry(data):
    root=ET.fromstring(data,ET.XMLParser(no_network=True,resolve_entities=False));rings={};plans=[]
    for polygon in root.findall('.//gml:Polygon',NS):
        pos=polygon.find('./gml:exterior/gml:LinearRing/gml:posList',NS)
        points=np.array([float(v) for v in pos.text.split()]).reshape(-1,3)
        if not np.isfinite(points).all() or not np.array_equal(points[0],points[-1]):raise ValueError('Invalid serialized ring')
        rings[polygon.get('{'+NS['gml']+'}id')]=points.tolist()
        poly=Polygon(points[:,:2])
        if poly.area>1e-16:
            if not poly.is_valid:raise ValueError('Invalid projected polygon; no repair')
            plans.append(poly)
    components=[]
    for composite in root.findall('.//gml:CompositeSurface',NS):
        ids=[node.get('{http://www.w3.org/1999/xlink}href','').lstrip('#') or node.find('gml:Polygon',NS).get('{'+NS['gml']+'}id') for node in composite.findall('gml:surfaceMember',NS)]
        components.append(mesh_from_rings([rings[i] for i in ids]))
    if not components:components=[mesh_from_rings(list(rings.values()))]
    return {'mesh':mesh_from_rings(list(rings.values())),'components':components,'footprint':union_all(plans)}

def mesh_statistics(mesh):
    v=np.asarray(mesh['vertices']);f=np.asarray(mesh['triangles'],int)
    edges=np.unique(np.sort(np.vstack([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1),axis=0)
    lengths=np.linalg.norm(v[edges[:,0]]-v[edges[:,1]],axis=1)
    local=v-v[0];volume=float(np.sum(np.einsum('ij,ij->i',local[f[:,0]],np.cross(local[f[:,1]],local[f[:,2]])))/6)
    return {'vertices':len(v),'triangles':len(f),'edges':len(edges),'euler':len(v)-len(edges)+len(f),'minimum_edge_m':float(lengths.min()),
            'edges_below_1um':int(np.count_nonzero(lengths<1e-6)),'signed_volume_m3':volume}

def _samples(mesh,limit):
    v=np.asarray(mesh['vertices']);f=np.asarray(mesh['triangles'],int);points=np.vstack([v,v[f].mean(axis=1)])
    return points[np.linspace(0,len(points)-1,min(limit,len(points)),dtype=int)]

def sampled_surface_distance(first,second,limit=128):
    result=[];counts=[]
    for a,b in [(first,second),(second,first)]:
        samples=_samples(a,limit);mesh=trimesh.Trimesh(np.asarray(b['vertices']),np.asarray(b['triangles']),process=False);values=[]
        for start in range(0,len(samples),16):
            _,distances,_=trimesh.proximity.closest_point_naive(mesh,samples[start:start+16]);values.extend(distances.tolist())
        result.extend(values);counts.append(len(values))
    values=np.array(result)
    return {'sample_count_each_direction':counts,'median_m':float(np.median(values)),'p95_m':float(np.quantile(values,.95)),
            'sampled_maximum_m':float(values.max()),'method':'Deterministic vertices and face-centroid samples to closest triangles, both directions; not a certified Hausdorff bound'}

def compare_export(data,expected,surface_samples=128):
    exported=read_geometry(data);reference=shape(expected['footprint']);actual=exported['footprint'];precision={}
    for grid,label in [(None,'raw'),(1e-9,'measurement_1nm'),(1e-6,'measurement_1um')]:
        a,b=(actual,reference) if grid is None else (set_precision(actual,grid),set_precision(reference,grid))
        precision[label]={'iou':a.intersection(b).area/a.union(b).area,'symmetric_difference_m2':a.symmetric_difference(b).area,
            'boundary_discrete_hausdorff_m':a.boundary.hausdorff_distance(b.boundary),'area_m2':a.area,
            'holes':sum(len(p.interiors) for p in ([a] if a.geom_type=='Polygon' else a.geoms))}
    stats=[mesh_statistics(c) for c in exported['components']];volume=sum(s['signed_volume_m3'] for s in stats)
    result={'footprints':precision,'component_count':len(stats),'euler_sum':sum(s['euler'] for s in stats),
        'minimum_edge_m':min(s['minimum_edge_m'] for s in stats),'volume_m3':volume,'relative_volume_error':volume/expected['volume_m3']-1,
        'reference_kind':expected.get('reference_kind'),'sampled_surface_distance':sampled_surface_distance(exported['mesh'],expected['reference_mesh'],surface_samples)}
    limits=expected['acceptance'];p=precision['measurement_1nm']
    result['guards']={'footprint_iou':p['iou']>=limits['minimum_iou'],'boundary_distance':p['boundary_discrete_hausdorff_m']<=limits['maximum_boundary_distance_m'],
        'sampled_surface_distance':result['sampled_surface_distance']['sampled_maximum_m']<=limits['maximum_boundary_distance_m'],
        'volume':abs(result['relative_volume_error'])<=limits['maximum_relative_volume_error'],
        'components':result['component_count']==expected['expected_components'],'euler':result['euler_sum']==expected['expected_euler_sum'],
        'minimum_edge':result['minimum_edge_m']>=1e-6}
    result['all_guards_passed']=all(result['guards'].values());return result
