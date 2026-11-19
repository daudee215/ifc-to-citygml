from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from ifc_citygml_v3.limits import geometry_eligibility
def test_large_convex_matrix_is_refused_before_allocation():
    r=geometry_eligibility(272418,544836)
    assert r['status']=='resource_budget_exceeded' and r['convex_matrix_entries']==272418*544836
    assert geometry_eligibility(100,200)['status']=='eligible'
