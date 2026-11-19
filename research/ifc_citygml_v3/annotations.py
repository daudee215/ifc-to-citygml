"""Independent-review import and agreement; absence of reviewers is not fabricated."""
from collections import Counter
from ifc_citygml_lab.semantics import LABELS
from ifc_citygml_lab.semantics import face_predictions,evaluate_annotations

def evaluate_scoped(result,references):
    references=list(references);usable=[];pending=[]
    for row in references:
        if not row.get('input_sha256') or not row.get('output_sha256'):pending.append(row.get('region_id'));continue
        if row['input_sha256']!=result['input_sha256'] or row['output_sha256']!=result.get('output_sha256'):raise ValueError('Annotation belongs to a different source or output artifact')
        usable.append(row)
    evaluated=evaluate_annotations(face_predictions(result),usable)
    evaluated['unscoped_regions_not_scored']=len(pending);evaluated['output_sha256']=result.get('output_sha256');return evaluated
def reviewer_agreement(first,second):
    def valid(rows):
        result={}
        for r in rows:
            key=(r.get('input_sha256',''),r.get('output_sha256',''),r['region_id'])
            if key in result:raise ValueError('Duplicate region')
            if r.get('reference_label') in LABELS-{'unknown'} and r.get('reviewer_id') and str(r.get('independent_reference','')).lower()=='true' and r.get('evidence_uri'):result[key]=r
        return result
    a,b=valid(first),valid(second);keys=sorted(a.keys()&b.keys())
    if any(a[k]['reviewer_id']==b[k]['reviewer_id'] for k in keys):raise ValueError('Agreement requires distinct declared reviewers')
    if not keys:return {'status':'awaiting_two_independent_reviews','shared_scored_regions':0,'cohens_kappa':None}
    n=len(keys);ca=Counter(a[k]['reference_label'] for k in keys);cb=Counter(b[k]['reference_label'] for k in keys);observed=sum(a[k]['reference_label']==b[k]['reference_label'] for k in keys)/n;expected=sum(ca[label]*cb[label] for label in LABELS)/(n*n)
    return {'status':'evaluated_supplied_reviews','shared_scored_regions':n,'region_agreement_fraction':observed,'cohens_kappa':(observed-expected)/(1-expected) if expected<1 else None,
        'disagreements':[{'region_id':k,'first':a[k]['reference_label'],'second':b[k]['reference_label']} for k in keys if a[k]['reference_label']!=b[k]['reference_label']],
        'independence_note':'Reviewer independence and supporting evidence are asserted in supplied records, not established automatically'}
