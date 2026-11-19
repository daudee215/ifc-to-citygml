"""Verify composed source placements against analytical corners in SI units."""
import math
from pathlib import Path
import sys
import ifcopenshell
import ifcopenshell.geom
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from shape_fidelity_experiment import create_ifc
from frame_alignment_stress import rotate_contents

@pytest.mark.parametrize('mm',[False,True])
@pytest.mark.parametrize('outer',[0,37])
def test_oblique_contents_preserve_expected_world_corners(tmp_path,mm,outer):
    path=tmp_path/'oblique.ifc';create_ifc(path,'u_shape',outer,mm);rotate_contents(path,7)
    model=ifcopenshell.open(str(path));settings=ifcopenshell.geom.settings();settings.set('use-world-coords',True)
    # Third prism starts at x=3,y=0 and has width=6,depth=3,height=6.
    element=next(w for w in model.by_type('IfcWall') if w.Name=='Analytical prism 2')
    source=ifcopenshell.geom.create_shape(settings,element);actual=np.asarray(source.geometry.verts).reshape(-1,3)
    a=math.radians(outer+7)
    for x,y,z in [(3,0,0),(9,0,0),(9,3,6),(3,3,6)]:
        expected=np.array([100+x*math.cos(a)-y*math.sin(a),200+x*math.sin(a)+y*math.cos(a),10+z])
        assert np.linalg.norm(actual-expected,axis=1).min()<1e-10
