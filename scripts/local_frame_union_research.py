"""Research adapter: snap and union in a gravity-aligned building placement frame.

The installed extractor stays byte-for-byte unchanged. An exact, checked source
insertion makes the single experimental difference inspectable. The ordinary
writer and independent validators operate on the restored world coordinates.
"""
import inspect
import ifcopenshell.util.placement
import ifcopenshell.util.unit
import numpy as np
import ifc_citygml.envelope as original


def building_frame(model,building):
    frame=np.asarray(ifcopenshell.util.placement.get_local_placement(building.ObjectPlacement),dtype=float)
    frame[:3,3]*=ifcopenshell.util.unit.calculate_unit_scale(model)
    r=frame[:3,:3]
    if not np.allclose(r.T@r,np.eye(3),atol=1e-10) or not np.isclose(np.linalg.det(r),1,atol=1e-10):
        raise ValueError('Research frame requires a proper rigid placement')
    if not np.allclose(r[:,2],[0,0,1],atol=1e-10):
        raise ValueError('Research frame requires a gravity aligned building placement')
    return frame


def to_local(vertices,frame):return (vertices-frame[:3,3])@frame[:3,:3]
def to_world(vertices,frame):return vertices@frame[:3,:3].T+frame[:3,3]


def extract_local_frame(path,profile):
    source=inspect.getsource(original.extract_envelopes)
    anchor='        solids, sources, omitted = [], {}, []'
    vertex='                vertices = np.asarray(shape.geometry.verts, dtype=np.float64).reshape(-1, 3)'
    assert source.count(anchor)==1 and source.count(vertex)==1
    source=source.replace(anchor,anchor+'\n        research_frame = building_frame(model, building)')
    source=source.replace(vertex,vertex+'\n                vertices = to_local(vertices, research_frame)')
    scope={**original.__dict__,'building_frame':building_frame,'to_local':to_local}
    exec(compile(source,'<research_local_frame_extractor>','exec'),scope)
    extraction=scope['extract_envelopes'](path,profile)
    model=original.ifcopenshell.open(str(path));frames=[]
    for building in extraction['buildings']:
        frame=building_frame(model,model.by_guid(building['source_building_global_id']))
        for component in building['components']:
            component['vertices']=to_world(np.asarray(component['vertices']),frame).tolist()
        all_points=np.vstack([c['vertices'] for c in building['components']])
        building['bounds_m']=[all_points.min(axis=0).tolist(),all_points.max(axis=0).tolist()]
        frames.append({'building':building['source_building_global_id'],'matrix_local_to_world':frame.tolist(),
                       'frame_source':'IFC hierarchical building placement; translation converted to SI metres'})
    extraction['research_frame_policy']={'operation':'World vertices to building frame, snap, union, restore world frame',
        'gravity_aligned_only':True,'frames':frames,'grid_m':profile['geometry_tolerance_m'],
        'no_mesh_simplification':True,'coordinate_output':'Original IFC world engineering metre frame',
        'limitation':'Requires a reliable gravity aligned building placement; no geographic transformation is inferred'}
    return extraction
