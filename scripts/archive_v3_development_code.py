from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'research'))
from ifc_citygml_v3.benchmark import ALGORITHM_FILES
records=[]
for study in ['development','development_corrected']:
    folder=ROOT/'results/v3/code_archives'/study;folder.mkdir(parents=True,exist_ok=True);h=hashlib.sha256()
    for name in ALGORITHM_FILES:
        content=(ROOT/'research/ifc_citygml_v3'/name).read_bytes()
        if study=='development' and name=='fixtures.py':
            s=content.decode();start=s.index('            # Per-building material targets');end=s.index("        elif mechanism=='tilted':",start)
            s=s[:start]+s[end:];s=s.replace('create_case,FAMILIES,reference_mesh','create_case,FAMILIES');content=s.encode()
        (folder/name).write_bytes(content);h.update(name.encode());h.update(content)
    protocol=json.loads((ROOT/'results/v3'/study/'PROTOCOL.json').read_text())
    records.append({'study':study,'snapshot_sha256':h.hexdigest(),'protocol_algorithm_sha256':protocol['algorithm_sha256'],'matches':h.hexdigest()==protocol['algorithm_sha256']})
print(json.dumps(records));assert all(r['matches'] for r in records)
(ROOT/'results/v3/code_archives/VERIFICATION.json').write_text(json.dumps(records,indent=2))
