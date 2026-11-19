"""Check exact limb reconstruction and confirm the logging fix leaves OFF unchanged."""
from pathlib import Path
from fractions import Fraction
import json,re,sys,math
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
from ifc_citygml_v3.native import exact_union,read_off
from ifc_citygml_lab.geometry import extract_sources
from ifc_citygml.common import write_json,digest
def mp_float(text):
    expression=text.split('[')[0];terms=re.findall(r'([+-]?\d+)(?:\s*\*\s*2\^([+-]?\d+))?',expression)
    if not terms:raise ValueError('Invalid exact limb record')
    return sum((Fraction(int(c))*Fraction(2)**int(e or 0) for c,e in terms),Fraction(0))
def main():
    folder=ROOT/'results/v3/exact_logging_check';folder.mkdir(parents=True,exist_ok=False);rows=[];binary=ROOT/'tools/v3_native/build_logged/exact_union.exe'
    write_json(folder/'PROTOCOL.json',{'binary_sha256':digest(binary),'scope':'Serialization diagnostic fix only; original native computation and artifacts preserved','original_quotient_text_is_lossy':True})
    for key in ['control_1','control_2']:
        path=ROOT/'results/v3/exact_comparison'/(key+'.ifc');result,_=exact_union(extract_sources(path),folder/key,binary);assert result['status']=='completed',result
        output=folder/key/'union.off';identical=digest(output)==digest(ROOT/'results/v3/exact_comparison'/key/'union.off');vertices=read_off(output)['vertices'];maximum=0.;coords=0
        for v,line in zip(vertices,output.with_suffix('.off.rational.txt').read_text().splitlines()):
            fields=line.strip().split('\t');assert len(fields)==6
            for i in range(3):
                exact=mp_float(fields[2*i])/mp_float(fields[2*i+1]);error=abs(Fraction(v[i])-exact);maximum=max(maximum,float(error));coords+=1
                assert float(error)<=8*math.ulp(v[i])
        rows.append({'case':key,'off_byte_identical_to_original_native_run':identical,'exact_coordinates_reconstructed':coords,'maximum_exact_to_off_coordinate_error_m':maximum,'exact_log_sha256':digest(output.with_suffix('.off.rational.txt'))});assert identical
    write_json(folder/'index.json',{'status':'passed','cases':rows,'original_logs':'Original MP_Float stream output is approximate. Only corrected exact-limb records support exact reconstruction.'});print(rows)
if __name__=='__main__':main()
