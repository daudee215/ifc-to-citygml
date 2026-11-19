"""Check signed volume independently against a cube of known volume."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from shape_fidelity_confirmation import volume_from_rings

def cube():
    v=[[0,0,0],[2,0,0],[2,3,0],[0,3,0],[0,0,4],[2,0,4],[2,3,4],[0,3,4]]
    return [[v[i] for i in f] for f in [[0,3,2,1,0],[4,5,6,7,4],[0,1,5,4,0],[1,2,6,5,1],[2,3,7,6,2],[3,0,4,7,3]]]

@pytest.mark.parametrize('offset',[[0,0,0],[100,200,10],[400000,5000000,100]])
def test_signed_volume_preserves_known_volume_under_translation(offset):
    rings=[[[p[i]+offset[i] for i in range(3)] for p in ring] for ring in cube()]
    assert volume_from_rings(rings)==pytest.approx(24,abs=1e-10)

def test_signed_volume_detects_reversed_orientation():
    assert volume_from_rings([list(reversed(ring)) for ring in cube()])==pytest.approx(-24)
