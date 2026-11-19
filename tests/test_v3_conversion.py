from pathlib import Path
import sys,json
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from ifc_citygml_v3.policy import Policy
from ifc_citygml_v3.connections import connection_evidence,apply_connection_planes
from ifc_citygml_v3.interactions import interaction_pairs
from ifc_citygml_v3.converter import convert
from ifc_citygml_v3.fixtures import add_connection
from ifc_citygml_v3.references import corrected_expected
from ifc_citygml_lab.fixtures import create_case
from ifc_citygml_lab.geometry import extract_sources
from ifc_citygml_lab.metrics import compare_export,mesh_statistics
import ifcopenshell

def case(tmp_path,kind='geometric_connection',gap=4e-8,yaw=0):
    p=tmp_path/'test.ifc';create_case(p,'gap_pair',contents_yaw=yaw,gap=gap)
    model=ifcopenshell.open(str(p));add_connection(model,kind,'test');model.write(str(p));return p

def test_logical_connection_does_not_modify_source(tmp_path):
    p=case(tmp_path,'logical_connection');source=extract_sources(p);connections=connection_evidence(p)
    repaired,ledger,unresolved=apply_connection_planes(source,connections,Policy())
    assert connections[0]['kind']=='logical_connection_only' and not ledger
    assert repaired==source

@pytest.mark.parametrize('yaw',[0,23,71])
def test_supported_plane_closes_only_the_asserted_microgap(tmp_path,yaw):
    p=case(tmp_path,yaw=yaw);r,data=convert(p)
    assert r['status']=='accepted',[(c.get('status'),c.get('reason'),c.get('verification')) for c in r['candidates']]
    assert r['selected']['operation']=='connection_plane_projection'
    assert r['operation_ledger'] and r['verification']['serialization']['maximum_coordinate_roundtrip_change_m']==0
    assert len(r['extraction']['buildings'][0]['components'])==1

def test_conflicting_planes_are_not_repaired(tmp_path):
    p=case(tmp_path,'conflicting_connection');source=extract_sources(p)
    changed,ledger,unknown=apply_connection_planes(source,connection_evidence(p),Policy())
    assert changed==source and not ledger and unknown
    result,_=convert(p);assert result['status']!='accepted'

def test_index_matches_exhaustive_bounding_box_filter():
    rng=np.random.default_rng(138);elements=[{'vertices':(rng.uniform(-3,3,3)+np.array([[0,0,0],[.5,.5,.5]])).tolist()} for _ in range(80)];budget=.01
    indexed=interaction_pairs(elements,budget);truth=[]
    for i,a in enumerate(elements):
        for j,b in enumerate(elements[:i]):
            lo,hi=np.min(a['vertices'],0),np.max(a['vertices'],0);a0,a1=np.min(b['vertices'],0),np.max(b['vertices'],0)
            if np.all(hi+2*budget>=a0) and np.all(a1+2*budget>=lo):truth.append((j,i))
    assert indexed['pairs']==sorted(truth)
    assert interaction_pairs([{'vertices':[[0,0,0],[1,1,1]]}]*10,.1,maximum_pairs=2)['status']=='budget_exceeded'

def test_corrected_reference_has_no_scaled_axis_microcells(tmp_path):
    p=tmp_path/'ring.ifc';create_case(p,'slab_opening',scale=.6413322760988635)
    old=json.loads(p.with_suffix('.expected.json').read_text());new=corrected_expected(old)
    stats=mesh_statistics(new['reference_mesh']);assert stats['minimum_edge_m']>.1
    result,data=convert(p);assert result['status']=='accepted'
    assert compare_export(data,new,512)['all_guards_passed']

@pytest.mark.parametrize('value',[0,True,float('nan'),-1])
def test_v3_policy_rejects_invalid_budgets(value):
    with pytest.raises(ValueError):Policy(maximum_edit_m=value)
