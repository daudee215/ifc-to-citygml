"""Fresh SUM4Re applicability and bounded raw scan metadata, without invented alignment."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
from ifc_citygml.common import write_json,digest
from ifc_citygml_v3.benchmark import algorithm_digest

def scan_audit(path):
    import laspy,numpy as np
    counts={};sample=[];offset=0
    with laspy.open(path) as reader:
        h=reader.header;stride=max(1,h.point_count//2048)
        for points in reader.chunk_iterator(100000):
            classes,n=np.unique(points.classification,return_counts=True)
            for k,v in zip(classes,n):counts[str(int(k))]=counts.get(str(int(k)),0)+int(v)
            indices=np.arange(len(points));selected=indices[(indices+offset)%stride==0]
            sample.extend(np.column_stack([points.x[selected],points.y[selected],points.z[selected]]).tolist());offset+=len(points)
        crs=h.parse_crs();record={'path':path.relative_to(ROOT).as_posix(),'sha256':digest(path),'points':h.point_count,'bounds':[h.mins.tolist(),h.maxs.tolist()],
            'crs':crs.to_string() if crs else None,'coordinate_scales':h.scales.tolist(),'classification_counts':counts,'sample_points_xyz':sample[:2048],
            'registration_status':'not independently established','independent_semantic_labels_available':False}
    return record

def worker(path,output):
    import ifcopenshell
    from ifc_citygml_v3.converter import convert
    from ifc_citygml_lab.geometry import extract_sources
    from ifc_citygml_v3.policy import Policy
    path=Path(path);output=Path(output);model=ifcopenshell.open(str(path));site=path.stem
    record={'input':path.relative_to(ROOT).as_posix(),'input_sha256':digest(path),'schema':model.schema,'ifc_elements':len(model.by_type('IfcElement')),
        'ifc_buildings':len(model.by_type('IfcBuilding')),'project_group':'The_Hague' if site in ['Target','Donor'] else 'San_Sebastian' if site in ['Anoeta','Jolastokieta'] else 'Longyearbyen',
        'license':'CC-BY-4.0','matched_scan_by_publisher_filename':None,'reference_independence':'not established; no surveyed accuracy or semantic score calculated'}
    scan=path.parent/(site+'_HL2.laz')
    if scan.exists():record['matched_scan_by_publisher_filename']=scan_audit(scan)
    try:
        source=extract_sources(path);record['source_bounds']=[b.get('building_frame') for b in source['buildings']]
        result,data=convert(path,Policy(),source);write_json(output.with_suffix('.conversion.json'),result)
        if data:output.with_suffix('.'+result['status']+'.gml').write_bytes(data)
        record.update(status=result['status'],geometry_valid=result['geometry_valid'],conversion_report=output.with_suffix('.conversion.json').relative_to(ROOT).as_posix())
    except Exception as error:record.update(status='unsupported_or_failed',error=repr(error))
    write_json(output,record)

def job(path):
    output=ROOT/'results/v3/external'/(path.stem+'.audit.json');start=time.perf_counter()
    try:
        process=subprocess.run([sys.executable,__file__,'--worker',str(path),str(output)],capture_output=True,text=True,timeout=150)
        row=json.loads(output.read_text()) if output.exists() else {'input':str(path),'status':'execution_failed','stderr':process.stderr[-2000:]}
    except subprocess.TimeoutExpired:row={'input':str(path),'status':'timeout_150s'}
    row['wall_seconds']=time.perf_counter()-start;print(path.stem,row['status'],flush=True);return row

if __name__=='__main__':
    if len(sys.argv)>1:worker(sys.argv[2],sys.argv[3])
    else:
        folder=ROOT/'results/v3/external';folder.mkdir(parents=True,exist_ok=False);paths=sorted((ROOT/'data/raw/v3_sum4re').glob('*.ifc'))
        write_json(folder/'PROTOCOL.json',{'algorithm_sha256':algorithm_digest(),'inputs':[{'path':str(p),'sha256':digest(p)} for p in paths],'evaluation_role':'New external applicability holdout; paired scans require further registration/independence evidence','timeout_seconds':150,'workers':2,'source_manifest_sha256':digest(ROOT/'data/raw/v3_sum4re/source_manifest.json')})
        with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(job,paths))
        write_json(folder/'index.json',{'status':'completed','cases':rows,'claims':'Applicability and raw metadata only; not verified scan accuracy, semantic truth or Torino validation'})
