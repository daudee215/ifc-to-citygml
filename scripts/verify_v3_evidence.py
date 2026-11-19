"""Verify frozen predecessors, study snapshots, source inputs and new artifacts."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src'),str(ROOT/'scripts')]
from prepare_methodology_evidence import verify_frozen
from ifc_citygml_v3.benchmark import ALGORITHM_FILES,algorithm_digest

def sha(path,algorithm='sha256'):
    h=hashlib.new(algorithm)
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def main():
    frozen=verify_frozen();preserved={}
    for p in (ROOT/'reports').glob('*/VERIFICATION.json'):
        if p.parent.name=='v3':continue
        data=json.loads(p.read_text())
        for key in ['artifacts','new_artifacts','files','outputs']:
            values=data.get(key,[])
            if not isinstance(values,list):continue
            for row in values:
                if isinstance(row,dict) and 'path' in row and 'sha256' in row:preserved[row['path'].replace('\\','/')]=row['sha256']
    for i,(name,digest) in enumerate(preserved.items()):
        if sha(ROOT/name)!=digest:raise ValueError('Preserved artifact changed: '+name)
        if i and i%5000==0:print('Verified prior artifact hashes:',i,flush=True)
    print('All prior artifact hashes preserved:',len(preserved),flush=True)
    studies=[]
    for name in ['development','development_corrected','holdout']:
        folder=ROOT/'results/v3'/name;protocol=json.loads((folder/'PROTOCOL.json').read_text());index=json.loads((folder/'index.json').read_text());assert index['status']=='completed'
        snapshot=folder/'code_snapshot' if name=='holdout' else ROOT/'results/v3/code_archives'/name;h=hashlib.sha256()
        for file in ALGORITHM_FILES:h.update(file.encode());h.update((snapshot/file).read_bytes())
        if h.hexdigest()!=protocol['algorithm_sha256']:raise ValueError('Study code snapshot mismatch: '+name)
        manifest_path=Path(protocol['manifest']);assert sha(manifest_path)==protocol['manifest_sha256'];manifest=json.loads(manifest_path.read_text())
        for c in manifest['cases']:
            assert sha(Path(c['input']))==c['input_sha256'];assert sha(Path(c['input']).with_suffix('.expected.json'))==c['expected_sha256']
        for r in index['cases']:
            if r.get('output'):assert sha(folder/r['output'])==r['output_sha256']
        studies.append({'name':name,'attempts':index['attempts'],'snapshot_sha256':h.hexdigest(),'input_and_reference_hashes_verified':len(manifest['cases'])})
    assert algorithm_digest()==json.loads((ROOT/'results/v3/holdout/PROTOCOL.json').read_text())['algorithm_sha256']
    raw=json.loads((ROOT/'data/raw/v3_sum4re/source_manifest.json').read_text())
    for row in raw['files']:
        assert sha(ROOT/row['path'])==row['sha256'];algorithm,expected=row['publisher_checksum'].split(':');assert sha(ROOT/row['path'],algorithm)==expected
    for folder in ['build','build_logged']:
        path=ROOT/'tools/v3_native'/folder;build=json.loads((path/'BUILD_MANIFEST.json').read_text());assert sha(path/'exact_union.exe')==build['executable_sha256']
    assert json.loads((ROOT/'results/v3/exact_logging_check/index.json').read_text())['status']=='passed'
    assert json.loads((ROOT/'results/v3/exact_intersection_check/index.json').read_text())['status']=='passed'
    assert all(r['byte_identical'] for r in json.loads((ROOT/'results/v3/measurement_recovery_equivalence.json').read_text())['cases'])
    tests=json.loads((ROOT/'results/v3/test_summary.json').read_text());assert tests['unique_passed_tests']==181 and tests['all_latest_records_passed']
    browser=json.loads((ROOT/'reports/v3/viewer_verification.json').read_text());assert len(browser)==16 and all(r['passed'] for r in browser)
    assert json.loads((ROOT/'reports/v3/layout_bounds.json').read_text())==[]
    pdf=json.loads((ROOT/'reports/v3/pdf_verification.json').read_text());assert pdf['pages']==16 and pdf['all_page_renders_present'] and pdf['required_end_text_retained']
    paths=[]
    for name in ['research/ifc_citygml_v3','research/native_v3','results/v3','reports/v3','data/derived/v3','data/raw/v3_sum4re']:
        paths.extend(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='VERIFICATION.json')
    paths.extend((ROOT/'scripts').glob('*v3*.py'));paths.extend((ROOT/'tests').glob('test_v3*.py'))
    paths.extend(ROOT/name for name in ['docs/V3_IMPLEMENTATION_GUIDE.md','docs/ADVANCED_EXTENSION_V3.md','docs/ADVANCED_EXTENSION_V3_BACKLOG.json','docs/ADVANCED_EXTENSION_V3_EXECUTION.json','V3_START_HERE.md','research/requirements_v3_optional.txt','tools/v3_native/SOURCE_MANIFEST.json','tools/v3_native/sdk/SOURCE_MANIFEST.json'])
    for folder in ['build','build_logged']:
        paths.extend(ROOT/'tools/v3_native'/folder/file for file in ['BUILD_MANIFEST.json','build.log','exact_union.exe'])
    records=[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in sorted(set(paths))]
    result={'status':'verified_with_explicit_research_limits','preserved_prior_unique_artifacts':len(preserved),'frozen_releases':frozen,'studies':studies,'tests_passed':181,'browser_checks_passed':16,
        'pdf_pages':16,'figures':12,'original_holdout_algorithm_unchanged':True,'telemetry_recovery_byte_identical':True,'native_exact_logging_audited':True,
        'release_promoted':False,'independent_semantic_reference_regions':0,'verified_torino_ifc_survey_pairs':0,'artifacts':records}
    (ROOT/'reports/v3/VERIFICATION.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('Verified V3 artifacts:',len(records),'and predecessor hashes:',len(preserved))
if __name__=='__main__':main()
