"""Measured, query-constrained simplification with explicit information loss."""
from dataclasses import dataclass,asdict
from copy import deepcopy
import math
import numpy as np
import manifold3d as m
from ifc_citygml.validation import validate_document
from ifc_citygml_lab.metrics import read_geometry,sampled_surface_distance,mesh_statistics
from .diagnostics import material_contains
from ifc_citygml_lab.fixtures import reference_mesh
from .checks import serialize

@dataclass(frozen=True)
class QueryContract:
    name:str='urban_visualisation'
    maximum_sampled_boundary_error_m:float=.1
    maximum_relative_volume_error:float=.05
    preserve_components:bool=True
    preserve_euler:bool=True
    protected_void_probes:tuple=()
    require_protected_void_reference:bool=False
    def __post_init__(self):
        if not self.name:raise ValueError('Named query contract required')
        for key in ['maximum_sampled_boundary_error_m','maximum_relative_volume_error']:
            v=getattr(self,key)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0:raise ValueError('Positive finite query budgets required')
        for key in ['preserve_components','preserve_euler','require_protected_void_reference']:
            if type(getattr(self,key)) is not bool:raise ValueError('Boolean query switches required')
        for point in self.protected_void_probes:
            if np.asarray(point).shape!=(3,) or not np.isfinite(point).all():raise ValueError('Finite 3D protected probes required')

def simplify(extraction,tolerance):
    result=deepcopy(extraction)
    for b in result['buildings']:
        for component in b['components']:
            if component['volume_m3']<=0:raise ValueError('Separate cavity-shell simplification is not qualified')
            vertices=np.asarray(component['vertices']);origin=vertices.mean(0);ids=np.asarray(component['triangle_source_ids']);faces=np.asarray(component['triangles'],np.uint64);order=np.argsort(ids,kind='stable');ids=ids[order];faces=faces[order]
            runs=[];offsets=[0];mapping={}
            for identity in dict.fromkeys(ids.tolist()):
                new=m.Manifold.reserve_ids(1);runs.append(new);mapping[new]=int(identity);offsets.append(offsets[-1]+int((ids==identity).sum())*3)
            mesh=m.Mesh64(np.ascontiguousarray(vertices-origin),np.ascontiguousarray(faces),run_index=np.array(offsets,np.uint64),run_original_id=np.array(runs,np.uint32),tolerance=0.)
            solid=m.Manifold(mesh)
            if solid.status()!=m.Error.NoError:raise ValueError('Simplification input is not a valid manifold')
            reduced=solid.simplify(tolerance);out=reduced.to_mesh64();newids=np.zeros(len(out.tri_verts),np.int64)
            for a,z,i in zip(out.run_index[:-1],out.run_index[1:],out.run_original_id):newids[int(a)//3:int(z)//3]=mapping[int(i)]
            component.update(vertices=(np.asarray(out.vert_properties)[:,:3]+origin).tolist(),triangles=np.asarray(out.tri_verts).tolist(),triangle_source_ids=newids.tolist(),triangle_semantics=['UnclassifiedBoundary']*len(newids),volume_m3=reduced.volume())
    return result

def blocks(extraction):
    result=deepcopy(extraction)
    for b in result['buildings']:
        points=np.vstack([c['vertices'] for c in b['components']]);lo,hi=points.min(0),points.max(0);w,d,h=hi-lo
        v,f=reference_mesh([{'kind':'box','box':(0,0,0,float(w),float(d),float(h))}],'rectangle',1.)
        b['derived_contributor_guids']=[r['ifc_global_id'] for r in b['sources'].values()]
        b['sources']={0:{'ifc_global_id':b['source_building_global_id'],'ifc_class':'IfcBuilding','step_id':None,'name':b['name'],'lineage_kind':'Derived bound from all selected source material; not original boundary attribution'}}
        b['components']=[{'vertices':(np.asarray(v)+lo).tolist(),'triangles':f,'triangle_source_ids':[0]*len(f),'triangle_semantics':['UnclassifiedBoundary']*len(f),'volume_m3':float(w*d*h)}]
    return result

def choose(result,contract=None):
    contract=contract or QueryContract()
    if result['status']!='accepted':return {'status':'source_conversion_not_accepted','selected':None,'candidates':[]},{}
    original=result['extraction'];profile=result['source_evidence']['profile'];original_data,_=serialize(original,profile);reference=read_geometry(original_data)
    base_stats=[mesh_statistics(c) for c in reference['components']];base_volume=sum(s['signed_volume_m3'] for s in base_stats);base_euler=sum(s['euler'] for s in base_stats)
    for p in contract.protected_void_probes:
        if material_contains(p,reference['components']):raise ValueError('A protected void probe lies inside the source material')
    generators=[('identity',lambda:deepcopy(original)),('block',lambda:blocks(original))]
    for factor in [.25,.5,1.]:
        tolerance=contract.maximum_sampled_boundary_error_m*factor;generators.append((f'simplify_{tolerance:g}m',lambda t=tolerance:simplify(original,t)))
    rows=[];outputs={}
    for name,generator in generators:
        try:
            extraction=generator();data,links=serialize(extraction,profile);mesh=read_geometry(data);stats=[mesh_statistics(c) for c in mesh['components']];volume=sum(s['signed_volume_m3'] for s in stats);distance=sampled_surface_distance(reference['mesh'],mesh['mesh'],512);validation=validate_document(data,1e-6)
            guards={'schema_and_surfaces':validation['status']=='passed','solid':validation.get('independent_general_solid_validation')=='passed',
                'sampled_boundary':distance['sampled_maximum_m']<=contract.maximum_sampled_boundary_error_m,'volume':abs(volume/base_volume-1)<=contract.maximum_relative_volume_error,
                'components':not contract.preserve_components or len(stats)==len(base_stats),'euler':not contract.preserve_euler or sum(s['euler'] for s in stats)==base_euler,
                'protected_void_probes':not any(material_contains(p,mesh['components']) for p in contract.protected_void_probes),
                'reference_available':not contract.require_protected_void_reference or bool(contract.protected_void_probes)}
            row={'name':name,'status':'admissible' if all(guards.values()) else 'not_admissible','guards':guards,'triangles':sum(s['triangles'] for s in stats),'bytes':len(data),
                'sampled_boundary_maximum_m':distance['sampled_maximum_m'],'relative_volume_error':volume/base_volume-1,'components':len(stats),'euler':sum(s['euler'] for s in stats),
                'information_loss':'Original boundary and element-level attribution replaced by building bounds' if name=='block' else 'Source geometric detail reduced; element identifiers retained through Manifold runs' if name!='identity' else 'None beyond accepted source conversion',
                'lineage_scope':'Building-level derived bounds' if name=='block' else 'Element-level source identifiers; not a one-to-one original triangle mapping'}
            outputs[name]={'data':data,'extraction':extraction,'source_links':links};rows.append(row)
        except Exception as error:rows.append({'name':name,'status':'unsupported_or_failed','error':repr(error)})
    admissible=[r for r in rows if r['status']=='admissible'];frontier=[]
    for r in admissible:
        values=lambda q:(q['triangles'],q['bytes'],q['sampled_boundary_maximum_m'],abs(q['relative_volume_error']))
        if not any(all(a<=b for a,b in zip(values(q),values(r))) and any(a<b for a,b in zip(values(q),values(r))) for q in admissible if q is not r):frontier.append(r['name'])
    selected=min(admissible,key=lambda r:(r['triangles'],r['bytes'],r['sampled_boundary_maximum_m']))['name'] if admissible else None
    return {'status':'selected' if selected else 'no_admissible_candidate','contract':asdict(contract),'selected':selected,'pareto_candidates':frontier,'candidates':rows,
        'evidence_level':'Measured finite samples, topology indicators and protected probes; no certified global error or complete opening-preservation guarantee'},outputs
