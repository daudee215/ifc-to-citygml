"""Independent rigid-placement and unit checks for the research adapter."""
from pathlib import Path
from types import SimpleNamespace
import sys
import numpy as np
import pytest
import ifcopenshell
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from shape_fidelity_experiment import create_ifc
from local_frame_union_research import building_frame,to_local,to_world

@pytest.mark.parametrize('millimetres',[False,True])
def test_hierarchical_building_frame_uses_si_translation(tmp_path,millimetres):
    path=tmp_path/'frame.ifc';create_ifc(path,'l_shape',37.5,millimetres)
    model=ifcopenshell.open(str(path));frame=building_frame(model,model.by_type('IfcBuilding')[0])
    assert frame[:3,3]==pytest.approx([100,200,10])
    angle=np.deg2rad(37.5)
    assert frame[:3,0]==pytest.approx([np.cos(angle),np.sin(angle),0])

def test_roundtrip_preserves_distances_and_coordinates():
    angle=.731;frame=np.eye(4);frame[:2,:2]=[[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]];frame[:3,3]=[395000,4982000,200]
    local=np.array([[0,0,0],[12,8,6],[3,7,2]],dtype=float)
    world=to_world(local,frame)
    assert to_local(world,frame)==pytest.approx(local,abs=1e-9)
    assert np.linalg.norm(world[1]-world[0])==pytest.approx(np.sqrt(244),abs=1e-9)

def test_tilted_frame_is_explicitly_rejected(monkeypatch):
    matrix=np.eye(4);angle=.1;matrix[1:3,1:3]=[[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]]
    monkeypatch.setattr('ifcopenshell.util.placement.get_local_placement',lambda p:matrix)
    monkeypatch.setattr('ifcopenshell.util.unit.calculate_unit_scale',lambda m:1.)
    with pytest.raises(ValueError,match='gravity aligned'):building_frame(None,SimpleNamespace(ObjectPlacement=None))

def test_reflected_frame_is_explicitly_rejected(monkeypatch):
    matrix=np.eye(4);matrix[0,0]=-1
    monkeypatch.setattr('ifcopenshell.util.placement.get_local_placement',lambda p:matrix)
    monkeypatch.setattr('ifcopenshell.util.unit.calculate_unit_scale',lambda m:1.)
    with pytest.raises(ValueError,match='proper rigid'):building_frame(None,SimpleNamespace(ObjectPlacement=None))
