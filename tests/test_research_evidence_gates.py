"""Scientific gates fail visibly when reference or coordinate evidence is absent."""
from pathlib import Path
import sys
import numpy as np
import pytest
from shapely.geometry import box,mapping
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from ifc_citygml_lab.coordinates import apply_matrix,checkpoint_residuals,transform_engineering,audit_chain
from ifc_citygml_lab.corpus import partition_projects
from ifc_citygml_lab.semantics import evaluate_annotations,face_predictions,annotation_template
from ifc_citygml_lab.urban import exposure,compare_exposure,height_exposure
from ifc_citygml_lab.fixtures import create_case
from ifc_citygml_lab.geometry import convert_research

def collection(*geometries):return {'type':'FeatureCollection','features':[{'type':'Feature','id':str(i),'properties':{},'geometry':mapping(g)} for i,g in enumerate(geometries)]}

def test_coordinate_role_and_roundtrip():
    matrix=np.eye(4);matrix[:3,3]=[395000,4982000,200];points=np.array([[1,2,3],[4,5,6]])
    projected=apply_matrix(points,matrix)
    assert np.allclose(apply_matrix(projected,np.linalg.inv(matrix)),points)
    check=checkpoint_residuals(points,projected,matrix,'synthetic_truth','Analytically declared test')
    assert check['horizontal_rmse_m']==0 and 'Synthetic' in check['accuracy_claim']
    with pytest.raises(ValueError):checkpoint_residuals([],[],matrix,'independent_check','')
    with pytest.raises(ValueError):transform_engineering(points,{'status':'engineering_only'})
    matrix[0,0]=-1
    with pytest.raises(ValueError):apply_matrix(points,matrix)

def test_unit_audit_and_nonidentity_context_refusal(tmp_path):
    p=tmp_path/'a.ifc';create_case(p,'rectangle',millimetres=True)
    chain=audit_chain(p);assert chain['source_unit_to_metre']==.001
    import ifcopenshell
    model=ifcopenshell.open(str(p));context=model.by_type('IfcGeometricRepresentationContext',include_subtypes=False)[0]
    context.WorldCoordinateSystem.Location.Coordinates=(1.,0.,0.);model.write(str(p))
    assert audit_chain(p)['status']=='unsupported_context'
    with pytest.raises(ValueError,match='Nonidentity'):convert_research(p)

@pytest.mark.parametrize('yaw',[0,23,60])
def test_probe_on_legitimate_beam_boundary_is_not_protected(tmp_path,yaw):
    p=tmp_path/'passage.ifc';create_case(p,'passage',contents_yaw=yaw)
    result,_=convert_research(p,'conditioned_grid')
    assert result['status']=='accepted',result.get('correspondence')
    relations=result['candidate_attempts'][0]['relations']['relations']
    assert any(r.get('gap_witness_m') and not r.get('protected_gap_probe') for r in relations)

def test_semantic_truth_is_not_generated_from_hints(tmp_path):
    p=tmp_path/'roof.ifc';create_case(p,'gable_roof');result,_=convert_research(p)
    predictions=face_predictions(result);blank=annotation_template(result)
    assert len(predictions)==len(blank)>0
    assert evaluate_annotations(predictions,blank)['metrics'] is None
    item=blank[0];item.update(reference_label='roof',reviewer_id='test',independent_reference='false',evidence_uri='test')
    assert evaluate_annotations(predictions,[item])['scored_regions']==0

def test_horizontal_area_touch_and_union_are_distinct():
    buildings=collection(box(0,0,2,2),box(2,0,3,2));hazard=collection(box(-1,-1,2,3))
    result=exposure(buildings,hazard,'EPSG:32632','synthetic_truth')
    assert result['positive_area_features']==1 and result['touching_only_features']==1
    assert result['union_exposed_area_m2']==4
    with pytest.raises(ValueError):exposure(buildings,hazard,'EPSG:4326','synthetic_truth')
    with pytest.raises(ValueError):exposure(buildings,hazard,'EPSG:32632','metadata_only')
    other=exposure(buildings,collection(box(0,0,1,1)),'EPSG:32632','synthetic_truth')
    with pytest.raises(ValueError):compare_exposure(result,other)
    with pytest.raises(ValueError):height_exposure(None,None,None,None)

def test_partition_leakage_is_rejected():
    rows=[{'project_group':'a','sha256':'same'},{'project_group':'b','sha256':'same'}]
    with pytest.raises(ValueError,match='Duplicate'):partition_projects(rows,{'a':'development','b':'test'})
