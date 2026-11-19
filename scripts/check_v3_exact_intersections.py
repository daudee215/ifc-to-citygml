"""Exercise newly constructed non-dyadic intersection coordinates in the exact log."""
from pathlib import Path
from fractions import Fraction
import json,math,sys
import ifcopenshell
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src'),str(ROOT/'scripts')]
from ifc_citygml_lab.fixtures import create_case
from ifc_citygml_lab.geometry import extract_sources
from ifc_citygml_v3.native import exact_union,read_off
from check_v3_exact_logging import mp_float
from ifc_citygml.common import write_json,digest
folder=ROOT/'results/v3/exact_intersection_check';folder.mkdir(parents=True,exist_ok=False);path=folder/'overlapping_rotated_boxes.ifc';create_case(path,'gap_pair')
model=ifcopenshell.open(str(path));wall=sorted(model.by_type('IfcWall'),key=lambda e:e.id())[1];wall.ObjectPlacement.RelativePlacement.RefDirection.DirectionRatios=(.8,.6,0.);model.write(str(path))
record,data=exact_union(extract_sources(path),folder/'native',ROOT/'tools/v3_native/build_logged/exact_union.exe');assert record['status']=='completed',record
vertices=read_off(folder/'native/union.off')['vertices'];maximum=0.;non_dyadic=0;coordinates=0
for point,line in zip(vertices,(folder/'native/union.off.rational.txt').read_text().splitlines()):
    fields=line.strip().split('\t');assert len(fields)==6
    for i in range(3):
        exact=mp_float(fields[2*i])/mp_float(fields[2*i+1]);error=abs(Fraction(point[i])-exact);maximum=max(maximum,float(error));coordinates+=1
        if exact.denominator&(exact.denominator-1):non_dyadic+=1
        assert float(error)<=8*math.ulp(point[i])
assert non_dyadic>0
write_json(folder/'index.json',{'status':'passed','input_sha256':digest(path),'binary_sha256':record['executable_sha256'],'exact_coordinates_reconstructed':coordinates,'non_dyadic_rational_coordinates':non_dyadic,'maximum_exact_to_off_coordinate_error_m':maximum,'scope':'Exact-log and floating serialization test, not independent building design or survey validation'});print('Reconstructed',coordinates,'exact coordinates;',non_dyadic,'non-dyadic;',maximum,'m maximum OFF error')
