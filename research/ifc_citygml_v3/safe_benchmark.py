"""Post-evaluation telemetry hardening; frozen conversion algorithms are unchanged."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import replace
import json,time
from ifc_citygml.common import digest,write_json,software_versions
from ifc_citygml_lab.geometry import extract_sources,convert_research
from ifc_citygml_lab.metrics import compare_export
from .converter import convert
from .policy import Policy
from .benchmark import algorithm_digest,ALGORITHM_FILES

def worker(job):
    case,output,policies=job;folder=Path(output);path=Path(case['input']);expected_path=path.with_suffix('.expected.json')
    if digest(path)!=case['input_sha256'] or digest(expected_path)!=case['expected_sha256']:raise ValueError('Registered source/reference changed')
    expected=json.loads(expected_path.read_text());source=extract_sources(path);rows=[]
    for method in ['v2_guarded','v3_no_repair','v3_constrained']:
        target=folder/method;target.mkdir(exist_ok=True);report=target/(path.stem+'.report.json');start=time.perf_counter();result=None
        row={'case':case['case'],'mechanism':case['mechanism'],'family':case['family'],'group':case['group'],'method':method,'status':'execution_failed','geometry_valid':False,'reference_passed':False,'input_sha256':digest(path),'report':report.relative_to(folder).as_posix()}
        try:
            result,data=convert_research(path,source=source) if method=='v2_guarded' else convert(path,Policy.from_dict(policies[method]),source=source)
            row.update(status=result['status'],conversion_status=result['status'],geometry_valid=result['geometry_valid'])
            if data:
                gml=target/(path.stem+'.'+result['status']+'.gml');gml.write_bytes(data);row.update(output=gml.relative_to(folder).as_posix(),output_sha256=digest(gml))
                try:
                    metrics=compare_export(data,expected,256);row.update(metrics=metrics,reference_passed=result['geometry_valid'] and metrics['all_guards_passed'])
                except Exception as error:row.update(status='execution_failed',failed_stage='reference_measurement',error=repr(error))
        except Exception as error:row.update(status='execution_failed',failed_stage='conversion',error=repr(error))
        row['wall_seconds']=time.perf_counter()-start
        if result is None:result={'input':str(path),'source_evidence':source,'error':row.get('error')}
        result['summary']=row;write_json(report,result);rows.append(row)
    return rows

def run(manifest_path,output,workers=3,evaluation_role='Registered partition; independence depends on prior inspection and study protocol'):
    folder=Path(output)
    if folder.exists():raise FileExistsError('Use a new experiment directory')
    folder.mkdir(parents=True);manifest_path=Path(manifest_path);manifest=json.loads(manifest_path.read_text());policy=Policy();rows=[]
    policies={'v3_no_repair':replace(policy,permit_connection_plane_repairs=False).to_dict(),'v3_constrained':policy.to_dict()}
    snapshot=folder/'code_snapshot';snapshot.mkdir()
    for name in [*ALGORITHM_FILES,'safe_benchmark.py']:(snapshot/name).write_bytes((Path(__file__).parent/name).read_bytes())
    protocol={'manifest':str(manifest_path.resolve()),'manifest_sha256':digest(manifest_path),'algorithm_sha256':algorithm_digest(),'telemetry_sha256':digest(Path(__file__)),'partition':manifest['partition'],'evaluation_role':evaluation_role,'policies':policies,'software':software_versions(),'reference_samples':256}
    write_json(folder/'PROTOCOL.json',protocol);start=time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs={pool.submit(worker,(case,str(folder),policies)):case for case in manifest['cases']}
        for future in as_completed(jobs):
            case=jobs[future]
            try:rows.extend(future.result())
            except Exception as error:
                for method in policies.keys()|{'v2_guarded'}:
                    path=folder/method/(case['case']+'.report.json');path.parent.mkdir(exist_ok=True);row={'case':case['case'],'mechanism':case['mechanism'],'family':case['family'],'group':case['group'],'method':method,'status':'execution_failed','failed_stage':'source_extraction_or_worker','geometry_valid':False,'reference_passed':False,'error':repr(error),'input_sha256':case['input_sha256'],'report':path.relative_to(folder).as_posix()};write_json(path,{'summary':row});rows.append(row)
            rows.sort(key=lambda r:(r['case'],r['method']));write_json(folder/'index.json',{'status':'running','cases':rows})
    if algorithm_digest()!=protocol['algorithm_sha256'] or digest(Path(__file__))!=protocol['telemetry_sha256']:raise ValueError('Code changed during run')
    result={'status':'completed','attempts':len(rows),'wall_seconds':time.perf_counter()-start,'cases':rows,'evaluation_role':evaluation_role};write_json(folder/'index.json',result);write_json(folder/'COMPLETE.json',{'index_sha256':digest(folder/'index.json'),'protocol_sha256':digest(folder/'PROTOCOL.json')});return result
