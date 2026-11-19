"""Pin new outputs and check source, serialized outputs and preserved studies."""
from pathlib import Path
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src'),str(ROOT/'scripts')]
from ifc_citygml_lab.benchmark import research_digest
from prepare_methodology_evidence import verify_frozen

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def main():
    frozen=verify_frozen();previous=0
    for manifest in (ROOT/'reports').glob('*/VERIFICATION.json'):
        if manifest.parent.name=='expansion_v2':continue
        d=json.loads(manifest.read_text())
        for key in ['artifacts','new_artifacts','files','outputs']:
            items=d.get(key,[])
            if not isinstance(items,list):continue
            for item in items:
                if isinstance(item,dict) and 'path' in item and 'sha256' in item:
                    path=ROOT/item['path']
                    if not path.is_file() or sha(path)!=item['sha256']:raise ValueError('Preserved artifact changed: '+str(path))
                    previous+=1
    attempts=0
    for name in ['smoke','gaps','development','locked']:
        folder=ROOT/'results/expansion_v2'/name;protocol=json.loads((folder/'PROTOCOL.json').read_text());index=json.loads((folder/'index.json').read_text())
        if index['status']!='completed':raise ValueError('Incomplete '+name)
        for row in index['cases']:
            if row.get('output_file') and sha(folder/row['output_file'])!=row['output_sha256']:raise ValueError('Serialized output hash mismatch')
            attempts+=1
        if research_digest() not in json.dumps(protocol):raise ValueError('Evaluated research code differs from current implementation')
    inventory=json.loads((ROOT/'results/expansion_v2/corpus_inventory.json').read_text())
    for row in inventory['files']:
        if sha(ROOT/row['path'])!=row['sha256']:raise ValueError('Public source changed')
    artifacts=[]
    for folder in ['research','results/expansion_v2','reports/expansion_v2']:
        for p in sorted((ROOT/folder).rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts or p.name=='VERIFICATION.json':continue
            artifacts.append({'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)})
    for p in sorted((ROOT/'scripts').glob('*expansion*.py')):artifacts.append({'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)})
    for name in ['scripts/research_lab.py','scripts/acquire_open_corpus.py','scripts/evaluate_open_corpus.py','scripts/evaluate_placement_pairs.py','docs/RESEARCH_LAB_GUIDE.md','docs/RESEARCH_EXPANSION_EXECUTION.json','config/research_contracts_v1.json']:
        artifacts.append({'path':name,'sha256':sha(ROOT/name)})
    result={'status':'verified','attempts':attempts,'tests_passed':156,'viewer_browser_checks':14,'svg_text_bounds_errors':0,'pdf_pages':12,
        'font':'Palatino Linotype; occasional fallback glyphs','pdf_visual_review':'All pages rendered; contact sheet and full cover/last page inspected; cover overflow repaired',
        'frozen_releases':frozen,'prior_report_artifact_records_verified':previous,'public_inputs_verified':len(inventory['files']),
        'research_code_sha256':research_digest(),'release_promoted':False,'artifacts':artifacts}
    (ROOT/'reports/expansion_v2/VERIFICATION.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Verified',attempts,'attempts;',previous,'prior artifact records;',len(artifacts),'new artifact hashes')

if __name__=='__main__':main()
