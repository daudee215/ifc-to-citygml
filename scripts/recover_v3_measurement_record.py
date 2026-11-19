from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
from ifc_citygml_v3.safe_benchmark import run
from ifc_citygml.common import write_json,digest
if __name__=='__main__':
    original=ROOT/'data/derived/v3/holdout/manifest.json';manifest=json.loads(original.read_text());case=next(c for c in manifest['cases'] if c['case']=='v3_holdout_0066_faceted_encoding')
    folder=ROOT/'results/v3/measurement_recovery_protocol';folder.mkdir(parents=True,exist_ok=False);path=folder/'manifest.json';write_json(path,{'partition':'historical_recovery','cases':[case],'original_manifest_sha256':digest(original)})
    r=run(path,ROOT/'results/v3/measurement_recovery',workers=1,evaluation_role='Post-evaluation telemetry recovery of an inspected measurement exception; not fresh validation')
    print([(x['method'],x['status'],x.get('failed_stage'),bool(x.get('report'))) for x in r['cases']])
