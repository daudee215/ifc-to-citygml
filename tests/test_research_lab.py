"""Research contracts, analytical geometry and source correspondence protections."""
from pathlib import Path
import sys
import json
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from ifc_citygml_lab.contracts import Contract,default_contracts
from ifc_citygml_lab.fixtures import create_case,reference_mesh,specification
from ifc_citygml_lab.geometry import extract_sources,convert_research
from ifc_citygml_lab.metrics import mesh_statistics,compare_export
from ifc_citygml_lab.evidence import convex_relation,geometric_graph,winding_contains

@pytest.mark.parametrize('value',[0,-1,float('nan'),float('inf'),True])
def test_invalid_physical_budget_is_rejected(value):
    with pytest.raises(ValueError):Contract(maximum_vertex_change_m=value)

def test_contracts_roundtrip_and_unknown_keys_fail():
    for value in default_contracts().values():assert Contract.from_dict(value).to_dict()==value
    with pytest.raises(ValueError):Contract.from_dict({'fake_accuracy':True})

@pytest.mark.parametrize('family,volume,euler',[('courtyard',576,0),('passage',432,2),('gable_roof',432,2),('hip_roof',400,2),('slab_opening',144,0),('multipart',480,4)])
def test_independent_reference_volume_and_euler(family,volume,euler):
    parts,_,_,_,_=specification(family);v,f=reference_mesh(parts,family,1.);stats=mesh_statistics({'vertices':v,'triangles':f})
    assert stats['signed_volume_m3']==pytest.approx(volume);assert stats['euler']==euler

@pytest.mark.parametrize('gap,relation',[(0,'face_contact'),(1e-9,'separated'),(.001,'separated')])
def test_contact_classifier_preserves_real_small_gaps(tmp_path,gap,relation):
    p=tmp_path/'gap.ifc';create_case(p,'gap_pair',contents_yaw=23,gap=gap)
    source=extract_sources(p);assert source['status']=='passed',source['failures']
    evidence=convex_relation(*source['buildings'][0]['elements']);assert evidence['relation']==relation
    if gap>0:assert 'gap_witness_m' in evidence

def test_guarded_oblique_courtyard_is_checked_after_serialization(tmp_path):
    p=tmp_path/'court.ifc';create_case(p,'courtyard',37,23)
    result,data=convert_research(p);assert result['status']=='accepted'
    expected=json.loads(p.with_suffix('.expected.json').read_text());m=compare_export(data,expected,32)
    assert m['all_guards_passed'],m
    assert b'RoofSurface' not in data and b'WallSurface' not in data
    assert len(result['source_links'][0]['surface_contributions'])>0

def test_no_reference_oracle_enters_candidate_selection(tmp_path):
    p=tmp_path/'oracle.ifc';create_case(p,'rectangle')
    p.with_suffix('.expected.json').write_text('not a reference')
    result,data=convert_research(p);assert result['status']=='accepted' and data

def test_source_geometry_body_units_and_composed_placements(tmp_path):
    p=tmp_path/'mm.ifc';create_case(p,'rectangle',37,23,True)
    source=extract_sources(p);v=np.array(source['buildings'][0]['elements'][0]['vertices'])
    assert v[:,2].min()==pytest.approx(10) and v[:,2].max()==pytest.approx(16)
    assert np.linalg.norm(v-[100,200,10],axis=1).min()<1e-11

def test_guarded_genuine_gap_cannot_silently_join(tmp_path):
    p=tmp_path/'realgap.ifc';create_case(p,'gap_pair',37,23,gap=1e-9)
    result,data=convert_research(p)
    if result['status']=='accepted':
        expected=json.loads(p.with_suffix('.expected.json').read_text());assert compare_export(data,expected,32)['component_count']==2
    else:assert result['status'] in {'rejected','needs_review'}
