"""Frozen V3 comparisons with corrected truth and no holdout-guided selection."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import replace
import hashlib,json,time
import psutil
from ifc_citygml.common import digest,write_json,software_versions
from ifc_citygml_lab.geometry import extract_sources,convert_research
from ifc_citygml_lab.metrics import compare_export
from .converter import convert
from .policy import Policy

ALGORITHM_FILES=['__init__.py','policy.py','connections.py','interactions.py','checks.py','converter.py','references.py','fixtures.py','benchmark.py']
def algorithm_digest():
    h=hashlib.sha256()
    for name in ALGORITHM_FILES:h.update(name.encode());h.update((Path(__file__).parent/name).read_bytes())
    return h.hexdigest()

def worker(job):
    case,output,policies=job;folder=Path(output);path=Path(case['input']);expected_path=path.with_suffix('.expected.json')
    if digest(path)!=case['input_sha256'] or digest(expected_path)!=case['expected_sha256']:raise ValueError('Registered input/reference changed')
    expected=json.loads(expected_path.read_text());source=extract_sources(path);rows=[]
    for method in ['v2_guarded','v3_no_repair','v3_constrained']:
        start=time.perf_counter();target=folder/method;target.mkdir(exist_ok=True)
        try:
            if method=='v2_guarded':result,data=convert_research(path,source=source)
            else:result,data=convert(path,Policy.from_dict(policies[method]),source=source)
            row={'case':case['case'],'mechanism':case['mechanism'],'family':case['family'],'group':case['group'],'method':method,'status':result['status'],'geometry_valid':result['geometry_valid'],'reference_passed':False,'input_sha256':digest(path)}
            if data:
                gml=target/(path.stem+'.'+result['status']+'.gml');gml.write_bytes(data);row['output']=gml.relative_to(folder).as_posix();row['output_sha256']=digest(gml)
                row['metrics']=compare_export(data,expected,256);row['reference_passed']=row['geometry_valid'] and row['metrics']['all_guards_passed']
            row['wall_seconds']=time.perf_counter()-start;row['worker_rss_at_completion_bytes']=psutil.Process().memory_info().rss
            row['report']=(target/(path.stem+'.report.json')).relative_to(folder).as_posix();result['summary']=row;write_json(folder/row['report'],result)
        except Exception as error:row={'case':case['case'],'mechanism':case['mechanism'],'family':case['family'],'group':case['group'],'method':method,'status':'execution_failed','geometry_valid':False,'reference_passed':False,'error':repr(error),'wall_seconds':time.perf_counter()-start}
        rows.append(row)
    return rows

def run(manifest_path,output,workers=3):
    folder=Path(output)
    if folder.exists():raise FileExistsError('Experiments are immutable; use a fresh output directory')
    folder.mkdir(parents=True);manifest_path=Path(manifest_path);manifest=json.loads(manifest_path.read_text());policy=Policy()
    snapshot=folder/'code_snapshot';snapshot.mkdir()
    for name in ALGORITHM_FILES:(snapshot/name).write_bytes((Path(__file__).parent/name).read_bytes())
    policies={'v3_no_repair':replace(policy,permit_connection_plane_repairs=False).to_dict(),'v3_constrained':policy.to_dict()}
    protocol={'manifest':str(manifest_path.resolve()),'manifest_sha256':digest(manifest_path),'algorithm_sha256':algorithm_digest(),'partition':manifest['partition'],'policies':policies,'software':software_versions(),
        'methods':['v2_guarded','v3_no_repair','v3_constrained'],'reference_samples_each_direction_maximum':256,'evaluation_role':'Fresh mechanism holdout' if manifest['partition']=='holdout' else 'Development',
        'claim_limits':'Related analytic controls; not independent buildings. No semantic or geographic accuracy inferred.'}
    write_json(folder/'PROTOCOL.json',protocol);rows=[];start=time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs={pool.submit(worker,(case,str(folder),policies)):case for case in manifest['cases']}
        for future in as_completed(jobs):
            case=jobs[future]
            try:rows.extend(future.result())
            except Exception as error:
                rows.extend({'case':case['case'],'mechanism':case['mechanism'],'family':case['family'],'group':case['group'],'method':m,'status':'execution_failed','geometry_valid':False,'reference_passed':False,'error':repr(error)} for m in protocol['methods'])
            rows.sort(key=lambda r:(r['case'],r['method']));write_json(folder/'index.json',{'status':'running','planned_attempts':len(manifest['cases'])*3,'completed_attempts':len(rows),'cases':rows})
            if len(rows)%30==0:print('Completed',len(rows),'/',len(manifest['cases'])*3,flush=True)
    if algorithm_digest()!=protocol['algorithm_sha256']:raise ValueError('Algorithm changed during evaluation; do not label run frozen')
    result={'status':'completed','attempts':len(rows),'partition':manifest['partition'],'wall_seconds':time.perf_counter()-start,'cases':rows}
    write_json(folder/'index.json',result);write_json(folder/'COMPLETE.json',{'index_sha256':digest(folder/'index.json'),'protocol_sha256':digest(folder/'PROTOCOL.json')});return result
