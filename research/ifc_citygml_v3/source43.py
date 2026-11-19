"""Experimental IFC4X3 selected-building adapter; frozen V2 extraction algorithm retained.

This does not qualify infrastructure alignments or linear placements. Map metadata
are retained without geographic application. Unsupported placements fail explicitly.
"""
from pathlib import Path
import hashlib
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.placement
import ifcopenshell.util.unit
from ifc_citygml.common import digest,load_profile
from ifc_citygml.envelope import _host_guid
from ifc_citygml_lab.evidence import explicit_graph
from ifc_citygml_lab.geometry import engineering_profile as legacy_profile
from .limits import geometry_eligibility

def engineering_profile(path):
    model=ifcopenshell.open(str(path))
    if not model.schema.startswith('IFC4X3'):return legacy_profile(path)
    profile=load_profile('engineering-exterior')
    profile.update(profile_id='v3.1-ifc4x3-selected-building-engineering',supported_ifc_schemas=[model.schema],
        representation='selected_material_union',qualified_scope='Experimental selected building solids with ordinary local placements; no road/rail alignment interpretation')
    profile['shell_ifc_classes'] += ['IfcBeam','IfcColumn','IfcMember','IfcPlate','IfcFooting','IfcStair','IfcStairFlight','IfcBuildingElementProxy']
    profile['retained_map_metadata_not_applied']=[str(r) for r in model.by_type('IfcMapConversion')]+[str(r) for r in model.by_type('IfcProjectedCRS')]
    return profile

def extract_sources(path,allow_ifc43=True):
    model=ifcopenshell.open(str(path));settings=ifcopenshell.geom.settings();settings.set('use-world-coords',True);settings.set('convert-back-units',False)
    import ifcopenshell.util.geolocation as geo
    wcs=geo.get_wcs(model)
    if wcs is not None and not np.allclose(wcs,np.eye(4),atol=1e-12,rtol=0):
        raise ValueError('Nonidentity representation context is outside the tested extraction contract')
    if model.schema.startswith('IFC4X3') and not allow_ifc43:raise ValueError('IFC4X3 building adapter requires explicit experimental opt-in')
    profile=engineering_profile(path);profile['resource_eligibility']={'maximum_triangles_per_element':20000,'maximum_vertex_face_matrix_entries':1000000};buildings=[];failures=[]
    for building in sorted(model.by_type('IfcBuilding'),key=lambda b:b.GlobalId):
        elements=[];omitted=[]
        for element in sorted(ifcopenshell.util.element.get_decomposition(building),key=lambda e:e.id()):
            if not element.is_a('IfcElement') or element.is_a('IfcFeatureElement'):continue
            record={'ifc_global_id':element.GlobalId,'ifc_class':element.is_a(),'step_id':element.id(),'name':element.Name,
                    'predefined_type':getattr(element,'PredefinedType',None),'host_global_id':_host_guid(element)}
            if not any(element.is_a(c) for c in profile['shell_ifc_classes']):omitted.append({**record,'reason':'Outside declared shell classes'});continue
            if not element.Representation:omitted.append({**record,'reason':'Missing source representation'});continue
            representations=list(element.Representation.Representations)
            body=[r for r in representations if (r.RepresentationIdentifier or '').lower()=='body']
            if len(body)>1:failures.append({**record,'reason':'Multiple Body representations require an explicit selection policy'});continue
            annotations=all((r.RepresentationIdentifier or '').lower() in {'annotation','axis','footprint'} for r in representations)
            if annotations:omitted.append({**record,'reason':'Annotation only representation'});continue
            try:
                shape=ifcopenshell.geom.create_shape(settings,body[0] if body else element)
                if body:
                    # SDK representation-only geometry does not apply the product placement.
                    import ifcopenshell.util.shape as shape_util
                    placement=np.asarray(ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement),float)
                    placement[:3,3]*=ifcopenshell.util.unit.calculate_unit_scale(model)
                    vertices=np.asarray(shape.verts,float).reshape(-1,3)@placement[:3,:3].T+placement[:3,3]
                    triangles=np.asarray(shape.faces,np.uint64).reshape(-1,3);items=np.asarray(shape.item_ids)
                else:
                    vertices=np.asarray(shape.geometry.verts,float).reshape(-1,3);triangles=np.asarray(shape.geometry.faces,np.uint64).reshape(-1,3);items=np.asarray(shape.geometry.item_ids)
                eligibility=geometry_eligibility(len(vertices),len(triangles))
                if eligibility['status']!='eligible':
                    failures.append({**record,'reason':'Source geometry resource eligibility failed','resource_eligibility':eligibility});continue
                if not len(triangles) or not np.isfinite(vertices).all():raise ValueError('Empty or nonfinite source geometry')
                normals=np.cross(vertices[triangles[:,1]]-vertices[triangles[:,0]],vertices[triangles[:,2]]-vertices[triangles[:,0]])
                if np.any(np.linalg.norm(normals,axis=1)==0):raise ValueError('Degenerate source triangles')
                elements.append({**record,'vertices':vertices.tolist(),'triangles':triangles.tolist(),'item_ids':items.tolist(),
                    'selected_representation_step_id':body[0].id() if body else None,'triangle_count':len(triangles),
                    'triangle_sha256':hashlib.sha256(np.ascontiguousarray(vertices[triangles],dtype='<f8').tobytes()).hexdigest()})
            except Exception as error:failures.append({**record,'reason':str(error)})
        frame=np.asarray(ifcopenshell.util.placement.get_local_placement(building.ObjectPlacement),float)
        frame[:3,3]*=ifcopenshell.util.unit.calculate_unit_scale(model)
        buildings.append({'source_building_global_id':building.GlobalId,'name':building.Name,'elements':elements,'omitted':omitted,'building_frame':frame.tolist()})
    return {'status':'passed' if buildings and not failures and all(b['elements'] for b in buildings) else 'failed',
        'input':str(Path(path).resolve()),'input_sha256':digest(Path(path)),'ifc_schema':model.schema,
        'length_unit_to_metre':ifcopenshell.util.unit.calculate_unit_scale(model),'buildings':buildings,'failures':failures,
        'graph':explicit_graph(model),'profile':profile}
