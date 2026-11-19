"""Verify the expanded evidence, preserved releases and final atlas package."""
import csv
from collections import Counter
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from pypdf import PdfReader
from prepare_methodology_evidence import ROOT,sha,verify_frozen

EXP=ROOT/'results/experiments/shape_fidelity_002';OUT=ROOT/'reports/shape_fidelity_002'
protocol=json.loads((EXP/'PROTOCOL.json').read_text())
assert sha(ROOT/'scripts/shape_fidelity_confirmation.py')==protocol['runner_sha256']
for key,filename in [('protocol_sha256','PROTOCOL.json'),('evaluation_sha256','evaluation.json')]:
    assert sha(ROOT/'results/experiments/shape_fidelity_001'/filename)==protocol['earlier_study'][key]
sources=json.loads((EXP/'candidate_inputs.json').read_text());assert len(sources)==60
for c in sources:
    path=Path(c['input']);assert sha(path)==c['input_sha256']
    assert sha(path.with_suffix('.expected.json'))==c['expected_sha256']
data=json.loads((EXP/'evaluation.json').read_text());baseline=data['baseline_rows'];candidate=data['candidate_rows']
assert len(baseline)==180 and len(candidate)==60
assert Counter((r['mode'],r['status']) for r in baseline)=={('block','passed'):60,('source','passed'):60,('exterior','passed'):52,('exterior','failed'):8}
transitions=Counter()
for r in candidate:
    b=next(b for b in baseline if b['case']==r['case'] and b['mode']=='exterior')
    transitions[b['status']+'_'+r['status']]+=1
    detail=json.loads((EXP/'candidate'/r['report']).read_text())
    assert detail['source_sha256']==protocol['source_sha256']
    assert sha(EXP/'candidate'/detail['candidate_gml'])==detail['output_sha256']
    assert detail['validation']['external_validation']['report']['parameters']['snap_tol']==1e-6
    assert detail['union_grid_m']==1e-7
assert dict(transitions)=={'passed_passed':50,'failed_passed':4,'passed_failed':2,'failed_failed':4}
for r in baseline:
    report=ROOT/r['report'];detail=json.loads(report.read_text())
    assert detail['converter_source_sha256']==protocol['source_sha256']
    path=report.with_name(report.name.replace('.report.json','.gml'))
    if r['status']=='passed':assert sha(path)==detail['output_sha256']
    else:assert not path.exists()
for r in baseline+candidate:
    if 'metrics'in r and r['mode']!='block':assert r['metrics']['within_surface_thresholds']
    if r['status']=='failed':assert r['validation']['external_validation']['report']['all_errors']==[102]
csvrows=list(csv.DictReader((OUT/'metrics_240.csv').open(encoding='utf-8')))
assert len(csvrows)==240 and sum(r['status']=='failed' for r in csvrows)==14
assert all(not r['raw_intersection_over_union'] for r in csvrows if r['status']=='failed')
suites=ET.parse(EXP/'tests.xml').findall('.//testsuite')
assert sum(int(x.get('tests')) for x in suites)==120
assert all(int(x.get('failures','0'))==0 and int(x.get('errors','0'))==0 for x in suites)
reader=PdfReader(OUT/'Research_Atlas_Palatino.pdf');assert len(reader.pages)==12
assert all(len(p.extract_text())>400 for p in reader.pages)
fonts={str(f.get_object().get('/BaseFont')) for page in reader.pages for f in page['/Resources'].get('/Font',{}).values()}
assert any('Palatino' in f for f in fonts)
assert len(list((OUT/'figures').glob('*.svg')))==10
assert len(list((OUT/'figures').glob('*.png')))==10
with ZipFile(OUT/'Palatino_Research_Figures.zip') as z:assert z.testzip() is None and len(z.namelist())==23
record={'status':'passed','baseline_attempts':180,'baseline_completed':172,'candidate_attempts':60,'candidate_completed':54,
        'paired_transitions':dict(transitions),'input_hashes_verified':60,'tests_passed':120,'figures':10,'atlas_pages':12,
        'visual_review':'All twelve PDF pages inspected; two introduction pages revised and inspected again to remove footer collisions',
        'frozen_releases_verified':verify_frozen(),'fonts':sorted(fonts),'artifacts':[]}
paths=[*EXP.rglob('*'),*(ROOT/'data/derived/shape_fidelity_002').glob('*'),*OUT.glob('*.md'),*OUT.glob('*.pdf'),*OUT.glob('*.csv'),*OUT.glob('*.zip'),OUT/'plot_data.json',*(OUT/'figures').glob('*'),
       *[ROOT/'scripts'/name for name in ['shape_fidelity_confirmation.py','prepare_confirmation_atlas.py','build_confirmation_figures.py','package_confirmation_atlas.py','verify_confirmation_atlas.py']],ROOT/'tests/test_confirmation_volume.py']
for path in paths:
    if path.is_file():record['artifacts'].append({'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path)})
(OUT/'VERIFICATION.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k not in ['artifacts','frozen_releases_verified']}))
