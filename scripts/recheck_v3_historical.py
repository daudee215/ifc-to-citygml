from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
from ifc_citygml_v3.converter import convert
from ifc_citygml_v3.references import corrected_expected
from ifc_citygml_lab.metrics import compare_export
from ifc_citygml.common import write_json
def main():
    folder=ROOT/'results/v3/historical_recheck';folder.mkdir(parents=True,exist_ok=False);rows=[]
    for case in json.loads((ROOT/'reports/expansion_v2/Results_Summary.json').read_text())['locked_guarded_counterexamples']:
        old=json.loads((ROOT/'results/expansion_v2/locked'/case['report']).read_text());path=Path(old['input']);result,data=convert(path)
        record={'case':case['case'],'v3_status':result['status'],'evaluation_role':'Inspected historical development diagnosis','reference_passed':False}
        if data:
            (folder/(path.stem+'.'+result['status']+'.gml')).write_bytes(data);record['metrics']=compare_export(data,corrected_expected(json.loads(path.with_suffix('.expected.json').read_text())),512);record['reference_passed']=record['metrics']['all_guards_passed']
        write_json(folder/(path.stem+'.report.json'),result);rows.append(record);print(path.stem,record['v3_status'],record['reference_passed'],flush=True)
    write_json(folder/'index.json',{'status':'completed','cases':rows,'heldout_validation':False})
if __name__=='__main__':main()
