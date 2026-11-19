"""Read connection planes in product-local coordinates; logical edges never edit geometry."""
from copy import deepcopy
import numpy as np
import ifcopenshell
import ifcopenshell.util.placement as placement
import ifcopenshell.util.unit as unit
from shapely.geometry import MultiPoint

def connection_evidence(path):
    model=ifcopenshell.open(str(path));scale=unit.calculate_unit_scale(model);rows=[]
    for rel in model.by_type('IfcRelConnectsElements'):
        a,b=rel.RelatingElement,rel.RelatedElement;geometry=rel.ConnectionGeometry
        row={'relationship_guid':rel.GlobalId,'source':a.GlobalId,'target':b.GlobalId,'kind':'logical_connection_only','permits_geometry_edit':False}
        if geometry:
            row['connection_geometry_type']=geometry.is_a();row['kind']='unsupported_connection_geometry'
            if geometry.is_a('IfcConnectionSurfaceGeometry'):
                planes=[]
                for side,element in [('SurfaceOnRelatingElement',a),('SurfaceOnRelatedElement',b)]:
                    surface=getattr(geometry,side)
                    if surface is None:continue
                    if not surface.is_a('IfcPlane'):planes=[];break
                    matrix=np.asarray(placement.get_local_placement(element.ObjectPlacement))@np.asarray(placement.get_axis2placement(surface.Position))
                    planes.append({'origin_m':(matrix[:3,3]*scale).tolist(),'normal':(matrix[:3,2]/np.linalg.norm(matrix[:3,2])).tolist(),'side':side})
                if planes:
                    row.update(kind='supported_connection_plane',planes=planes,permits_geometry_edit=True,
                        interpretation='Source declares geometric interface plane; actual opposed source support and edit budget must still be checked')
        rows.append(row)
    return rows

def apply_connection_planes(source,connections,policy):
    result=deepcopy(source);elements={e['ifc_global_id']:e for b in result['buildings'] for e in b['elements']};ledger=[];unresolved=[]
    originals={k:np.array(e['vertices']) for k,e in elements.items()}
    for relation in connections:
        if not relation['permits_geometry_edit']:continue
        if relation['source'] not in elements or relation['target'] not in elements:
            unresolved.append({**relation,'reason':'Connection endpoint outside selected material representation'});continue
        first=relation['planes'][0];origin=np.asarray(first['origin_m']);normal=np.asarray(first['normal']);d=origin@normal
        if any(abs(np.dot(normal,p['normal']))<1-1e-10 or abs(np.dot(p['origin_m'],normal)-d)>policy.maximum_edit_m for p in relation['planes'][1:]):
            unresolved.append({**relation,'reason':'Conflicting source connection planes'});continue
        selections=[];centres=[];polygons=[]
        u=np.cross(normal,[0,0,1])
        if np.linalg.norm(u)<1e-8:u=np.cross(normal,[0,1,0])
        u/=np.linalg.norm(u);w=np.cross(normal,u)
        for guid in [relation['source'],relation['target']]:
            vertices=np.asarray(elements[guid]['vertices']);signed=(vertices-origin)@normal;mask=np.abs(signed)<=policy.maximum_edit_m
            if mask.sum()<3 or (signed.min()<-policy.maximum_edit_m and signed.max()>policy.maximum_edit_m):break
            poly=MultiPoint(np.column_stack([(vertices[mask]-origin)@u,(vertices[mask]-origin)@w])).convex_hull
            if poly.area<=1e-14:break
            selections.append((guid,vertices,signed,mask));centres.append(float(signed.mean()));polygons.append(poly)
        if len(selections)!=2 or centres[0]*centres[1]>=0 or polygons[0].intersection(polygons[1]).area<=1e-12:
            unresolved.append({**relation,'reason':'Opposed overlapping support faces not established'});continue
        proposed={guid:vertices.copy() for guid,vertices,signed,mask in selections}
        for guid,vertices,signed,mask in selections:proposed[guid][mask]-=signed[mask,None]*normal
        maximum=max(float(np.linalg.norm(proposed[k]-originals[k],axis=1).max()) for k in proposed)
        if maximum>policy.maximum_edit_m:
            unresolved.append({**relation,'reason':'Cumulative edit budget exceeded'});continue
        for guid,vertices,signed,mask in selections:
            elements[guid]['vertices']=proposed[guid].tolist();ledger.append({'source':guid,'operation':'project_declared_interface_vertices','relationship_guid':relation['relationship_guid'],
                'vertices_changed':int(mask.sum()),'maximum_vertex_change_from_original_m':float(np.linalg.norm(proposed[guid]-originals[guid],axis=1).max()),'plane':first})
    return result,ledger,unresolved
