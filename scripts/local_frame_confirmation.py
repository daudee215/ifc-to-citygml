"""Recorded local-frame experiment with 20 previously unexecuted angle controls."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
import numpy as np
import shape_fidelity_experiment as first
from shape_fidelity_confirmation import metrics
from local_frame_union_research import extract_local_frame
from union_simplification_research import mesh_statistics,simplify_extraction
from ifc_citygml.common import code_digest,digest,load_profile,write_json,software_versions
from ifc_citygml.benchmark import run_benchmark
from ifc_citygml.exterior_writer import create_exterior_document
from ifc_citygml.validation import validate_document

ROOT=first.ROOT;OUT=ROOT/'results/experiments/local_frame_003';INPUT=ROOT/'data/derived/local_frame_003'

def audit(extraction):
    components=[c for b in extraction['buildings'] for c in b['components']]
    stats=[mesh_statistics(c) for c in components]
    return {'components':len(components),'triangles':sum(s['triangles'] for s in stats),
            'minimum_edge_m':min(s['minimum_edge_m'] for s in stats),'edges_below_1um':sum(s['edges_below_1um'] for s in stats),
            'euler_sum':sum(s['euler_characteristic'] for s in stats)}

def main():
    if OUT.exists():raise FileExistsError('Existing experiment must not be overwritten')
    OUT.mkdir(parents=True);INPUT.mkdir(parents=True,exist_ok=False)
    earlier=json.loads((ROOT/'results/experiments/shape_fidelity_002/candidate_inputs.json').read_text())
    write_json(OUT/'PROTOCOL.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'experiment':'local_frame_003',
        'converter_source_sha256':code_digest(),'runner_sha256':digest(Path(__file__)),
        'adapter_sha256':digest(ROOT/'scripts/local_frame_union_research.py'),'software':software_versions(),
        'motivation':'World-frame quantisation is not invariant under rigid building rotations and can disconnect touching prisms.',
        'exploration_disclosure':['A retained fine-grid U shape at 45 degrees fails after Manifold.simplify(1e-6); short edge unchanged.',
            'A local-frame prototype on that same known case passes both MultiSurface and Solid and yields one component.'],
        'design':{'earlier_inputs':60,'new_angles':[22.5,67.5],'new_inputs':20,'new_baseline_exterior_attempts':20,'local_frame_attempts':80},
        'fixed_candidate':{'union_grid_m':1e-6,'validator_snap_m':1e-6,'frame':'gravity aligned IFC building placement','simplification':False},
        'acceptance':{'minimum_iou_1nm':.999999,'maximum_boundary_distance_m':5e-6,'maximum_absolute_volume_relative_error':1e-6,
            'connected_components':1,'expected_euler':{'courtyard':0,'other':2},'short_edges_below_1um':0,
            'both_declared_surface_and_stronger_solid_pass':True},
        'hypothesis':'Local-frame snapping preserves intended contacts and topology across the tested rotations without changing validator tolerance.',
        'limits':'20 additional inputs from the same five designs are a prospective angular check, not independent real buildings; prototype already inspected one old case.',
        'frozen_releases':first.verify_frozen()})
    new=[]
    for family in first.SHAPES:
        for yaw in [22.5,67.5]:
            for mm in [False,True]:
                case=f'{family}_yaw{str(yaw).replace(".","p")}_{"mm" if mm else "m"}';source=INPUT/(case+'.ifc')
                first.create_ifc(source,family,yaw,mm)
                write_json(source.with_suffix('.expected.json'),{'case':case,'shape_family':family,'yaw_degrees':yaw,
                    'units':'millimetre' if mm else 'metre',**first.reference(family,yaw)})
                new.append({'id':case,'input':str(source),'input_sha256':digest(source),'expected_sha256':digest(source.with_suffix('.expected.json')),
                    'provenance':{'kind':'controlled_analytic_solid','license':'CC0-1.0','prospective_angle':True}})
    write_json(OUT/'manifest.json',{'format_version':1,'profiles':['exterior'],'cases':new})
    run_benchmark(OUT/'manifest.json',OUT/'baseline',progress=lambda r:print('baseline',r['case'],r['status'],flush=True))
    sources=earlier+new;write_json(OUT/'all_inputs.json',sources)
    rows=[];folder=OUT/'candidate';folder.mkdir()
    for case in sources:
        source=Path(case['input']);assert digest(source)==case['input_sha256'];expected=json.loads(source.with_suffix('.expected.json').read_text())
        row={'case':case['id'],'mode':'exterior','status':'failed','input':str(source),'input_sha256':digest(source),
            'cohort':'prospective_angles' if case in new else 'earlier_controls','experimental':True,**{k:expected[k] for k in ['shape_family','yaw_degrees','units']}}
        start=time.perf_counter()
        try:
            profile=load_profile('exterior');extraction=extract_local_frame(source,profile);row['extraction']=extraction
            if extraction['status']!='passed':raise ValueError('Extraction failed')
            data,links=create_exterior_document(extraction,profile);validation=validate_document(data,1e-6)
            row['validation']=validation;row['status']=validation['status'];row['source_links']=links
            path=folder/(case['id']+('.experimental.gml' if row['status']=='passed' else '.rejected_candidate.gml'))
            path.write_bytes(data);row['candidate_gml']=path.name;row['output_sha256']=digest(path);row['mesh_audit']=audit(extraction)
            if row['status']=='passed':
                row['metrics']=metrics(path,expected,'exterior',validation)
                row['all_research_guards_passed']=(row['metrics']['within_surface_thresholds'] and
                    abs(row['metrics'].get('volume',{}).get('relative_error',float('inf')))<=1e-6 and row['mesh_audit']['components']==1 and
                    row['mesh_audit']['euler_sum']==(0 if row['shape_family']=='courtyard' else 2) and row['mesh_audit']['edges_below_1um']==0)
        except Exception as error:row['error']=repr(error)
        row['wall_seconds']=time.perf_counter()-start;report=folder/(case['id']+'.report.json');write_json(report,row)
        brief={k:v for k,v in row.items() if k not in ['extraction','validation','source_links']};brief['report']=report.name;rows.append(brief)
        write_json(folder/'index.json',{'status':'running','cases':rows});print('local_frame',row['case'],row['status'],row.get('all_research_guards_passed'),flush=True)
    write_json(folder/'index.json',{'status':'completed','attempts':len(rows),'completed':sum(r['status']=='passed' for r in rows),'cases':rows})
    old=json.loads((ROOT/'results/experiments/shape_fidelity_002/evaluation.json').read_text())['baseline_rows']
    baseline=[]
    for r in old:
        if r['mode']!='exterior':continue
        detail=json.loads((ROOT/r['report']).read_text());baseline.append({**{k:r[k] for k in ['case','shape_family','yaw_degrees','units','status','report']},
            'cohort':'earlier_controls','mesh_audit':audit(detail['extraction']),'metrics':r.get('metrics')})
    for r in json.loads((OUT/'baseline/index.json').read_text())['cases']:
        detail=json.loads((OUT/'baseline'/r['report']).read_text());expected=json.loads(Path(r['input']).with_suffix('.expected.json').read_text())
        row={**{k:r[k] for k in ['case','status']},**{k:expected[k] for k in ['shape_family','yaw_degrees','units']},'cohort':'prospective_angles',
            'report':str((OUT/'baseline'/r['report']).relative_to(ROOT)),'mesh_audit':audit(detail['extraction'])}
        if r['status']=='passed':row['metrics']=metrics(OUT/'baseline'/(r['case']+'_exterior.gml'),expected,'exterior',detail['validation'])
        baseline.append(row)
    write_json(OUT/'evaluation.json',{'baseline':baseline,'candidate':rows,'frozen_releases_after':first.verify_frozen()})
    print('Finished experiment with all retained attempts',flush=True)

if __name__=='__main__':main()
