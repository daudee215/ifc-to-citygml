from pathlib import Path
from copy import deepcopy
import hashlib,time
import numpy as np
from ifc_citygml.common import digest
from ifc_citygml.validation import validate_document
from ifc_citygml_lab.geometry import extract_sources,build_union
from ifc_citygml_lab.contracts import Contract
from .policy import Policy
from .connections import connection_evidence,apply_connection_planes
from .interactions import relation_evidence
from .checks import serialize,verification

def convert(path,policy=None,source=None):
    path=Path(path);policy=policy or Policy();start=time.perf_counter();source=deepcopy(source) if source is not None else extract_sources(path)
    if source['input_sha256']!=digest(path):raise ValueError('Cached source changed')
    connections=connection_evidence(path);result={'input':str(path.resolve()),'input_sha256':digest(path),'policy':policy.to_dict(),'status':'rejected','geometry_valid':False,
        'source_evidence':source,'connections':connections,'candidates':[],'experimental':True,'semantic_reference':'not independently reviewed','geographic_accuracy':'not established'}
    if source['status']!='passed':result['reason']='Source extraction failed';return result,None
    original_relations={b['source_building_global_id']:relation_evidence(b['elements'],policy,[]) for b in source['buildings']}
    variants=[('source_geometry',source,[],[])]
    if policy.permit_connection_plane_repairs and any(c['permits_geometry_edit'] for c in connections):
        repaired,edits,unresolved=apply_connection_planes(source,connections,policy);variants.append(('connection_plane_projection',repaired,edits,unresolved))
    chosen=None;rank={'rejected':0,'needs_review':1,'accepted':2}
    for operation,working,edits,repair_unknown in variants:
        for backend in ['unquantised','conditioned_grid']:
            record={'operation':operation,'backend':backend,'edits':edits,'repair_unknown':repair_unknown,'status':'rejected'}
            try:
                contract=Contract(maximum_vertex_change_m=policy.maximum_edit_m,numerical_relation_tolerance_m=policy.numerical_floor_m)
                extraction,legacy,changes=build_union(working,backend,contract)
                record.update(extraction=extraction,changes=changes,legacy_relation_status=legacy['status'])
                if extraction['status']!='passed':record['reason']='Invalid source solid or union';result['candidates'].append(record);continue
                perbuilding=[relation_evidence(b['elements'],policy,connections) for b in working['buildings']]
                relations={'status':'complete' if all(r['status']=='complete' for r in perbuilding) else 'unresolved','relations':[r for g in perbuilding for r in g['relations']],
                    'ambiguities':[r for g in perbuilding for r in g['ambiguities']],'broad_phase':[r['broad_phase'] for r in perbuilding]}
                data,links=serialize(extraction,working['profile']);validation=validate_document(data,1e-6);checks=verification(working,extraction,data,relations,connections,policy)
                protected_violations=[]
                after={frozenset((r['source'],r['target'])):r for r in relations['relations']};asserted={frozenset((r['source'],r['target'])) for r in connections if r['kind']=='supported_connection_plane'}
                for g in original_relations.values():
                    for r in g['relations']:
                        key=frozenset((r['source'],r['target']));new=after.get(key)
                        if key not in asserted and r.get('separating_axis_gap_m',0)>policy.numerical_floor_m and new and new.get('separating_axis_gap_m',0)<=policy.numerical_floor_m:
                            protected_violations.append({'kind':'unasserted_source_gap_removed','before':r,'after':new})
                maximum=max([c['maximum_vertex_change_m'] for c in changes]+[0.])+max([e['maximum_vertex_change_from_original_m'] for e in edits]+[0.])
                valid=validation['status']=='passed' and (not policy.require_solid or validation.get('independent_general_solid_validation')=='passed')
                rejected=not valid or maximum>policy.maximum_edit_m or bool(checks['violations']) or bool(protected_violations)
                status='rejected' if rejected else 'needs_review' if checks['status']!='passed' or repair_unknown else 'accepted'
                record.update(status=status,geometry_valid=valid,validation=validation,verification=checks,relations=relations,protected_gap_violations=protected_violations,
                    maximum_total_edit_bound_m=maximum,source_links=links,output_sha256=hashlib.sha256(data).hexdigest())
                result['candidates'].append(record)
                if chosen is None or rank[status]>rank[chosen[0]['status']]:chosen=(record,data)
            except Exception as error:record['reason']=repr(error);result['candidates'].append(record)
    if chosen:
        c,data=chosen;result.update({k:c[k] for k in ['status','geometry_valid','extraction','source_links','verification','output_sha256']});result['selected']={'operation':c['operation'],'backend':c['backend']}
        result['operation_ledger']=c['edits'];result['relations']=c['relations']
    else:data=None
    result['wall_seconds']=time.perf_counter()-start;return result,data
