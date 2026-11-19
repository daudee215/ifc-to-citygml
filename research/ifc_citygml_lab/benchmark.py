"""Checkpointed immutable experiments with isolated process workers."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import time
from ifc_citygml.common import digest,write_json,code_digest,software_versions
from .contracts import Contract
from .geometry import extract_sources,convert_research,write_material_union
from .metrics import compare_export

def research_digest():
    h=hashlib.sha256()
    for name in ['contracts.py','evidence.py','geometry.py','fixtures.py','metrics.py','benchmark.py']:
        path=Path(__file__).parent/name;h.update(name.encode());h.update(path.read_bytes())
    return h.hexdigest()

def _worker(job):
    case,backends,output,contract_data,samples=job;folder=Path(output);source_path=Path(case['input']);contract=Contract.from_dict(contract_data)
    if digest(source_path)!=case['input_sha256']:raise ValueError('Input hash changed')
    expected_path=source_path.with_suffix('.expected.json')
    if digest(expected_path)!=case['expected_sha256']:raise ValueError('Reference hash changed')
    expected=json.loads(expected_path.read_text());source=extract_sources(source_path);rows=[]
    for backend in backends:
        target=folder/backend;target.mkdir(exist_ok=True);report_path=target/(case['case']+'.report.json')
        if report_path.exists():
            report=json.loads(report_path.read_text());brief=report['summary']
            if brief['input_sha256']!=case['input_sha256']:raise ValueError('Resume source mismatch')
            if report.get('output_file') and digest(target/report['output_file'])!=report['output_sha256']:raise ValueError('Resume output changed')
            rows.append(brief);continue
        started=time.perf_counter()
        try:
            result,data=convert_research(source_path,backend,contract,source)
            row={'case':case['case'],'family':case['family'],'group':case['group'],'backend':backend,'input_sha256':case['input_sha256'],
                'status':result['status'],'geometry_valid':result['geometry_valid'],'reference_all_guards':False,
                'report':str(report_path.relative_to(folder)),'units':expected['units']}
            if data:
                suffix='.gml' if result['status']=='accepted' else '.review.gml' if result['status']=='needs_review' else '.rejected.gml'
                path=target/(case['case']+suffix);path.write_bytes(data);result['output_file']=path.name
                result['output_sha256']=digest(path);measurements=compare_export(data,expected,samples);row['metrics']=measurements
                row['reference_all_guards']=result['geometry_valid'] and measurements['all_guards_passed']
                row['output_file']=str(path.relative_to(folder));row['output_sha256']=result['output_sha256']
            for number,attempt in enumerate(result['candidate_attempts']):
                if 'validation' not in attempt:continue
                candidate,_=write_material_union(attempt['extraction'],source['profile'])
                path=target/(case['case']+f'.attempt{number}.{attempt["backend"]}.candidate.gml');path.write_bytes(candidate)
                attempt['candidate_file']=path.name
                if digest(path)!=attempt['output_sha256']:raise ValueError('Candidate serialization hash mismatch')
            row['wall_seconds']=time.perf_counter()-started
            try:
                import psutil
                row['worker_rss_bytes']=psutil.Process().memory_info().rss
                row['memory_measure']='Process resident memory at completion; not peak RSS'
            except ImportError:row['memory_measure']='Unavailable; peak RSS not measured'
            result['summary']=row;write_json(report_path,result);rows.append(row)
        except Exception as error:
            row={'case':case['case'],'family':case['family'],'group':case['group'],'backend':backend,'input_sha256':case['input_sha256'],
                'status':'execution_failed','geometry_valid':False,'reference_all_guards':False,'error':repr(error),
                'report':str(report_path.relative_to(folder)),'wall_seconds':time.perf_counter()-started}
            write_json(report_path,{'summary':row,'error':repr(error)});rows.append(row)
    return rows

def run(manifest_path,output,backends=None,workers=2,surface_samples=128):
    manifest_path=Path(manifest_path).resolve();folder=Path(output).resolve();manifest=json.loads(manifest_path.read_text())
    backends=backends or ['world_grid','building_grid','unquantised','conditioned_grid','guarded']
    folder.mkdir(parents=True,exist_ok=True);protocol_path=folder/'PROTOCOL.json'
    if (folder/'COMPLETE.json').exists():raise FileExistsError('Completed experiment is immutable')
    settings={'manifest_sha256':digest(manifest_path),'research_source_sha256':research_digest(),'frozen_converter_sha256':code_digest(),
        'backends':backends,'surface_samples_per_direction':surface_samples,'contract':Contract().to_dict()}
    if protocol_path.exists():
        old=json.loads(protocol_path.read_text())
        if old['settings']!=settings:raise ValueError('Resume protocol differs; use a new output folder')
    else:write_json(protocol_path,{'created_utc':datetime.now(timezone.utc).isoformat(),'manifest':str(manifest_path),'settings':settings,
        'partition':manifest['partition'],'software':software_versions(),'oracle_policy':'References used only after conversion and selection, never as candidate inputs',
        'sampling_limit':manifest['sampling_note'],'workers':workers,'scope':'Experimental material union profiles; no independent semantic or surveyed geographic validation'})
    lock=folder/'RUNNING.lock'
    descriptor=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(descriptor,str(os.getpid()).encode());os.close(descriptor)
    rows=[];start=time.perf_counter()
    try:
        jobs=[(case,backends,str(folder),settings['contract'],surface_samples) for case in manifest['cases']]
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures={executor.submit(_worker,job):job[0] for job in jobs}
            for future in as_completed(futures):
                rows.extend(future.result());rows.sort(key=lambda r:(r['case'],r['backend']))
                write_json(folder/'index.json',{'status':'running','completed_attempts':len(rows),'planned_attempts':len(jobs)*len(backends),'cases':rows})
                if len(rows)%max(len(backends)*5,1)==0:print(json.dumps({'completed':len(rows),'planned':len(jobs)*len(backends)}),flush=True)
        summary={'status':'completed','attempts':len(rows),'geometry_valid':sum(r['geometry_valid'] for r in rows),
                 'reference_all_guards':sum(r['reference_all_guards'] for r in rows),'wall_seconds':time.perf_counter()-start,'cases':rows}
        write_json(folder/'index.json',summary);write_json(folder/'COMPLETE.json',{'index_sha256':digest(folder/'index.json'),'settings':settings})
        return summary
    finally:
        lock.unlink(missing_ok=True)
