"""Resource-guarded follow-up; all reused external models are development evidence."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
from ifc_citygml.common import write_json,digest
def worker(path,out):
    from ifc_citygml_v3.source43 import extract_sources
    from ifc_citygml_v3.converter import convert
    try:
        source=extract_sources(path);result,data=convert(path,source=source)
        if data:out.with_suffix('.'+result['status']+'.gml').write_bytes(data)
        write_json(out,result)
    except Exception as error:write_json(out,{'status':'unsupported_or_failed','error':repr(error)})
def job(path):
    out=ROOT/'results/v3/bounded_adapter'/(path.stem+'.json');start=time.perf_counter()
    try:
        process=subprocess.run([sys.executable,__file__,'--worker',str(path),str(out)],capture_output=True,text=True,timeout=60)
        d=json.loads(out.read_text()) if out.exists() else {'status':'execution_failed','error':process.stderr[-1000:]}
        row={'case':path.stem,'status':d['status'],'error':d.get('error'),'geometry_valid':d.get('geometry_valid',False),'source_failures':d.get('source_evidence',{}).get('failures',[]),'report':out.relative_to(ROOT).as_posix()}
    except subprocess.TimeoutExpired:row={'case':path.stem,'status':'timeout_60s'}
    row['wall_seconds']=time.perf_counter()-start;print(path.stem,row['status'],flush=True);return row
if __name__=='__main__':
    if len(sys.argv)>1:worker(Path(sys.argv[2]),Path(sys.argv[3]))
    else:
        folder=ROOT/'results/v3/bounded_adapter';folder.mkdir(parents=True,exist_ok=False);paths=sorted((ROOT/'data/raw/v3_sum4re').glob('*.ifc'))
        write_json(folder/'PROTOCOL.json',{'source_adapter_sha256':digest(ROOT/'research/ifc_citygml_v3/source43.py'),'resource_policy_sha256':digest(ROOT/'research/ifc_citygml_v3/limits.py'),'evaluation_role':'Development resource-eligibility follow-up; not a new holdout','timeout_seconds':60,'input_hashes':{p.name:digest(p) for p in paths}})
        with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(job,paths))
        write_json(folder/'index.json',{'status':'completed','cases':rows,'scope':'No source truncation, silent repairs or partial accepted exports'})
