from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from ifc_citygml_lab.fixtures import create_case
from ifc_citygml_v3.converter import convert
from ifc_citygml_v3.annotations import evaluate_scoped,reviewer_agreement
def test_annotation_cannot_score_a_different_output(tmp_path):
    p=tmp_path/'r.ifc';create_case(p,'rectangle');r,_=convert(p)
    with pytest.raises(ValueError,match='different'):evaluate_scoped(r,[{'input_sha256':r['input_sha256'],'output_sha256':'wrong','region_id':'x'}])
def test_unscoped_reference_does_not_become_truth(tmp_path):
    p=tmp_path/'r.ifc';create_case(p,'rectangle');r,_=convert(p)
    score=evaluate_scoped(r,[{'region_id':'x','reference_label':'wall','reviewer_id':'person','independent_reference':'true','evidence_uri':'drawing'}])
    assert score['scored_regions']==0 and score['unscoped_regions_not_scored']==1
def test_review_agreement_does_not_mix_artifacts():
    base={'region_id':'same','reference_label':'roof','reviewer_id':'A','independent_reference':'true','evidence_uri':'drawing','input_sha256':'input','output_sha256':'first'}
    other={**base,'reviewer_id':'B','output_sha256':'second'}
    assert reviewer_agreement([base],[other])['shared_scored_regions']==0
