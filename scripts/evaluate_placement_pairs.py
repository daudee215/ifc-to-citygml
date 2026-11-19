"""Independently compare world geometry across placement hierarchy refactoring."""
from pathlib import Path
import json
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
from ifc_citygml_lab.metrics import read_geometry,sampled_surface_distance
from ifc_citygml.common import write_json,digest

def max_nearest(a,b):
    a=np.asarray(a);b=np.asarray(b)
    return max(float(np.sqrt(((a[:,None,:]-b[None,:,:])**2).sum(axis=2)).min(axis=1).max()),float(np.sqrt(((b[:,None,:]-a[None,:,:])**2).sum(axis=2)).min(axis=1).max()))

def main():
    folder=ROOT/'results/expansion_v2/smoke';manifest=ROOT/'data/derived/expansion_v1/smoke/manifest.json';rows=[]
    for pair in json.loads(manifest.read_text())['placement_pairs']:
        reports=[json.loads((folder/'guarded'/(pair[key]+'.report.json')).read_text()) for key in ['first','second']]
        points=[np.vstack([e['vertices'] for b in r['source_evidence']['buildings'] for e in b['elements']]) for r in reports]
        source_difference=max_nearest(*points);meshes=[read_geometry((folder/'guarded'/r['output_file']).read_bytes())['mesh'] for r in reports]
        surface=sampled_surface_distance(*meshes,512)
        rows.append({**pair,'source_world_vertex_set_max_nearest_m':source_difference,'output_sampled_surface_distance':surface,'source_invariant_passed':source_difference<1e-10,'output_invariant_passed':surface['sampled_maximum_m']<1e-7,'both_operationally_accepted':all(r['status']=='accepted' for r in reports)})
    write_json(ROOT/'results/expansion_v2/placement_refactoring.json',{'manifest_sha256':digest(manifest),'pairs':rows,'all_passed':all(r['source_invariant_passed'] and r['output_invariant_passed'] and r['both_operationally_accepted'] for r in rows),'scope':'Finite vertex-set and sampled surface checks, not exact arithmetic equivalence'})
    print('Placement pairs',len(rows),'passed',sum(r['source_invariant_passed'] and r['output_invariant_passed'] for r in rows))

if __name__=='__main__':main()
