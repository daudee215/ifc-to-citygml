"""Audit new controls, unchanged evidence, figure metadata and final exports."""
import csv
from collections import Counter
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from pypdf import PdfReader
from PIL import Image
from prepare_methodology_evidence import ROOT,sha,verify_frozen

EXP=ROOT/'results/experiments/frame_alignment_004';OUT=ROOT/'reports/publication_figures_004'
protocol=json.loads((EXP/'PROTOCOL.json').read_text())
assert sha(ROOT/'scripts/frame_alignment_stress.py')==protocol['runner_sha256']
assert sha(ROOT/'scripts/local_frame_union_research.py')==protocol['adapter_sha256']
for folder in ['shape_fidelity_001','shape_fidelity_002','local_frame_003']:
    record=json.loads((ROOT/'reports'/folder/'VERIFICATION.json').read_text())
    for item in record.get('new_artifacts',record.get('artifacts',[])):assert sha(ROOT/item['path'])==item['sha256'],item['path']
manifest=json.loads((EXP/'manifest.json').read_text());assert len(manifest)==32
for case in manifest:
    path=Path(case['input']);assert sha(path)==case['input_sha256']
    assert sha(path.with_suffix('.expected.json'))==case['expected_sha256']
    ref=json.loads(path.with_suffix('.expected.json').read_text())
    assert ref['contents_yaw_degrees'] in [7,23] and ref['building_yaw_degrees'] in [0,37]
rows=json.loads((EXP/'index.json').read_text())['cases'];assert len(rows)==64
assert Counter((r['arm'],r['status'],r['all_guards_passed']) for r in rows)=={
    ('world_frame','passed',True):14,('world_frame','passed',False):14,('world_frame','failed',False):4,
    ('building_frame','passed',True):16,('building_frame','passed',False):16}
for row in rows:
    detail=json.loads((ROOT/row['report']).read_text())
    assert sha(ROOT/row['report']) and sha((ROOT/row['report']).parent/detail['output'])==detail['output_sha256']
    assert detail['validation']['external_validation']['report']['parameters']['snap_tol']==1e-6
    components=[c for b in detail['extraction']['buildings'] for c in b['components']]
    euler=0;minimum=float('inf');edge_count=0
    for comp in components:
        vertices=comp['vertices'];faces=comp['triangles'];edges=set()
        for a,b,c in faces:edges.update([tuple(sorted((a,b))),tuple(sorted((b,c))),tuple(sorted((c,a)))])
        euler+=len(vertices)-len(edges)+len(faces)
        lengths=[math.dist(vertices[a],vertices[b]) for a,b in edges];minimum=min(minimum,min(lengths));edge_count+=sum(v<1e-6 for v in lengths)
    audit=row['mesh_audit'];assert len(components)==audit['components'] and euler==audit['euler_sum']
    assert math.isclose(minimum,audit['minimum_edge_m'],rel_tol=1e-14,abs_tol=1e-14) and edge_count==audit['edges_below_1um']
    good=(len(components)==1 and euler==(0 if row['shape_family']=='courtyard' else 2));assert good==row['expected_topology']
    counterpart=next(r for r in rows if r['case']==row['case'].removesuffix('_m')+'_mm' and r['arm']==row['arm']) if row['units']=='metre' else row
    assert counterpart['mesh_audit']==row['mesh_audit'] and counterpart['status']==row['status'] and counterpart['all_guards_passed']==row['all_guards_passed']
    if row['status']=='failed':assert detail['validation']['external_validation']['report']['all_errors']==[102]
    else:assert detail['validation']['independent_general_solid_validation']=='passed'
assert len(list(csv.DictReader((OUT/'stress_comparison_64.csv').open(encoding='utf-8'))))==64
assert len(list(csv.DictReader((OUT/'complete_controlled_404.csv').open(encoding='utf-8'))))==404
suites=ET.parse(EXP/'tests.xml').findall('.//testsuite');assert sum(int(s.get('tests')) for s in suites)==129
assert all(int(s.get('failures','0'))==int(s.get('errors','0'))==0 for s in suites)
assert json.loads((OUT/'layout_bounds.json').read_text())==[]
assert len(list((OUT/'figures').glob('*.svg')))==len(list((OUT/'figures').glob('*.png')))==9
for image in (OUT/'figures').glob('*.png'):
    with Image.open(image) as im:assert im.size==(3200,2000)
reader=PdfReader(OUT/'Research_Figure_Edition_Palatino.pdf');assert len(reader.pages)==11
assert all(len(page.extract_text())>400 for page in reader.pages)
fonts={str(f.get_object().get('/BaseFont')) for page in reader.pages for f in page['/Resources'].get('/Font',{}).values()}
assert any('Palatino' in f for f in fonts)
with ZipFile(OUT/'Editable_Figures_and_Evidence.zip') as z:assert z.testzip() is None and len(z.namelist())==24
record={'status':'passed','new_inputs':32,'new_attempts':64,'total_controlled_attempts':404,
    'stress_baseline_valid':28,'stress_baseline_all_guards':14,'stress_building_frame_valid':32,'stress_building_frame_all_guards':16,
    'tests_passed':129,'figures':9,'png_dimensions':[3200,2000],'pages':11,'fonts':sorted(fonts),
    'visual_review':'All eleven final PDF pages inspected; introductory typography corrected and reviewed; all SVG text bounds checked',
    'frozen_releases_verified':verify_frozen(),'artifacts':[]}
paths=[*EXP.rglob('*'),*(ROOT/'data/derived/frame_alignment_004').glob('*'),*OUT.glob('*.md'),*OUT.glob('*.csv'),*OUT.glob('*.pdf'),*OUT.glob('*.zip'),OUT/'figure_index.json',OUT/'geometry_sources.json',OUT/'layout_bounds.json',*(OUT/'figures').glob('*'),
    *[ROOT/'scripts'/name for name in ['frame_alignment_stress.py','prepare_publication_geometry.py','build_publication_figures.py','check_publication_layout.py','package_publication_edition.py','verify_publication_edition.py']],ROOT/'tests/test_frame_alignment_fixture.py']
for path in paths:
    if path.is_file():record['artifacts'].append({'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path)})
(OUT/'VERIFICATION.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k not in ['artifacts','frozen_releases_verified']}))
