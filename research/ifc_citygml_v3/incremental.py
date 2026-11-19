"""Conservative building-level reuse with source and dependency invalidation."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,time
import ifcopenshell
from ifc_citygml.common import write_json,digest
from ifc_citygml.validation import validate_document
from ifc_citygml_lab.geometry import extract_sources
from .connections import connection_evidence
from .converter import convert
from .checks import serialize
from .interactions import interaction_pairs
from .policy import Policy
from .benchmark import algorithm_digest

def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def element_records(source):return {e['ifc_global_id']:{'building':b['source_building_global_id'],'element':e} for b in source['buildings'] for e in b['elements']}
def canonical_geometry(extraction):
    rows=[]
    for b in extraction.get('buildings',[]):
        for c in b['components']:
            v=c['vertices']
            for face,sid in zip(c['triangles'],c['triangle_source_ids']):
                source=b['sources'].get(sid,b['sources'].get(str(sid)))['ifc_global_id'];points=[tuple(format(float(x),'.17g') for x in v[i]) for i in face]
                triangle=min(tuple(points[i:]+points[:i]) for i in range(3));rows.append((b['source_building_global_id'],source,triangle))
    return fingerprint(sorted(rows))

def update(path,cache_path,policy=None,verify_rebuild=True):
    path=Path(path);cache_path=Path(cache_path);policy=policy or Policy();started=time.perf_counter();source=extract_sources(path);connections=connection_evidence(path)
    prior=json.loads(cache_path.read_text()) if cache_path.exists() else {};old=prior.get('elements',{});new=element_records(source)
    model=ifcopenshell.open(str(path));mapping=[] if model.schema=='IFC2X3' else [str(r) for r in model.by_type('IfcMapConversion')]+[str(r) for r in model.by_type('IfcProjectedCRS')]
    global_hash=fingerprint({'policy':policy.to_dict(),'profile':source['profile'],'units':source['length_unit_to_metre'],'schema':source['ifc_schema'],'map_metadata':mapping,'algorithm':algorithm_digest(),'incremental_source_sha256':digest(Path(__file__))})
    changed={k for k in old.keys()|new.keys() if k not in old or k not in new or fingerprint(old[k])!=fingerprint(new[k])}
    if prior.get('global_hash')!=global_hash:changed=set(old)|set(new)
    adjacency={k:set() for k in set(old)|set(new)};index_status=[]
    for records in [old,new]:
        items=[r['element'] for r in records.values()];broad=interaction_pairs(items,policy.maximum_edit_m,policy.maximum_interaction_pairs);index_status.append(broad['status'])
        if broad['status']!='complete':changed=set(adjacency);continue
        for i,j in broad['pairs']:
            a,b=items[i]['ifc_global_id'],items[j]['ifc_global_id'];adjacency[a].add(b);adjacency[b].add(a)
    connection_changed=prior.get('connections')!=connections
    for c in [*prior.get('connections',[]),*connections]:
        a,b=c['source'],c['target']
        if a in adjacency and b in adjacency:adjacency[a].add(b);adjacency[b].add(a)
        if connection_changed:changed.update([a,b])
    dependent=set(changed);queue=list(changed)
    while queue:
        for neighbour in adjacency.get(queue.pop(),set())-dependent:dependent.add(neighbour);queue.append(neighbour)
    affected={r['building'] for k,r in {**old,**new}.items() if k in dependent};cache={};recomputed=[];reused=[];results=[]
    cross_building=any(c['source'] in new and c['target'] in new and new[c['source']]['building']!=new[c['target']]['building'] for c in connections)
    if cross_building or connections and len(source['buildings'])>1 or source['status']!='passed':
        result,data=convert(path,policy,source);result['incremental']={'strategy':'full_rebuild_fallback','reason':'Cross-building connections or source extraction failure','reused_buildings':[],'recomputed_buildings':[b['source_building_global_id'] for b in source['buildings']]};return result,data
    for building in source['buildings']:
        key=building['source_building_global_id'];local_connections=[c for c in connections if c['source'] in {e['ifc_global_id'] for e in building['elements']}]
        key_hash=fingerprint({'building':building,'connections':local_connections,'global':global_hash})
        previous=prior.get('buildings',{}).get(key)
        if previous and previous['fingerprint']==key_hash and key not in affected:
            r=previous['result'];reused.append(key)
        else:
            subset=deepcopy(source);subset['buildings']=[building];r,_=convert(path,policy,subset);recomputed.append(key)
        cache[key]={'fingerprint':key_hash,'result':r,'origin_input_sha256':r['input_sha256']};results.append(r)
    result={'input':str(path.resolve()),'input_sha256':digest(path),'policy':policy.to_dict(),'source_evidence':source,'connections':connections,'experimental':True}
    rank={'rejected':0,'needs_review':1,'accepted':2};result['status']=min((r['status'] for r in results),key=lambda s:rank[s]) if results else 'rejected';result['geometry_valid']=all(r['geometry_valid'] for r in results)
    result['extraction']={k:source[k] for k in ['input','input_sha256','ifc_schema','length_unit_to_metre']};result['extraction'].update(buildings=[b for r in results for b in r.get('extraction',{}).get('buildings',[])],status='passed' if results and all('extraction' in r for r in results) else 'failed')
    data=None
    if result['extraction']['buildings']:
        data,links=serialize(result['extraction'],source['profile']);result['source_links']=links;result['validation']=validate_document(data,1e-6)
        if result['validation']['status']!='passed':result['status']='rejected';result['geometry_valid']=False
    elapsed=time.perf_counter()-started
    record={'strategy':'building_level_boolean_reuse','changed_source_elements':sorted(changed),'dependent_source_elements':sorted(dependent),'recomputed_buildings':recomputed,'reused_buildings':reused,
        'incremental_wall_seconds_before_rebuild_check':elapsed,'verification_status':'not_requested','invalidation_index_status':index_status,'cache_origin_input_hashes':{k:v['origin_input_sha256'] for k,v in cache.items()}}
    if verify_rebuild:
        start=time.perf_counter();full,full_data=convert(path,policy,source);equivalent=canonical_geometry(result['extraction'])==canonical_geometry(full.get('extraction',{})) and result['status']==full['status']
        record.update(verification_status='passed' if equivalent else 'mismatch_full_rebuild_returned',full_rebuild_wall_seconds=time.perf_counter()-start,canonical_geometry_and_lineage_equal=equivalent)
        if not equivalent:result,data=full,full_data
    result['incremental']=record;result['wall_seconds']=time.perf_counter()-started
    write_json(cache_path,{'version':1,'global_hash':global_hash,'elements':new,'connections':connections,'buildings':cache,'last_input_sha256':digest(path)})
    return result,data
