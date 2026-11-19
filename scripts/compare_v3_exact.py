from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
from ifc_citygml_v3.native import exact_union
from ifc_citygml_v3.references import corrected_expected
from ifc_citygml_lab.fixtures import create_case
from ifc_citygml_lab.geometry import extract_sources
from ifc_citygml_lab.metrics import compare_export
from ifc_citygml.validation import validate_document
from ifc_citygml.common import write_json,digest
def main():
    folder=ROOT/'results/v3/exact_comparison';folder.mkdir(parents=True,exist_ok=False);cases=[];rows=[]
    for i,(yaw,gap) in enumerate([(0,0),(17,0),(17,1e-9),(71,.001)]):
        path=folder/f'control_{i}.ifc';create_case(path,'gap_pair',contents_yaw=yaw,gap=gap);cases.append(path)
    for name in ['locked_0123_passage','locked_0171_u_shape','locked_0183_l_shape']:cases.append(ROOT/'data/derived/expansion_v2/locked'/(name+'.ifc'))
    binary=ROOT/'tools/v3_native/build_logged/exact_union.exe'
    if not binary.exists():binary=ROOT/'tools/v3_native/build/exact_union.exe'
    write_json(folder/'PROTOCOL.json',{'cases':[{'path':str(p),'sha256':digest(p)} for p in cases],'binary_sha256':digest(binary),'scope':'Minimal feasibility and historical diagnosis, not independent final evaluation','timeout_seconds':90})
    for path in cases:
        try:
            source=extract_sources(path);result,data=exact_union(source,folder/path.stem,binary)
            if data:
                result['validation']=validate_document(data,1e-6);expected=corrected_expected(json.loads(path.with_suffix('.expected.json').read_text()));result['reference_metrics']=compare_export(data,expected,512)
            result['case']=path.stem
        except Exception as error:result={'case':path.stem,'status':'execution_failed','error':repr(error)}
        rows.append(result);write_json(folder/'index.json',{'status':'running','cases':rows});print(path.stem,result['status'],flush=True)
    write_json(folder/'index.json',{'status':'completed','cases':rows,'arithmetic_scope':'Exact represented input doubles; does not establish author intent, source correctness or exact decimal output geometry'})
if __name__=='__main__':main()
