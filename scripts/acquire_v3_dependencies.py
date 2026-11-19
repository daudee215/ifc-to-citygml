"""Pinned official native headers and a bounded, licensed fresh IFC/scan subset."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,shutil,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]

def fetch(url,path,algorithm,expected,limit=250_000_000):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        temporary=path.with_suffix(path.suffix+'.partial');size=0
        with urllib.request.urlopen(url,timeout=180) as response,temporary.open('wb') as target:
            while chunk:=response.read(1024*1024):
                size+=len(chunk)
                if size>limit:raise ValueError('Download budget exceeded')
                target.write(chunk)
        if hashlib.new(algorithm,temporary.read_bytes()).hexdigest()!=expected:raise ValueError('Publisher checksum mismatch')
        temporary.rename(path)
    if hashlib.new(algorithm,path.read_bytes()).hexdigest()!=expected:raise ValueError('Retained checksum mismatch')
    return {'path':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'url':url,'publisher_checksum':algorithm+':'+expected}

def native():
    folder=ROOT/'tools/v3_native';folder.mkdir(parents=True,exist_ok=True)
    records=[]
    specifications=[('CGAL-6.2.1.zip','https://github.com/CGAL/cgal/releases/download/v6.2.1/CGAL-6.2.1.zip','eebd737d9b7f0199647ba5c1f9f6c7a3d0651aacef9c2fd4dedc52da6c25edbe'),('boost_1_87_0.zip','https://archives.boost.io/release/1.87.0/source/boost_1_87_0.zip','f367a218d27b23b568956bacf56d08d2c1d9647211337136be8cac5cb2ff0828')]
    for name,url,checksum in specifications:
        path=folder/name;records.append(fetch(url,path,'sha256',checksum))
        with zipfile.ZipFile(path) as z:
            for member in z.infolist():
                # Only headers and licence texts; no third-party setup/build execution.
                wanted=('/include/' in member.filename or name.startswith('boost') and '/boost/' in member.filename or 'LICENSE' in member.filename or 'COPYING' in member.filename)
                if member.is_dir() or not wanted:continue
                target=(folder/member.filename).resolve()
                if not target.is_relative_to(folder.resolve()):raise ValueError('Unsafe archive path')
                target.parent.mkdir(parents=True,exist_ok=True)
                if not target.exists():
                    with z.open(member) as src,target.open('wb') as out:shutil.copyfileobj(src,out)
        print('Verified and extracted',name,flush=True)
    (folder/'SOURCE_MANIFEST.json').write_text(json.dumps({'files':records,'scope':'CGAL GPL/commercial package and Boost BSL headers for local research comparison; no binaries redistributed in project release'},indent=2))

def corpus():
    metadata=json.loads((ROOT/'results/v3/discovery/sum4re_23808860.json').read_text());assert metadata['metadata']['license']['id']=='cc-by-4.0'
    folder=ROOT/'data/raw/v3_sum4re';rows=[]
    for item in metadata['files']:
        if not (item['key'].endswith('.ifc') or item['key'].endswith('_HL2.laz')):continue
        rows.append(fetch(item['links']['self'],folder/item['key'],'md5',item['checksum'].split(':')[1],30_000_000));print('Verified SUM4Re',item['key'],flush=True)
    (folder/'source_manifest.json').write_text(json.dumps({'record':'23808860','source':'https://zenodo.org/records/23808860','license':'CC-BY-4.0','metadata':metadata['metadata'],'files':rows,'reference_status':'Pairing and registration require audit; not assumed independent survey truth','torino':False},indent=2))

if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in [pool.submit(native),pool.submit(corpus)]:future.result()
