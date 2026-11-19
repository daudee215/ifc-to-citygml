"""Experimental post-union simplification with explicit provenance and guards.

This module is a research adapter. It never changes the installed converter.
"""
from copy import deepcopy
import manifold3d as m
import numpy as np
from ifc_citygml.envelope import classify_surface


def mesh_statistics(component):
    vertices=np.asarray(component['vertices']);faces=np.asarray(component['triangles'])
    edges=np.unique(np.sort(np.vstack([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
    lengths=np.linalg.norm(vertices[edges[:,0]]-vertices[edges[:,1]],axis=1)
    return {'vertices':len(vertices),'triangles':len(faces),'edges':len(edges),
            'euler_characteristic':len(vertices)-len(edges)+len(faces),
            'minimum_edge_m':float(lengths.min()),'edges_below_1um':int(np.count_nonzero(lengths<1e-6))}


def simplify_extraction(extraction,tolerance=1e-6):
    result=deepcopy(extraction);records=[]
    for building in result['buildings']:
        sources={int(k):v for k,v in building['sources'].items()}
        identities={old:m.Manifold.reserve_ids(1) for old in sources}
        building['sources']={identities[k]:v for k,v in sources.items()}
        for index,component in enumerate(building['components']):
            before=mesh_statistics(component)
            vertices=np.ascontiguousarray(component['vertices'],dtype=np.float64)
            faces=np.ascontiguousarray(component['triangles'],dtype=np.uint64)
            original=m.Manifold(m.Mesh64(vertices,faces,
                run_index=np.arange(0,faces.size+1,3,dtype=np.uint64),
                run_original_id=np.array([identities[int(i)] for i in component['triangle_source_ids']],dtype=np.uint32)))
            if original.status()!=m.Error.NoError:raise ValueError('Reconstructed union is not manifold')
            simplified=original.simplify(tolerance)
            if simplified.status()!=m.Error.NoError or simplified.is_empty():raise ValueError('Simplification failed')
            mesh=simplified.to_mesh64();points=np.asarray(mesh.vert_properties)[:,:3];triangles=np.asarray(mesh.tri_verts)
            ids=np.full(len(triangles),-1,dtype=np.int64)
            for start,end,identity in zip(mesh.run_index[:-1],mesh.run_index[1:],mesh.run_original_id):ids[int(start)//3:int(end)//3]=identity
            if not set(ids).issubset(building['sources']):raise ValueError('Source attribution lost')
            # The documented simplifier retains a subset of input vertices.
            old_set={tuple(v) for v in vertices}
            if any(tuple(v) not in old_set for v in points):raise ValueError('Simplifier introduced new vertex coordinates')
            semantics=[]
            for face,identity in zip(triangles,ids):
                tri=points[face];normal=np.cross(tri[1]-tri[0],tri[2]-tri[0]);length=np.linalg.norm(normal)
                if length==0:raise ValueError('Degenerate simplified triangle')
                semantics.append(classify_surface(building['sources'][int(identity)],normal/length,tri.mean(axis=0),building['bounds_m'][0][2],tolerance))
            candidate={'vertices':points.tolist(),'triangles':triangles.tolist(),'triangle_source_ids':ids.tolist(),
                       'triangle_semantics':semantics,'volume_m3':simplified.volume()}
            after=mesh_statistics(candidate)
            if before['euler_characteristic']!=after['euler_characteristic']:raise ValueError('Euler characteristic changed')
            if len(original.decompose())!=len(simplified.decompose()):raise ValueError('Component count changed')
            relative=abs(simplified.volume()/original.volume()-1)
            if relative>1e-6:raise ValueError('Volume deviation exceeds research guard')
            records.append({'building':building['source_building_global_id'],'component':index,'before':before,'after':after,
                'input_volume_m3':original.volume(),'output_volume_m3':simplified.volume(),'relative_volume_change':relative,
                'vertex_subset_verified':True,'component_count_preserved':True,'attribution_ids_verified':True,
                'original_sources':sorted({sources[int(s)]['ifc_global_id'] for s in component['triangle_source_ids']}),
                'retained_sources':sorted({building['sources'][int(s)]['ifc_global_id'] for s in ids})})
            building['components'][index]=candidate
        building['outer_shell_volume_m3']=sum(c['volume_m3'] for c in building['components'])
        building['research_note']='Post union simplification changes triangulation and may move surfaces within tolerance; not source preserving geometry'
    result['research_simplification']={'tolerance_m':tolerance,'operation':'Manifold.simplify','records':records,
        'scope':'Experimental changed exterior geometry; no coordinate claim follows from a vertex subset alone'}
    return result
