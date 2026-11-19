from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import ifcopenshell
from ifc_citygml_lab.fixtures import create_case
from ifc_citygml_v3.source43 import extract_sources
from ifc_citygml_v3.converter import convert
def test_ifc43_mapped_building_stays_in_engineering_frame(tmp_path):
    path=tmp_path/'mapped.ifc';create_case(path,'rectangle')
    contents=path.read_text();contents=contents.replace("FILE_SCHEMA(('IFC4'));","FILE_SCHEMA(('IFC4X3_ADD2'));");path.write_text(contents)
    model=ifcopenshell.open(str(path));context=model.by_type('IfcGeometricRepresentationContext')[0]
    target=model.create_entity('IfcProjectedCRS',Name='EPSG:32632');model.create_entity('IfcMapConversion',SourceCRS=context,TargetCRS=target,Eastings=395000.,Northings=4982000.,OrthogonalHeight=200.,Scale=1.);model.write(str(path))
    source=extract_sources(path);assert source['ifc_schema'].startswith('IFC4X3') and source['status']=='passed'
    assert source['profile']['retained_map_metadata_not_applied']
    points=source['buildings'][0]['elements'][0]['vertices'];assert min(p[0] for p in points)==100.
    result,data=convert(path,source=source);assert result['status']=='accepted'
