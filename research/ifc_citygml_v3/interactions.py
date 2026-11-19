"""Conservative sweep broad phase; excluded AABBs cannot meet within edit budget."""
import numpy as np
from ifc_citygml_lab.evidence import convex_relation

def bounds(elements):
    return [(np.asarray(e['vertices']).min(0),np.asarray(e['vertices']).max(0)) for e in elements]

def interaction_pairs(elements,influence_m,maximum_pairs=20000):
    boxes=bounds(elements);order=sorted(range(len(elements)),key=lambda i:boxes[i][0][0]);active=[];pairs=[]
    for i in order:
        lo,hi=boxes[i];active=[j for j in active if boxes[j][1][0]+2*influence_m>=lo[0]]
        for j in active:
            a,b=boxes[j]
            if np.all(hi+2*influence_m>=a) and np.all(b+2*influence_m>=lo):
                pairs.append(tuple(sorted((i,j))))
                if len(pairs)>maximum_pairs:return {'status':'budget_exceeded','pairs':[],'observed_pairs':len(pairs),'maximum_pairs':maximum_pairs}
        active.append(i)
    return {'status':'complete','pairs':sorted(pairs),'all_pair_count':len(elements)*(len(elements)-1)//2,
            'pruned_pairs':len(elements)*(len(elements)-1)//2-len(pairs),'influence_m':influence_m,
            'pruning_rule':'At least one AABB axis gap exceeds twice the maximum per-element displacement; excluded pairs cannot form contacts under that budget'}

def relation_evidence(elements,policy,connections=()):
    magnitude=max((float(np.abs(e['vertices']).max()) for e in elements),default=1.)
    numerical=max(policy.numerical_floor_m,8*float(np.spacing(magnitude)))
    ambiguity=max(policy.ambiguity_distance_m,numerical)
    broad=interaction_pairs(elements,max(policy.maximum_edit_m,ambiguity),policy.maximum_interaction_pairs)
    if broad['status']!='complete':return {'status':'unresolved','relations':[],'ambiguities':[broad],'broad_phase':broad}
    asserted={frozenset((c['source'],c['target'])):c for c in connections if c['kind']=='supported_connection_plane'}
    relations=[];ambiguous=[]
    for i,j in broad['pairs']:
        r=convex_relation(elements[i],elements[j],policy.numerical_floor_m)
        gap=r.get('separating_axis_gap_m');r['coordinate_roundoff_indicator_m']=numerical;r['intent']='source_geometry_only'
        key=frozenset((r['source'],r['target']))
        if r['relation'].startswith('unresolved') or r['relation']=='lower_dimensional_contact':ambiguous.append(r)
        elif gap is not None and policy.numerical_floor_m<abs(gap)<=ambiguity and key not in asserted:
            r['intent']='ambiguous_near_contact';ambiguous.append(r)
        relations.append(r)
    return {'status':'unresolved' if ambiguous else 'complete','relations':relations,'ambiguities':ambiguous,'broad_phase':broad,
            'limits':'Coordinate ULP and declared ambiguity distance are deterministic review indicators, not probabilistic uncertainty or surveyed accuracy'}
