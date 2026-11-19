"""Prospective extension and candidate comparison without modifying v0.6."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
import numpy as np
from shapely import set_precision
from shapely.geometry import shape,mapping
import shape_fidelity_experiment as first
from ifc_citygml.common import code_digest,digest,load_profile,write_json,software_versions
from ifc_citygml.benchmark import run_benchmark
from ifc_citygml.georeferencing import prepare_profile
from ifc_citygml.envelope import extract_envelopes
from ifc_citygml.exterior_writer import create_exterior_document
from ifc_citygml.validation import validate_document

ROOT=first.ROOT;OUT=ROOT/'results/experiments/shape_fidelity_002';INPUT=ROOT/'data/derived/shape_fidelity_002'


def volume_from_rings(rings):
    origin=np.asarray(rings[0][0]);total=0.
    for ring in rings:
        local=np.asarray(ring)-origin
        for i in range(1,len(local)-1):total+=float(np.dot(local[0],np.cross(local[i],local[i+1]))/6)
    return total


def metrics(path,expected,mode,validation):
    fp,rings=first.read_footprint(path)
    result={'raw':first.compare(fp,expected),'footprint':mapping(fp)}
    for grid,key in [(1e-9,'measurement_1nm'),(1e-6,'measurement_1um')]:
        ref=set_precision(shape(expected['footprint']),grid)
        result[key]=first.compare(set_precision(fp,grid),{**expected,'footprint':mapping(ref)})
    if mode=='block' or (mode=='exterior' and validation.get('independent_general_solid_validation')=='passed'):
        volume=volume_from_rings(rings)
        result['volume']={'signed_volume_m3':volume,'reference_volume_m3':expected['volume_m3'],'relative_error':volume/expected['volume_m3']-1}
    result['within_surface_thresholds']=(result['measurement_1nm']['intersection_over_union']>=.999999 and result['measurement_1nm']['boundary_hausdorff_m']<=5e-6)
    return result


def main():
    if OUT.exists():raise FileExistsError('Confirmation experiment already exists; do not overwrite')
    OUT.mkdir(parents=True);INPUT.mkdir(parents=True,exist_ok=False)
    old_manifest=json.loads((first.OUT/'manifest.json').read_text())
    write_json(OUT/'PROTOCOL.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'experiment':'shape_fidelity_002',
      'source_sha256':code_digest(),'runner_sha256':digest(Path(__file__)),'software':software_versions(),
      'earlier_study':{'protocol_sha256':digest(first.OUT/'PROTOCOL.json'),'evaluation_sha256':digest(first.OUT/'evaluation.json')},
      'design':{'existing_inputs':30,'new_inputs':30,'shape_families':list(first.SHAPES),'new_yaw_degrees':[15,60,75],'units':['metre','millimetre'],
      'new_baseline_attempts':90,'candidate_exterior_attempts':60,'total_new_attempts':150},
      'candidate':{'union_grid_m':1e-7,'validator_snap_m':1e-6,'policy':'Experimental extraction and validation adapter; not an installed production profile or new release'},
      'hypothesis':'The finer union grid removes known short-edge failures without causing fidelity or validation regressions across existing and additional rotations.',
      'measurement_policy':{'report_raw':True,'primary_comparison_grid_m':1e-9,'topology_sensitivity_grid_m':1e-6,'minimum_iou':.999999,'maximum_boundary_hausdorff_m':5e-6,'maximum_exterior_volume_relative_error':1e-6},
      'sampling_limit':'Five related analytical designs and six angles, two units; not independent real buildings. Additional angles were selected after study 001 but before study 002 execution.',
      'failure_policy':'Retain every attempt; compare baseline and candidate on the same inputs; never overwrite earlier failed attempts.',
      'frozen_releases':first.verify_frozen()})
    new=[]
    for name in first.SHAPES:
        for yaw in [15,60,75]:
            for mm in [False,True]:
                case=f'{name}_yaw{yaw}_{"mm" if mm else "m"}';source=INPUT/(case+'.ifc')
                first.create_ifc(source,name,yaw,mm)
                exp={'case':case,'shape_family':name,'yaw_degrees':yaw,'units':'millimetre' if mm else 'metre',**first.reference(name,yaw)}
                write_json(source.with_suffix('.expected.json'),exp)
                new.append({'id':case,'input':str(source),'input_sha256':digest(source),'expected_sha256':digest(source.with_suffix('.expected.json')),'provenance':{'kind':'controlled_analytic_solid','license':'CC0-1.0','new_rotation':True}})
    write_json(OUT/'manifest.json',{'format_version':1,'profiles':['block','exterior','source'],'cases':new})
    baseline=run_benchmark(OUT/'manifest.json',OUT/'baseline',progress=lambda r:print(json.dumps({'stage':'baseline',**{k:r[k] for k in ['case','mode','status']}}),flush=True))
    all_sources=old_manifest['cases']+new;write_json(OUT/'candidate_inputs.json',all_sources)
    folder=OUT/'candidate';folder.mkdir();candidates=[]
    config=load_profile('exterior');config['geometry_tolerance_m']=1e-7
    config['profile_id']='experimental_union_1e-7_validator_1e-6'
    write_json(OUT/'candidate_union_profile.json',config)
    for case in all_sources:
        source=Path(case['input']);assert digest(source)==case['input_sha256']
        started=time.perf_counter();row={'case':case['id'],'mode':'exterior','status':'failed','input':str(source),'input_sha256':digest(source),'source_sha256':code_digest(),'union_grid_m':1e-7,'validator_snap_m':1e-6,'experimental':True}
        try:
            profile=prepare_profile(load_profile(OUT/'candidate_union_profile.json'),source)
            extraction=extract_envelopes(source,profile)
            row['extraction']=extraction
            if extraction['status']!='passed':raise RuntimeError('Candidate extraction failed')
            data,links=create_exterior_document(extraction,profile)
            validation=validate_document(data,1e-6);row['validation']=validation
            row['status']=validation['status']
            target=folder/(case['id']+('.experimental.gml' if row['status']=='passed' else '.rejected_candidate.gml'))
            target.write_bytes(data);row['candidate_gml']=target.name;row['output_sha256']=digest(target)
        except Exception as e:row['error']=repr(e)
        row['wall_seconds']=time.perf_counter()-started
        report=folder/(case['id']+'.report.json');write_json(report,row)
        candidates.append({'case':row['case'],'mode':'exterior','status':row['status'],'report':report.name})
        write_json(folder/'index.json',{'status':'running','cases':candidates})
        print(json.dumps({'stage':'candidate','case':row['case'],'status':row['status']}),flush=True)
    write_json(folder/'index.json',{'status':'completed','attempts':len(candidates),'completed':sum(c['status']=='passed' for c in candidates),'cases':candidates})
    combined=[]
    for index_path in [first.OUT/'conversions/index.json',OUT/'baseline/index.json']:
        data=json.loads(index_path.read_text())
        for case in data['cases']:
            source=Path(case['input']);expected=json.loads(source.with_suffix('.expected.json').read_text())
            row={k:case[k] for k in ['case','mode','status']};row.update({k:expected[k] for k in ['shape_family','yaw_degrees','units']});row['cohort']='initial' if index_path.parent.name=='conversions' else 'additional_angles'
            report=index_path.parent/case['report'];detail=json.loads(report.read_text());row['report']=str(report.relative_to(ROOT));row['validation']=detail.get('validation')
            if case['status']=='passed':row['metrics']=metrics(index_path.parent/(case['case']+'_'+case['mode']+'.gml'),expected,case['mode'],detail['validation'])
            combined.append(row)
    evaluated=[]
    for case in candidates:
        report=folder/case['report'];detail=json.loads(report.read_text());source=Path(detail['input']);expected=json.loads(source.with_suffix('.expected.json').read_text())
        row={**case,**{k:expected[k] for k in ['shape_family','yaw_degrees','units']},'validation':detail.get('validation')}
        if case['status']=='passed':row['metrics']=metrics(folder/detail['candidate_gml'],expected,'exterior',detail['validation'])
        evaluated.append(row)
    write_json(OUT/'evaluation.json',{'baseline_attempts':180,'baseline_completed':sum(r['status']=='passed' for r in combined),'candidate_attempts':60,'candidate_completed':sum(r['status']=='passed' for r in evaluated),'baseline_rows':combined,'candidate_rows':evaluated,'frozen_releases_after':first.verify_frozen()})
    print(json.dumps({'baseline_180_completed':sum(r['status']=='passed' for r in combined),'candidate_60_completed':sum(r['status']=='passed' for r in evaluated)}))


if __name__=='__main__':main()
