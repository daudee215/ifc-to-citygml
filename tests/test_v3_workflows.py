from pathlib import Path
from copy import deepcopy
import sys,json,csv
import numpy as np
import pytest
import ifcopenshell
from shapely.geometry import box,mapping
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from ifc_citygml_v3.converter import convert
from ifc_citygml_v3.incremental import update
from ifc_citygml_v3.generalisation import choose,QueryContract
from ifc_citygml_v3.annotations import reviewer_agreement
from ifc_citygml_v3.sensitivity import profile_sensitivity
from ifc_citygml_v3.fixtures import prepare
from ifc_citygml_lab.fixtures import create_case
from ifc_citygml_lab.metrics import compare_export

def test_incremental_unchanged_reuse_and_geometry_change(tmp_path):
    path=tmp_path/'initial.ifc';create_case(path,'rectangle');cache=tmp_path/'cache.json'
    first,_=update(path,cache);assert first['incremental']['verification_status']=='passed'
    second,_=update(path,cache);assert len(second['incremental']['reused_buildings'])==1 and not second['incremental']['recomputed_buildings']
    model=ifcopenshell.open(str(path));model.by_type('IfcExtrudedAreaSolid')[0].Depth=7.;revision=tmp_path/'changed.ifc';model.write(str(revision))
    third,_=update(revision,cache);assert third['incremental']['changed_source_elements'] and len(third['incremental']['recomputed_buildings'])==1
    assert third['incremental']['verification_status']=='passed'

def test_courtyard_block_fails_opening_topology_contract(tmp_path):
    path=tmp_path/'court.ifc';create_case(path,'courtyard');result,_=convert(path)
    selected,outputs=choose(result,QueryContract(maximum_sampled_boundary_error_m=10.,maximum_relative_volume_error=2.,protected_void_probes=((106,205,13),)))
    block=next(r for r in selected['candidates'] if r['name']=='block')
    assert not block['guards']['euler'] and not block['guards']['protected_void_probes']
    assert selected['selected']!='block'

def test_curved_generalisation_reduces_triangles_with_measured_guards(tmp_path):
    path=tmp_path/'cylinder.ifc';create_case(path,'cylinder');result,_=convert(path)
    selection,outputs=choose(result,QueryContract(maximum_sampled_boundary_error_m=.2,maximum_relative_volume_error=.1))
    accepted=[r for r in selection['candidates'] if r['status']=='admissible'];identity=next(r for r in accepted if r['name']=='identity')
    assert any(r['triangles']<identity['triangles'] for r in accepted),selection
    assert selection['selected'] in selection['pareto_candidates']

def test_missing_protected_reference_abstains(tmp_path):
    path=tmp_path/'r.ifc';create_case(path,'rectangle');result,_=convert(path)
    selected,_=choose(result,QueryContract(require_protected_void_reference=True))
    assert selected['selected'] is None

def test_independent_review_agreement_gates():
    assert reviewer_agreement([],[])['cohens_kappa'] is None
    def row(label,reviewer):return {'region_id':'x','reference_label':label,'reviewer_id':reviewer,'independent_reference':'true','evidence_uri':'independent-drawing'}
    assert reviewer_agreement([row('roof','a')],[row('wall','b')])['region_agreement_fraction']==0
    with pytest.raises(ValueError):reviewer_agreement([row('roof','a')],[row('roof','a')])

def test_fixed_hazard_sensitivity_uses_declared_scenarios():
    collection=lambda g:{'type':'FeatureCollection','features':[{'type':'Feature','id':'b','properties':{},'geometry':mapping(g)}]}
    profiles={'source':collection(box(0,0,2,2)),'block':collection(box(0,0,3,2))};hazard=collection(box(1,-2,4,4))
    r=profile_sensitivity(profiles,hazard,'EPSG:32632','synthetic_truth',[(0,0),(.1,0)],'Declared numerical sensitivity test; not observed coordinate uncertainty')
    assert len({x['hazard_sha256'] for x in r['scenarios']})==1
    assert r['profile_differences']['block']['features'][0]['change_in_exposed_area_m2']==2
    with pytest.raises(ValueError):profile_sensitivity(profiles,hazard,'EPSG:32632','synthetic_truth',[(0,0)],'')

def test_party_wall_reference_preserves_both_building_interfaces(tmp_path):
    manifest=prepare(tmp_path/'fixtures','development',8);case=manifest['cases'][-1];r,data=convert(case['input'])
    expected=json.loads(Path(case['input']).with_suffix('.expected.json').read_text())
    assert expected['expected_components']==2
    assert compare_export(data,expected,512)['all_guards_passed']
