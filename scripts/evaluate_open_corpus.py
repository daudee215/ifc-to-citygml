"""Bounded applicability trials on six newly acquired, licensed IFCs."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
from ifc_citygml.common import digest,write_json
from ifc_citygml_lab.benchmark import research_digest

def worker(path,output):
    from ifc_citygml_lab.geometry import convert_research
    try:
        result,data=convert_research(path)
        if data:
            gml=output.with_suffix('.'+result['status']+'.gml');gml.write_bytes(data)
        write_json(output,result)
    except Exception as error:write_json(output,{'status':'unsupported_or_failed','error':repr(error),'input_sha256':digest(path)})

def job(path):
    output=ROOT/'results/expansion_v2/open_applicability'/(path.parent.name+'_'+path.stem+'.json');start=time.perf_counter()
    try:
        process=subprocess.run([sys.executable,__file__,'--worker',str(path),str(output)],capture_output=True,text=True,timeout=120)
        result=json.loads(output.read_text()) if output.exists() else {'status':'execution_failed','error':process.stderr[-2000:]}
        row={'input':path.relative_to(ROOT).as_posix(),'input_sha256':digest(path),'report':output.relative_to(ROOT).as_posix(),'status':result['status'],'geometry_valid':result.get('geometry_valid',False)}
    except subprocess.TimeoutExpired:row={'input':path.relative_to(ROOT).as_posix(),'status':'timeout_120s','input_sha256':digest(path)}
    row['wall_seconds']=time.perf_counter()-start;print(row['input'],row['status'],flush=True);return row

if __name__=='__main__':
    if len(sys.argv)>1:worker(Path(sys.argv[2]),Path(sys.argv[3]))
    else:
        folder=ROOT/'results/expansion_v2/open_applicability';folder.mkdir(parents=True,exist_ok=False)
        paths=sorted((ROOT/'data/raw/open_corpus/6685810').glob('*.ifc'))+sorted((ROOT/'data/raw/open_corpus/6397164').glob('*.ifc'))
        write_json(folder/'PLAN.json',{'cases':[{'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p)} for p in paths],'research_code_sha256':research_digest(),'timeout_seconds_per_case':120,'task':'Engineering material-union applicability, not independent semantic or geographic accuracy','license':'CC-BY-4.0'})
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(job,paths))
        write_json(folder/'index.json',{'status':'completed','cases':rows,'independent_accuracy_reference':False})
