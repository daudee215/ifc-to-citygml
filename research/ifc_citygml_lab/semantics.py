"""Evidence-derived hints and independent-reference evaluation without invented labels."""
from collections import Counter,defaultdict
import csv
import math
import numpy as np

LABELS={'roof','wall','ground','outer_floor','outer_ceiling','opening','door','window','unknown'}

def annotation_template(result):
    rows=[]
    for link in result.get('source_links',[]):
        for face in link.get('surface_contributions',[]):
            rows.append({'region_id':face['polygon_id'],'ifc_global_id':face['ifc_global_id'],'reference_label':'',
                'reference_host_guid':'','area_m2':'','reviewer_id':'','independent_reference':'','evidence_uri':'',
                'source_note':'Blank review template, not an annotation or ground truth'})
    return rows

def face_predictions(result):
    rows=[]
    hints={'RoofSurface':'roof','WallSurface':'wall','GroundSurface':'ground','OuterFloorSurface':'outer_floor','OuterCeilingSurface':'outer_ceiling','DoorSurface':'door','WindowSurface':'window'}
    contributions=[r for l in result.get('source_links',[]) for r in l.get('surface_contributions',[])]
    byid={r['polygon_id']:r for r in contributions}
    for building,link in zip(result.get('extraction',{}).get('buildings',[]),result.get('source_links',[])):
        for j,component in enumerate(building['components']):
            v=np.asarray(component['vertices'])
            for i,face in enumerate(component['triangles']):
                key=f"{link['citygml_id']}_c{j}_t{i}";record=byid[key];points=v[face]
                rows.append({'region_id':key,'label':hints.get(record['heuristic_hint'],'unknown'),
                    'host_guid':None,'area_m2':float(np.linalg.norm(np.cross(points[1]-points[0],points[2]-points[0]))/2),
                    'evidence_kind':'source_class_and_orientation_heuristic','independent_semantic_truth':False})
    return rows

def evaluate_annotations(predictions,references):
    predictions=list(predictions);references=list(references);p={r['region_id']:r for r in predictions}
    if len(p)!=len(predictions):raise ValueError('Duplicate prediction region identity')
    seen=set();usable=[];pending=[]
    for r in references:
        key=r.get('region_id')
        if key in seen:raise ValueError('Duplicate annotation region identity')
        seen.add(key);label=r.get('reference_label','')
        if not label or not r.get('reviewer_id') or str(r.get('independent_reference','')).lower()!='true' or not r.get('evidence_uri'):
            pending.append(key);continue
        if label not in LABELS:raise ValueError('Unknown reference semantic label')
        if key not in p:raise ValueError('Reference region not represented in predictions')
        area=float(r.get('area_m2') or p[key]['area_m2'])
        if not math.isfinite(area) or area<=0:raise ValueError('Reference area must be finite and positive')
        if label!='unknown':usable.append((r,p[key],area))
    if not usable:return {'status':'awaiting_independent_reference','scored_regions':0,'pending_regions':len(pending),'metrics':None,
        'reason':'No complete independent reference annotations supplied; heuristic agreement is not used as truth'}
    confusion=defaultdict(float);counts=Counter();hostcorrect=hosttotal=0;correct=total=0.
    for r,pred,area in usable:
        truth=r['reference_label'];guess=pred['label'];confusion[truth,guess]+=area;counts[truth,guess]+=1;total+=area;correct+=area*(truth==guess)
        if r.get('reference_host_guid'):
            hosttotal+=1;hostcorrect+=pred.get('host_guid')==r['reference_host_guid']
    perclass={}
    for label in sorted({r['reference_label'] for r,p,a in usable}):
        tp=confusion[label,label];actual=sum(v for (a,b),v in confusion.items() if a==label);predicted=sum(v for (a,b),v in confusion.items() if b==label)
        perclass[label]={'area_precision':tp/predicted if predicted else None,'area_recall':tp/actual if actual else None}
    return {'status':'evaluated_supplied_reference','scored_regions':len(usable),'pending_regions':len(pending),
        'area_weighted_accuracy':correct/total,'per_class':perclass,'area_confusion':[{'truth':a,'prediction':b,'area_m2':v,'regions':counts[a,b]} for (a,b),v in sorted(confusion.items())],
        'host_correct':hostcorrect,'host_total':hosttotal,'reference_note':'Reference independence is asserted in supplied provenance, not inferred by the evaluator'}

def export_annotation_csv(path,result):
    rows=annotation_template(result)
    with open(path,'w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['region_id','reference_label','reviewer_id','independent_reference','evidence_uri']);writer.writeheader();writer.writerows(rows)
    return rows
