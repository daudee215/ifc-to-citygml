"""Independent audit of new study records, topology arithmetic and delivery."""
import csv
from collections import Counter
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from pypdf import PdfReader
from prepare_methodology_evidence import ROOT,sha,verify_frozen

EXP=ROOT/'results/experiments/local_frame_003';OUT=ROOT/'reports/local_frame_003'
protocol=json.loads((EXP/'PROTOCOL.json').read_text())
assert sha(ROOT/'scripts/local_frame_confirmation.py')==protocol['runner_sha256']
assert sha(ROOT/'scripts/local_frame_union_research.py')==protocol['adapter_sha256']
for folder in ['shape_fidelity_001','shape_fidelity_002']:
    old=json.loads((ROOT/'reports'/folder/'VERIFICATION.json').read_text())
    for item in old.get('new_artifacts',old.get('artifacts',[])):assert sha(ROOT/item['path'])==item['sha256'],item['path']
inputs=json.loads((EXP/'all_inputs.json').read_text());assert len(inputs)==80
for row in inputs:
    source=Path(row['input']);assert sha(source)==row['input_sha256']
    assert sha(source.with_suffix('.expected.json'))==row['expected_sha256']
data=json.loads((EXP/'evaluation.json').read_text());assert len(data['baseline'])==len(data['candidate'])==80
assert sum(r['status']=='passed' for r in data['baseline'])==70
assert sum(r['cohort']=='prospective_angles' for r in data['candidate'])==20
def expected_topology(row):return row['mesh_audit']['components']==1 and row['mesh_audit']['euler_sum']==(0 if row['shape_family']=='courtyard' else 2)
assert sum(expected_topology(r) for r in data['baseline'])==44
assert sum(r['status']=='passed' and not expected_topology(r) for r in data['baseline'])==26
maximum_volume_error=0
for row in data['candidate']:
    detail=json.loads((EXP/'candidate'/row['report']).read_text())
    assert sha(EXP/'candidate'/detail['candidate_gml'])==detail['output_sha256']
    assert detail['input_sha256']==sha(Path(detail['input']))
    assert row['status']=='passed' and row['all_research_guards_passed'] and expected_topology(row)
    assert detail['validation']['independent_general_solid_validation']=='passed'
    assert detail['validation']['external_validation']['report']['parameters']['snap_tol']==1e-6
    assert detail['extraction']['research_frame_policy']['grid_m']==1e-6
    components=[c for b in detail['extraction']['buildings'] for c in b['components']];assert len(components)==1
    euler=0;minimum=float('inf')
    for component in components:
        vertices=component['vertices'];faces=component['triangles'];edges=set()
        for a,b,c in faces:
            edges.update([tuple(sorted((a,b))),tuple(sorted((b,c))),tuple(sorted((c,a)))])
        euler+=len(vertices)-len(edges)+len(faces)
        minimum=min(minimum,min(math.dist(vertices[a],vertices[b]) for a,b in edges))
    assert euler==row['mesh_audit']['euler_sum']
    assert math.isclose(minimum,row['mesh_audit']['minimum_edge_m'],rel_tol=1e-14,abs_tol=1e-14) and minimum>=1e-6
    assert row['metrics']['measurement_1nm']['intersection_over_union']==1
    assert row['metrics']['measurement_1nm']['boundary_hausdorff_m']==0
    maximum_volume_error=max(maximum_volume_error,abs(row['metrics']['volume']['relative_error']))
    assert maximum_volume_error<=1e-6
external=json.loads((EXP/'external/index.json').read_text());assert len(external['cases'])==4
assert Counter(r['status'] for r in external['cases'])=={'passed':1,'failed':3}
plan=json.loads((EXP/'external/PLAN.json').read_text());assert sha(ROOT/'scripts/local_frame_external_check.py')==plan['runner_sha256']
for row in external['cases']:
    detail=json.loads((EXP/'external'/(row['case']+'.report.json')).read_text())
    if row['status']=='passed':assert sha(EXP/'external'/row['candidate_gml'])==row['output_sha256']
    else:assert detail['extraction']['status']=='failed' and 'candidate_gml' not in detail
probe=json.loads((EXP/'exploratory_probe/report.json').read_text())
assert probe['validation']['status']=='failed' and probe['validation']['external_validation']['report']['all_errors']==[102]
assert all(r['before']==r['after'] for r in probe['extraction']['research_simplification']['records'])
assert len(list(csv.DictReader((OUT/'combined_controlled_340.csv').open(encoding='utf-8'))))==340
assert len(list(csv.DictReader((OUT/'matched_exterior_160.csv').open(encoding='utf-8'))))==160
suites=ET.parse(EXP/'tests.xml').findall('.//testsuite')
assert sum(int(s.get('tests')) for s in suites)==125
assert all(int(s.get('failures','0'))==int(s.get('errors','0'))==0 for s in suites)
pdf=PdfReader(OUT/'Research_Atlas_Palatino.pdf');assert len(pdf.pages)==18
assert all(len(p.extract_text())>400 for p in pdf.pages)
for n in range(3,13):assert sha(OUT/f'qa/page-{n:02}.png')==sha(ROOT/f'reports/shape_fidelity_002/qa/page-{n:02}.png')
assert len(list((OUT/'figures').glob('*.svg')))==16
with ZipFile(OUT/'Palatino_Figures_and_Results.zip') as z:assert z.testzip() is None and len(z.namelist())==35
record={'status':'passed','controlled_attempts_across_studies':340,'matched_exterior_inputs':80,'prospective_controls':20,
    'baseline_surface_pass':70,'local_frame_surface_and_solid_pass':80,'baseline_expected_topology':44,'local_frame_expected_topology':80,
    'maximum_absolute_relative_volume_error':maximum_volume_error,'external_pass':1,'external_fail':3,'tests_passed':125,
    'frozen_releases_verified':verify_frozen(),'figures':16,'pages':18,
    'visual_review':'Two new introductory pages and six new plates inspected; ten earlier figure pages match previously inspected PNG hashes',
    'artifacts':[]}
paths=[*EXP.rglob('*'),*(ROOT/'data/derived/local_frame_003').glob('*'),*OUT.glob('*.md'),*OUT.glob('*.pdf'),*OUT.glob('*.csv'),*OUT.glob('*.zip'),*(OUT/'figures').glob('*'),
    *[ROOT/'scripts'/s for s in ['union_simplification_research.py','local_frame_union_research.py','local_frame_confirmation.py','local_frame_external_check.py','retain_simplification_probe.py','build_local_frame_figures.py','package_local_frame_atlas.py','verify_local_frame_study.py']],ROOT/'tests/test_local_frame_research.py']
for path in paths:
    if path.is_file():record['artifacts'].append({'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path)})
(OUT/'VERIFICATION.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k not in ['artifacts','frozen_releases_verified']}))
