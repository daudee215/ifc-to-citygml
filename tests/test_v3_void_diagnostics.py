from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from ifc_citygml_lab.fixtures import reference_mesh
from ifc_citygml_v3.diagnostics import material_contains,topology
def test_cavity_winding_combines_signed_shells():
    v,f=reference_mesh([{'kind':'box','box':(0,0,0,10,10,10)}],'rectangle',1.);a={'vertices':v,'triangles':f}
    v,f=reference_mesh([{'kind':'box','box':(3,3,3,4,4,4)}],'rectangle',1.);b={'vertices':v,'triangles':[list(reversed(x)) for x in f]}
    assert material_contains([1,1,1],[a,b]) and not material_contains([5,5,5],[a,b])
    combined={'vertices':a['vertices']+b['vertices'],'triangles':a['triangles']+[[i+len(a['vertices']) for i in face] for face in b['triangles']]}
    report=topology(combined);assert report['surface_shells']==2 and report['negative_oriented_shells']==1 and report['euler']==4
