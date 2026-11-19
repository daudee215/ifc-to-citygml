"""Explicit geometry candidates, source attribution, and guarded selection."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import time
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.placement
import ifcopenshell.util.unit
import ifcopenshell.guid
import manifold3d as manifold
import numpy as np
from lxml import etree as ET
from ifc_citygml.common import digest,load_profile
from ifc_citygml.envelope import oriented_source_solid,classify_surface,_host_guid
from ifc_citygml.exterior_writer import create_exterior_document
from ifc_citygml.georeferencing import prepare_profile
from ifc_citygml.validation import validate_document
from ifc_citygml.citygml_writer import NS,child,tag,format_points,SCHEMA_URL
from .contracts import Contract
from .evidence import explicit_graph,geometric_graph,correspondence_checks

BACKENDS={
    'world_grid':{'frame':'world','grid_m':1e-6,'manifold_tolerance_m':1e-6},
    'building_grid':{'frame':'building','grid_m':1e-6,'manifold_tolerance_m':1e-6},
    'unquantised':{'frame':'centred','grid_m':None,'manifold_tolerance_m':0.},
    'conditioned_grid':{'frame':'geometry','grid_m':1e-8,'manifold_tolerance_m':0.}}

def write_material_union(extraction,profile):
    root=ET.Element(tag('core','CityModel'),nsmap=NS);root.set(tag('gml','id'),'material_'+extraction['input_sha256'][:16])
    root.set(tag('xsi','schemaLocation'),f"{NS['bldg']} {SCHEMA_URL}")
    child(root,'gml','description','Experimental attributed material union in engineering metres; cavities retained; no independently interpreted exterior semantics or geographic accuracy.')
    links=[]
    for building in extraction['buildings']:
        identifier='b_'+ifcopenshell.guid.expand(building['source_building_global_id'])
        feature=child(child(root,'core','cityObjectMember'),'bldg','Building');feature.set(tag('gml','id'),identifier)
        child(feature,'gml','name',building['name'] or 'IFC building')
        multi=child(child(feature,'core','lod2MultiSurface'),'gml','MultiSurface',srsName=profile['srs_name'],srsDimension='3')
        contributions=[]
        for number,component in enumerate(building['components']):
            composite=child(child(multi,'gml','surfaceMember'),'gml','CompositeSurface');composite.set(tag('gml','id'),f'{identifier}_component_{number}')
            for i,(face,sid) in enumerate(zip(component['triangles'],component['triangle_source_ids'])):
                polygon_id=f'{identifier}_c{number}_t{i}'
                polygon=child(child(composite,'gml','surfaceMember'),'gml','Polygon');polygon.set(tag('gml','id'),polygon_id)
                linear=child(child(polygon,'gml','exterior'),'gml','LinearRing')
                ring=np.asarray(component['vertices'])[[*face,face[0]]]
                child(linear,'gml','posList',format_points(ring),srsDimension='3')
                source=building['sources'].get(sid,building['sources'].get(str(sid)))
                contributions.append({'polygon_id':polygon_id,'ifc_global_id':source['ifc_global_id'],'source_step_id':source['step_id'],
                    'source_ifc_class':source['ifc_class'],'component':number,'semantic_status':'unclassified_material_boundary',
                    'heuristic_hint':component['triangle_semantics'][i]})
        links.append({'citygml_id':identifier,'source_building_global_id':building['source_building_global_id'],
            'operation':'material_union_with_cavities_retained','surface_contributions':contributions,
            'information_loss':['Full IFC parametric history; use original IFC and ledger'],'semantic_claim':'No exterior boundary thematic labels inferred'})
    return ET.tostring(root,pretty_print=True,xml_declaration=True,encoding='UTF-8'),links

def engineering_profile(path):
    model=ifcopenshell.open(str(path));mapped=model.schema!='IFC2X3' and bool(model.by_type('IfcMapConversion'))
    return prepare_profile(load_profile('engineering-exterior' if mapped else 'exterior'),Path(path))

def extract_sources(path):
    model=ifcopenshell.open(str(path));settings=ifcopenshell.geom.settings();settings.set('use-world-coords',True);settings.set('convert-back-units',False)
    import ifcopenshell.util.geolocation as geo
    wcs=geo.get_wcs(model)
    if wcs is not None and not np.allclose(wcs,np.eye(4),atol=1e-12,rtol=0):
        raise ValueError('Nonidentity representation context is outside the tested extraction contract')
    profile=engineering_profile(path);buildings=[];failures=[]
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

def conditioned_frame(elements):
    points=np.vstack([e['vertices'] for e in elements]);origin=points.mean(axis=0);vectors=[]
    for element in elements:
        v=np.asarray(element['vertices']);f=np.asarray(element['triangles']);tri=v[f];normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
        for n in normal:
            if np.linalg.norm(n[:2])>1e-12 and abs(n[2])<1e-8*np.linalg.norm(n):vectors.append((np.linalg.norm(n),n/np.linalg.norm(n)))
    frame=np.eye(4)
    if vectors:
        n=max(vectors,key=lambda q:(round(q[0],8),round(abs(q[1][0]),8),round(abs(q[1][1]),8)))[1]
        yaw=np.arctan2(n[1],n[0]);c,s=np.cos(yaw),np.sin(yaw);frame[:3,:3]=[[c,-s,0],[s,c,0],[0,0,1]]
    local=(points-origin)@frame[:3,:3];frame[:3,3]=origin+local.min(axis=0)@frame[:3,:3].T
    return frame

def build_union(source,backend,contract):
    options=BACKENDS[backend];output=[];failures=[];changes=[];all_relations=[]
    for building in source['buildings']:
        elements=building['elements'];frame=np.eye(4)
        if options['frame']=='building':frame=np.asarray(building['building_frame'])
        elif options['frame']=='centred':frame[:3,3]=np.vstack([e['vertices'] for e in elements]).mean(axis=0)
        elif options['frame']=='geometry':frame=conditioned_frame(elements)
        if not np.allclose(frame[:3,:3].T@frame[:3,:3],np.eye(3),atol=1e-10,rtol=0):raise ValueError('Nonrigid frame')
        solids=[];sources={}
        for element in elements:
            vertices=np.asarray(element['vertices']);local=(vertices-frame[:3,3])@frame[:3,:3]
            grid=options['grid_m'];snapped=local.copy() if grid is None else np.round(local/grid)*grid
            move=float(np.linalg.norm(snapped-local,axis=1).max());sid=manifold.Manifold.reserve_ids(1)
            try:
                solid,repairs=oriented_source_solid(snapped,np.asarray(element['triangles'],np.uint64),np.asarray(element['item_ids']),sid,options['manifold_tolerance_m'])
                if solid.status()!=manifold.Error.NoError or solid.volume()<=0:raise ValueError(f'Invalid source solid: {solid.status()}')
                solids.append(solid);sources[sid]={k:v for k,v in element.items() if k not in ['vertices','triangles','item_ids']}
                sources[sid].update(maximum_grid_snap_displacement_m=move,source_repairs=repairs)
                changes.append({'source':element['ifc_global_id'],'operation':'no_quantisation' if grid is None else 'quantisation','frame':options['frame'],'grid_m':grid,'maximum_vertex_change_m':move})
            except Exception as error:failures.append({'source':element['ifc_global_id'],'stage':'source_solid','reason':str(error)})
        if not solids:continue
        union=manifold.Manifold.batch_boolean(solids,manifold.OpType.Add)
        if union.status()!=manifold.Error.NoError:failures.append({'building':building['source_building_global_id'],'stage':'union','reason':str(union.status())});continue
        components=[];minz=min(p[2] for e in elements for p in e['vertices'])
        for component in union.decompose():
            # Preserve cavities for the material-union contract. Do not fill them.
            mesh=component.to_mesh64();vertices=np.asarray(mesh.vert_properties)[:,:3]@frame[:3,:3].T+frame[:3,3];faces=np.asarray(mesh.tri_verts)
            ids=np.full(len(faces),-1,np.int64)
            for start,end,identity in zip(mesh.run_index[:-1],mesh.run_index[1:],mesh.run_original_id):ids[int(start)//3:int(end)//3]=identity
            if any(int(i) not in sources for i in ids):raise ValueError('Lost Boolean source attribution')
            semantics=[]
            for face,sid in zip(faces,ids):
                tri=vertices[face];n=np.cross(tri[1]-tri[0],tri[2]-tri[0]);length=np.linalg.norm(n)
                if length==0 or not np.isfinite(length):failures.append({'stage':'union','reason':'Degenerate output triangle'});semantics.append('invalid');continue
                semantics.append(classify_surface(sources[int(sid)],n/length,tri.mean(axis=0),minz,1e-6))
            components.append({'vertices':vertices.tolist(),'triangles':faces.tolist(),'triangle_source_ids':ids.tolist(),'triangle_semantics':semantics,'volume_m3':component.volume()})
        if not components:continue
        points=np.vstack([c['vertices'] for c in components]);output.append({'source_building_global_id':building['source_building_global_id'],'name':building['name'],
            'components':components,'sources':sources,'omitted':building['omitted'],'bounds_m':[points.min(axis=0).tolist(),points.max(axis=0).tolist()],
            'material_union_volume_m3':union.volume(),'outer_shell_volume_m3':union.volume(),'removed_enclosed_cavities':[],
            'removed_nested_positive_components':[],'enclosure_status':'material_union_no_envelope_claim',
            'semantic_policy':'Source class and normal heuristics; no independent semantic reference'})
        graph=geometric_graph(elements,contract.numerical_relation_tolerance_m);all_relations.append(graph)
    graph={'relations':[r for g in all_relations for r in g['relations']], 'status':'complete' if all(g['status']=='complete' for g in all_relations) else 'unresolved'}
    extraction={k:source[k] for k in ['input','input_sha256','ifc_schema','length_unit_to_metre']}
    extraction.update(status='passed' if output and not failures else 'failed',buildings=output,failures=failures,representation='material_union',
        geometry_policy='Selected source material union; cavities retained; no claim of an interpreted exterior building envelope',coordinate_frame='IFC world engineering metres')
    return extraction,graph,changes

def convert_research(path,backend='guarded',contract=None,source=None):
    contract=contract or Contract()
    if contract.target!='material_union':raise ValueError('This converter implements the material_union contract; use explicit source or block adapters for other targets')
    if contract.coordinate_policy!='engineering_only':raise ValueError('Use the separate audited coordinate-chain operation before geographic interpretation')
    start=time.perf_counter();source=extract_sources(Path(path)) if source is None else deepcopy(source)
    if source['input_sha256']!=digest(Path(path)):raise ValueError('Cached source hash mismatch')
    graph=source['graph'];attempts=[]
    result={'input':str(Path(path).resolve()),'input_sha256':source['input_sha256'],'contract':contract.to_dict(),'backend_requested':backend,
        'source_evidence':source,'status':'rejected','geometry_valid':False,'candidate_attempts':attempts,'experimental':True}
    if source['status']!='passed':result['reason']='Source extraction failed';return result,None
    candidates=['unquantised','conditioned_grid'] if backend=='guarded' else [backend]
    if any(name not in BACKENDS for name in candidates):raise ValueError('Unknown numerical backend')
    chosen=None
    for name in candidates:
        try:
            extraction,relations,changes=build_union(source,name,contract)
            record={'backend':name,'settings':BACKENDS[name],'changes':changes,'extraction':extraction,'relations':relations,'geometry_valid':False}
            if extraction['status']!='passed':record.update(status='rejected',reason='Source solid or union failure');attempts.append(record);continue
            data,links=write_material_union(extraction,source['profile']);validation=validate_document(data,contract.validator_snap_m)
            checks=correspondence_checks(extraction,relations)
            within_budget=all(c['maximum_vertex_change_m']<=contract.maximum_vertex_change_m for c in changes)
            valid=validation['status']=='passed' and (not contract.require_solid_diagnostic or validation.get('independent_general_solid_validation')=='passed')
            accepted=valid and within_budget and (not contract.require_source_relations or checks['status']=='passed' or (contract.allow_unresolved_contacts and not checks['violations']))
            record.update(status='accepted' if accepted else 'needs_review' if valid and within_budget and not checks['violations'] else 'rejected',
                validation=validation,correspondence=checks,within_change_budget=within_budget,geometry_valid=valid,source_links=links,
                output_sha256=hashlib.sha256(data).hexdigest())
            attempts.append(record)
            rank={'rejected':0,'needs_review':1,'accepted':2}
            if chosen is None or rank[record['status']]>rank[chosen[0]['status']]:chosen=(record,data)
            if accepted:break
        except Exception as error:attempts.append({'backend':name,'status':'rejected','geometry_valid':False,'reason':repr(error)})
    if chosen:
        record,data=chosen;result.update({k:record[k] for k in ['status','geometry_valid','extraction','validation','source_links','correspondence','output_sha256']})
        result['backend_selected']=record['backend'];graph['geometric_relations']=record['relations']['relations']
    else:data=None
    result['ledger']={'input_sha256':source['input_sha256'],'representation_contract':contract.to_dict(),'source_graph':graph,
        'operation':'Source attributed Boolean material union','semantic_status':'heuristic_not_independently_annotated',
        'coordinate_status':'engineering_only_no_geographic_accuracy','decision':result['status'],
        'limits':['Convex source correspondence uses floating point SAT and finite gap probes.','Fully hidden source contributions remain in the operation sources; absent exposed faces are not invented.']}
    result['wall_seconds']=time.perf_counter()-start
    return result,data
