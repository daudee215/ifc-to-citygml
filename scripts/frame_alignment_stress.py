"""Prospective test of geometry oblique to the IFC building placement frame."""
from datetime import datetime,timezone
import math
from pathlib import Path
import json
import ifcopenshell
import shape_fidelity_experiment as first
from shape_fidelity_confirmation import metrics
from local_frame_union_research import extract_local_frame
from local_frame_confirmation import audit
from ifc_citygml.common import code_digest,digest,load_profile,write_json
from ifc_citygml.envelope import extract_envelopes
from ifc_citygml.exterior_writer import create_exterior_document
from ifc_citygml.validation import validate_document

ROOT=first.ROOT;OUT=ROOT/'results/experiments/frame_alignment_004';INPUT=ROOT/'data/derived/frame_alignment_004'

def rotate_contents(path,degrees):
    model=ifcopenshell.open(str(path));a=math.radians(degrees);c,s=math.cos(a),math.sin(a)
    for wall in model.by_type('IfcWall'):
        placement=wall.ObjectPlacement.RelativePlacement;x,y,z=placement.Location.Coordinates
        placement.Location.Coordinates=(c*x-s*y,s*x+c*y,z)
        placement.RefDirection.DirectionRatios=(c,s,0.)
    model.write(str(path))

def main():
    if OUT.exists():raise FileExistsError('Do not overwrite the stress experiment')
    OUT.mkdir(parents=True);INPUT.mkdir(parents=True,exist_ok=False)
    write_json(OUT/'PROTOCOL.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'runner_sha256':digest(Path(__file__)),
        'adapter_sha256':digest(ROOT/'scripts/local_frame_union_research.py'),'converter_source_sha256':code_digest(),
        'question':'Does local frame quantisation retain its controlled success when source geometry is oblique to that frame?',
        'design':{'families':['l_shape','u_shape','courtyard','setback'],'contents_yaw_degrees':[7,23],
            'building_yaw_degrees':[0,37],'units':['metre','millimetre'],'inputs':32,'attempts':64},
        'fixed_settings':{'union_grid_m':1e-6,'validator_snap_m':1e-6,'tuning_after_outcomes':False},
        'comparison':'World frame baseline versus unchanged local frame research adapter; every attempt retained.',
        'reference':'Declared prisms rotated by sum of building and contents angles; translation stays 100,200,10 metres.',
        'topology':'One component; Euler 0 courtyard and 2 otherwise; no mesh edges below 1 micrometre.',
        'limits':'Same four analytic forms; tests alignment dependency rather than independent real buildings.',
        'frozen_releases':first.verify_frozen()})
    cases=[]
    for family in ['l_shape','u_shape','courtyard','setback']:
        for inner in [7,23]:
            for outer in [0,37]:
                for mm in [False,True]:
                    case=f'{family}_inner{inner}_outer{outer}_{"mm" if mm else "m"}';path=INPUT/(case+'.ifc')
                    first.create_ifc(path,family,outer,mm);rotate_contents(path,inner)
                    expected={'case':case,'shape_family':family,'contents_yaw_degrees':inner,'building_yaw_degrees':outer,
                        'units':'millimetre' if mm else 'metre',**first.reference(family,inner+outer)}
                    write_json(path.with_suffix('.expected.json'),expected)
                    cases.append({'case':case,'input':str(path),'input_sha256':digest(path),'expected_sha256':digest(path.with_suffix('.expected.json'))})
    write_json(OUT/'manifest.json',cases);rows=[]
    for case in cases:
        path=Path(case['input']);expected=json.loads(path.with_suffix('.expected.json').read_text())
        for arm,extract in [('world_frame',extract_envelopes),('building_frame',extract_local_frame)]:
            folder=OUT/arm;folder.mkdir(exist_ok=True)
            row={**case,**{k:expected[k] for k in ['shape_family','contents_yaw_degrees','building_yaw_degrees','units']},'arm':arm,'status':'failed'}
            try:
                profile=load_profile('exterior');extraction=extract(path,profile);row['extraction']=extraction
                if extraction['status']!='passed':raise ValueError('Extraction failed')
                row['mesh_audit']=audit(extraction)
                data,links=create_exterior_document(extraction,profile);validation=validate_document(data,1e-6)
                row['status']=validation['status'];row['validation']=validation
                target=folder/(case['case']+('.experimental.gml' if row['status']=='passed' else '.rejected_candidate.gml'))
                target.write_bytes(data);row['output']=target.name;row['output_sha256']=digest(target)
                if row['status']=='passed':row['metrics']=metrics(target,expected,'exterior',validation)
                a=row['mesh_audit'];row['expected_topology']=(a['components']==1 and a['euler_sum']==(0 if row['shape_family']=='courtyard' else 2))
                row['all_guards_passed']=(row['status']=='passed' and validation.get('independent_general_solid_validation')=='passed'
                    and row['expected_topology'] and a['edges_below_1um']==0 and row['metrics']['within_surface_thresholds']
                    and abs(row['metrics'].get('volume',{}).get('relative_error',float('inf')))<1e-6)
            except Exception as error:row['error']=repr(error)
            report=folder/(case['case']+'.report.json');write_json(report,row)
            brief={k:v for k,v in row.items() if k not in ['extraction','validation']};brief['report']=str(report.relative_to(ROOT));rows.append(brief)
            write_json(OUT/'index.json',{'status':'running','cases':rows});print(case['case'],arm,row['status'],row.get('all_guards_passed'),flush=True)
    write_json(OUT/'index.json',{'status':'completed','attempts':64,'cases':rows,'frozen_releases_after':first.verify_frozen()})

if __name__=='__main__':main()
