"""Acquire explicitly licensed Zenodo IFCs with publisher checksum verification."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import shutil
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'data/raw/open_corpus'

def acquire(record):
    metadata=json.loads((ROOT/f'results/expansion_v1/data_discovery/{record}.json').read_text())
    assert metadata['metadata']['license']['id']=='cc-by-4.0'
    folder=DEST/record;folder.mkdir(parents=True,exist_ok=True)
    (folder/'zenodo_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    selected=[f for f in metadata['files'] if f['key'].lower().endswith('.ifc') or f['key'] in ['2026_BIMprojects.zip','LICENSE','README.md']]
    rows=[]
    for item in selected:
        name=item['key'];assert Path(name).name==name
        target=folder/name
        if not target.exists():
            partial=target.with_suffix(target.suffix+'.partial')
            with urllib.request.urlopen(item['links']['self'],timeout=180) as response,partial.open('wb') as out:
                shutil.copyfileobj(response,out)
            assert partial.stat().st_size==item['size'], 'Incomplete download'
            assert hashlib.md5(partial.read_bytes()).hexdigest()==item['checksum'].split(':')[1], 'Publisher checksum mismatch'
            partial.rename(target)
        assert hashlib.md5(target.read_bytes()).hexdigest()==item['checksum'].split(':')[1]
        rows.append({'name':name,'bytes':target.stat().st_size,'publisher_checksum':item['checksum'],'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'download_url':item['links']['self']})
        print(record,name,'verified',flush=True)
        if target.suffix=='.zip':
            with zipfile.ZipFile(target) as archive:
                if sum(i.file_size for i in archive.infolist())>2_000_000_000:raise ValueError('Archive exceeds 2 GB extraction budget')
                for member in archive.infolist():
                    if member.is_dir() or not member.filename.lower().endswith(('.ifc','.md','.txt','.csv')):continue
                    resolved=(folder/'models'/member.filename).resolve()
                    if not resolved.is_relative_to((folder/'models').resolve()):raise ValueError('Unsafe archive path')
                    if member.file_size>1_000_000_000:raise ValueError('Oversized member')
                    resolved.parent.mkdir(parents=True,exist_ok=True)
                    if not resolved.exists():
                        with archive.open(member) as src,resolved.open('wb') as out:shutil.copyfileobj(src,out)
    manifest={'record':record,'source':f'https://zenodo.org/records/{record}','license':'CC-BY-4.0','title':metadata['metadata']['title'],'creators':metadata['metadata'].get('creators',[]),'files':rows,'genuine_torino_building':False,'independent_survey_controls':False,'grouping_note':'Architectural/structural exports from the same student team must remain one evaluation group.'}
    (folder/'source_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return {'record':record,'verified_downloads':len(rows),'ifc_files':len(list(folder.rglob('*.ifc')))}

if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(acquire,['6685810','6397164','19722012']):print(result,flush=True)
