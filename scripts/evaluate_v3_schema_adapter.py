"""Separate follow-up applicability study after IFC4X3 limitations were observed."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
from ifc_citygml.common import write_json,digest
def worker(path,output):
    from ifc_citygml_v3.source43 import extract_sources
    from ifc_citygml_v3.converter import convert
    try:
        source=extract_sources(path);result,data=convert(path,source=source)
        if data:output.with_suffix('.'+result['status']+'.gml').write_bytes(data)
        write_json(output,result)
    except Exception as error:write_json(output,{'status':'unsupported_or_failed','error':repr(error)})
def job(path):
    out=ROOT/'results/v3/schema_adapter'/(path.stem+'.json');start=time.perf_counter()
    try:
        process=subprocess.run([sys.executable,__file__,'--worker',str(path),str(out)],capture_output=True,text=True,timeout=90)
        d=json.loads(out.read_text()) if out.exists() else {'status':'execution_failed','error':process.stderr[-2000:]}
        row={'case':path.stem,'status':d['status'],'geometry_valid':d.get('geometry_valid',False),'error':d.get('error'),'report':out.relative_to(ROOT).as_posix()}
    except subprocess.TimeoutExpired:row={'case':path.stem,'status':'timeout_90s'}
    row['wall_seconds']=time.perf_counter()-start;print(row,flush=True);return row
if __name__=='__main__':
    if len(sys.argv)>1:worker(Path(sys.argv[2]),Path(sys.argv[3]))
    else:
        folder=ROOT/'results/v3/schema_adapter';folder.mkdir(parents=True,exist_ok=False);paths=sorted((ROOT/'data/raw/v3_sum4re').glob('*.ifc'))
        write_json(folder/'PROTOCOL.json',{'evaluation_role':'Development follow-up on already inspected external collection; not a fresh holdout','source_adapter_sha256':digest(ROOT/'research/ifc_citygml_v3/source43.py'),'timeout_seconds':90,'inputs':[{'path':str(p),'sha256':digest(p)} for p in paths]})
        with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(job,paths))
        write_json(folder/'index.json',{'status':'completed','cases':rows,'scope':'Experimental local-placement building subset, not general IFC4X3 infrastructure support'})
