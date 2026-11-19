"""Task-local SDK headers/libs from Microsoft NuGet, without system installation."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import base64,hashlib,json,shutil,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]
def acquire(name):
    version='10.0.28000.2957';base=f'https://api.nuget.org/v3-flatcontainer/{name}/{version}/{name}.{version}.nupkg';folder=ROOT/'tools/v3_native/sdk';folder.mkdir(parents=True,exist_ok=True);path=folder/(name+'.nupkg')
    if not path.exists():
        with urllib.request.urlopen(base,timeout=180) as src,path.open('wb') as out:shutil.copyfileobj(src,out)
    # Retain local digest; NuGet HTTPS origin is the acquisition provenance.
    records={'package':name,'version':version,'url':base,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            name=item.filename.lower()
            if item.is_dir() or not ('/include/' in name or name.endswith('.lib') and '/x64/' in name or 'license' in name or 'licence' in name):continue
            target=(folder/records['package']/item.filename).resolve()
            if not target.is_relative_to(folder.resolve()):raise ValueError('Unsafe SDK path')
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():
                with archive.open(item) as src,target.open('wb') as out:shutil.copyfileobj(src,out)
    print('SDK extracted',records['package'],flush=True);return records
if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=2) as pool:records=list(pool.map(acquire,['microsoft.windows.sdk.cpp','microsoft.windows.sdk.cpp.x64']))
    (ROOT/'tools/v3_native/sdk/SOURCE_MANIFEST.json').write_text(json.dumps({'files':records,'scope':'Microsoft SDK licensed files for local compilation; not redistributed'},indent=2))
