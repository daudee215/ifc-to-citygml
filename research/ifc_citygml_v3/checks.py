"""Operational checks use represented sources; never consult analytical design truth."""
import numpy as np
from lxml import etree as ET
from ifc_citygml_lab.geometry import write_material_union
from ifc_citygml_lab.metrics import read_geometry,sampled_surface_distance,mesh_statistics
from ifc_citygml_lab.evidence import correspondence_checks

def serialize(extraction,profile):
    data,links=write_material_union(extraction,profile);root=ET.fromstring(data)
    rings=root.findall('.//{http://www.opengis.net/gml/3.2}posList')
    triangles=[np.asarray(c['vertices'])[[*f,f[0]]] for b in extraction['buildings'] for c in b['components'] for f in c['triangles']]
    if len(rings)!=len(triangles):raise ValueError('Lost serialized face correspondence')
    for node,points in zip(rings,triangles):node.text=' '.join(format(float(x),'.17g') for x in points.flat)
    return ET.tostring(root,pretty_print=True,xml_declaration=True,encoding='UTF-8'),links

def serialization_check(extraction,data):
    output=read_geometry(data);actual=np.vstack([np.asarray(c['vertices'])[c['triangles']] for c in output['components']])
    expected=np.vstack([np.asarray(c['vertices'])[c['triangles']] for b in extraction['buildings'] for c in b['components']])
    if expected.shape!=actual.shape:return {'status':'failed','reason':'Triangle count changed in serialization'}
    change=float(np.linalg.norm(actual-expected,axis=2).max())
    return {'status':'passed' if np.array_equal(actual,expected) else 'failed','maximum_coordinate_roundtrip_change_m':change,'decimal_significant_digits':17,'property':'Exact roundtrip of IEEE input coordinates; not exact rational Boolean construction'}

def verification(source,extraction,data,relations,connections,policy):
    checks=correspondence_checks(extraction,{'relations':relations['relations'],'status':relations['status']})
    serialization=serialization_check(extraction,data);violations=list(checks['violations']);unknown=list(checks['unresolved']);single=[]
    exported=read_geometry(data)
    for building in source['buildings']:
        if len(building['elements'])==1 and len(source['buildings'])==1:
            element=building['elements'][0]
            distance=sampled_surface_distance(element,exported['mesh'],512);single.append(distance)
            if distance['sampled_maximum_m']>policy.source_boundary_distance_m:violations.append({'kind':'single_source_boundary_loss','measurement':distance})
    memberships={}
    for number,(b,c) in enumerate((b,c) for b in extraction['buildings'] for c in b['components']):
        for sid in c['triangle_source_ids']:
            e=b['sources'].get(sid,b['sources'].get(str(sid)));memberships.setdefault(e['ifc_global_id'],set()).add(number)
    source_elements={e['ifc_global_id']:e for b in source['buildings'] for e in b['elements']}
    for connection in connections:
        if connection['kind']!='supported_connection_plane':continue
        ids=[connection['source'],connection['target']]
        if not all(i in source_elements for i in ids):unknown.append({'kind':'connection_outside_selected_scope','connection':connection});continue
        p=connection['planes'][0];o=np.array(p['origin_m']);n=np.array(p['normal'])
        near=[float(np.abs((np.asarray(source_elements[i]['vertices'])-o)@n).min()) for i in ids]
        if max(near)>policy.numerical_floor_m:violations.append({'kind':'declared_interface_not_met','nearest_source_plane_distance_m':near,'connection':connection})
        a,b=[memberships.get(i,set()) for i in ids]
        if a and b and not a.intersection(b):violations.append({'kind':'declared_contact_disconnected','connection':connection})
        elif not a or not b:unknown.append({'kind':'declared_contact_not_exposed','connection':connection})
    if serialization['status']!='passed':violations.append({'kind':'serialization_changed_geometry','check':serialization})
    return {'status':'failed' if violations else 'unresolved' if unknown or relations['status']!='complete' else 'passed','violations':violations,'unresolved':unknown,
        'serialization':serialization,'single_source_boundary_checks':single,'mesh_components':[mesh_statistics(c) for c in exported['components']],
        'limits':'Finite source-boundary sampling and convex contact hypotheses; not a complete volumetric equivalence certificate'}
