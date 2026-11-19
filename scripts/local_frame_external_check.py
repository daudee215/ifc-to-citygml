"""Exploratory applicability check on the four existing public IFC files."""
from datetime import datetime,timezone
import json
from pathlib import Path
import time
import shape_fidelity_experiment as first
from local_frame_union_research import extract_local_frame
from local_frame_confirmation import audit
from ifc_citygml.common import load_profile,write_json,digest,code_digest
from ifc_citygml.georeferencing import prepare_profile
from ifc_citygml.exterior_writer import create_exterior_document
from ifc_citygml.validation import validate_document

ROOT=first.ROOT;OUT=ROOT/'results/experiments/local_frame_003/external'
if OUT.exists() and any(OUT.iterdir()):raise FileExistsError('Do not overwrite external checks')
OUT.mkdir(exist_ok=True)
data=json.loads((ROOT/'results/v0_6/research_index.json').read_text())
cases=[r for r in data['cases'] if (r['case'] in ['duplex','clinic'] and r['mode']=='exterior') or
       (r['case'] in ['gaia_renovation','digitalhub'] and r['mode']=='engineering-exterior')]
assert len(cases)==4
write_json(OUT/'PLAN.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'runner_sha256':digest(Path(__file__)),
    'adapter_sha256':digest(ROOT/'scripts/local_frame_union_research.py'),'source_sha256':code_digest(),
    'purpose':'Exploratory external applicability after controlled results; not a preregistered independent accuracy evaluation.',
    'cases':cases,'fixed_policy':'Same local building frame adapter, union grid 1e-6 m, validator snap 1e-6 m.',
    'scope':'Keep original map provenance and engineering coordinate policy; no invented vertical datum or Torino placement.'})
rows=[]
for case in cases:
    start=time.perf_counter();row={'case':case['case'],'baseline_status':case['status'],'status':'failed','input_sha256':digest(Path(case['input']))}
    print('Starting external',case['case'],flush=True)
    try:
        profile=prepare_profile(load_profile(case['mode']),Path(case['input']))
        extraction=extract_local_frame(Path(case['input']),profile);row['extraction']=extraction
        if extraction['status']!='passed':raise ValueError('Extraction failed; source failures retained')
        data,links=create_exterior_document(extraction,profile);validation=validate_document(data,1e-6)
        row['validation']=validation;row['status']=validation['status'];row['mesh_audit']=audit(extraction)
        path=OUT/(case['case']+('.experimental.gml' if row['status']=='passed' else '.rejected_candidate.gml'))
        path.write_bytes(data);row['candidate_gml']=path.name;row['output_sha256']=digest(path);row['source_links']=links
    except Exception as error:row['error']=repr(error)
    row['wall_seconds']=time.perf_counter()-start;write_json(OUT/(case['case']+'.report.json'),row)
    rows.append({k:v for k,v in row.items() if k not in ['extraction','validation','source_links']})
    write_json(OUT/'index.json',{'status':'running','cases':rows});print('Finished external',case['case'],row['status'],flush=True)
write_json(OUT/'index.json',{'status':'completed','cases':rows})
