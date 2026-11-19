"""Verify the complete new experiment, preserved baselines and final document."""
import csv
import json
from pathlib import Path
import shutil
from zipfile import ZipFile
from lxml import etree as ET
from pypdf import PdfReader
from prepare_methodology_evidence import ROOT,sha,verify_frozen

EXP=ROOT/'results/experiments/shape_fidelity_001';REPORT=ROOT/'reports/shape_fidelity_001'
protocol=json.loads((EXP/'PROTOCOL.json').read_text())
assert sha(ROOT/'scripts/shape_fidelity_experiment.py')==protocol['generator_sha256']
manifest=json.loads((EXP/'manifest.json').read_text());assert len(manifest['cases'])==30
for case in manifest['cases']:
    source=Path(case['input']);assert sha(source)==case['input_sha256']
    assert sha(source.with_suffix('.expected.json'))==case['expected_sha256']
index=json.loads((EXP/'conversions/index.json').read_text())
assert (index['attempts'],index['completed'],index['failed'])==(90,88,2)
assert index['converter_source_sha256']==protocol['converter_source_sha256']
for case in index['cases']:
    report=EXP/'conversions'/case['report'];assert report.is_file()
    parsed=json.loads(report.read_text());assert parsed['converter_source_sha256']==protocol['converter_source_sha256']
    target=EXP/'conversions'/f"{case['case']}_{case['mode']}.gml"
    if case['status']=='passed':assert sha(target)==case['output_sha256']
    else:assert not target.exists() and parsed['validation']['status']=='failed'
assert len(list(csv.DictReader((EXP/'metrics.csv').open(encoding='utf-8'))))==90
diagnostics=json.loads((EXP/'diagnostics/courtyard_grid_sensitivity.json').read_text())['rows']
assert len(diagnostics)==16
for row in diagnostics:
    assert sha(EXP/'diagnostics'/row['candidate'])==row['candidate_sha256']
    assert not row['promoted_to_primary_result']
    assert row['validator_parameters']['snap_tol']==row['validator_snap_m']
tests=ET.parse(str(EXP/'test_results.xml')).getroot()
suites=tests.findall('.//testsuite')
assert sum(int(s.get('tests')) for s in suites)==116
assert all(int(s.get('failures','0'))==0 and int(s.get('errors','0'))==0 for s in suites)
snapshot=json.loads((ROOT/'reports/methodology_v0_6/evidence_snapshot.json').read_text())
raw_count=0
for manifest in [*snapshot['datasets'].values(),snapshot['torino']]:
    for item in manifest['files']:
        assert sha(ROOT/item['path'])==item['sha256'];raw_count+=1
pdf=REPORT/'qa_final/Methods_and_Results.pdf';reader=PdfReader(pdf)
assert len(reader.pages)==7
assert all(len(p.extract_text())>1000 for p in reader.pages[:4])
for n in [2,3,4,6,7]:assert sha(REPORT/f'qa/page-{n}.png')==sha(REPORT/f'qa_final/page-{n}.png')
with ZipFile(REPORT/'Methods_and_Results.docx') as z:
    root=ET.fromstring(z.read('word/document.xml'));ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    assert len(root.xpath('//w:drawing',namespaces=ns))==3
    styles=ET.fromstring(z.read('word/styles.xml'));assert not styles.xpath('//w:pBdr',namespaces=ns)
shutil.copyfile(pdf,REPORT/'Methods_and_Results.pdf')
record={'status':'passed','primary_attempts':90,'primary_completed':88,'primary_failed':2,
        'diagnostic_validator_checks':16,'tests_passed':116,'generated_ifc_inputs_verified':30,
        'original_raw_files_verified':raw_count,'frozen_releases_verified':verify_frozen(),
        'document_pages':7,'figures':3,'visual_review':'All seven final pages inspected; pages 2 3 4 6 7 identical to inspected first rendering',
        'new_artifacts':[]}
paths=[*sorted(EXP.rglob('*')),*sorted((ROOT/'data/derived/shape_fidelity_001').glob('*')),
       *[REPORT/name for name in ['Methods_and_Results.md','Methods_and_Results.docx','Methods_and_Results.pdf']],
       *sorted((REPORT/'figures').glob('*')),
       *[ROOT/'scripts'/name for name in ['shape_fidelity_experiment.py','shape_fidelity_diagnostics.py','summarise_shape_fidelity.py','build_shape_fidelity_figures.py','build_shape_fidelity_document.py','verify_shape_fidelity_results.py']],
       ROOT/'tests/test_shape_fidelity_experiment.py']
for path in paths:
    if path.is_file():record['new_artifacts'].append({'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path)})
(REPORT/'VERIFICATION.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k not in ['new_artifacts','frozen_releases_verified']}))
