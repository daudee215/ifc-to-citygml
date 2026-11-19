from pathlib import Path
import itertools,json,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'research'))
from ifc_citygml_v3.interactions import interaction_pairs
rows=[]
for n in [100,500,2000,5000]:
    elements=[{'vertices':[[i,0,0],[i+1,1,1]]} for i in range(n)];start=time.perf_counter();result=interaction_pairs(elements,1e-7);elapsed=time.perf_counter()-start
    expected={(i,i+1) for i in range(n-1)};assert set(result['pairs'])==expected
    rows.append({'elements':n,'all_possible_pairs':n*(n-1)//2,'indexed_pairs':len(result['pairs']),'pruned_pairs':result['pruned_pairs'],'wall_seconds':elapsed,'known_strip_adjacency_matched':True})
path=ROOT/'results/v3/index_scaling.json';path.write_text(json.dumps({'status':'completed','scope':'AABB interaction indexing only; synthetic bounds, not full IFC conversion throughput','cases':rows},indent=2));print(rows)
