"""Post hoc diagnostics retained separately from the registered experiment."""
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from shapely import set_precision
from shapely.geometry import shape, mapping
from shape_fidelity_experiment import OUT, INPUT, ROOT, compare, read_footprint
from ifc_citygml.common import load_profile, digest, write_json, code_digest
from ifc_citygml.georeferencing import prepare_profile
from ifc_citygml.envelope import extract_envelopes
from ifc_citygml.exterior_writer import create_exterior_document
from ifc_citygml.validation import validate_document


def main():
    dest=OUT/'diagnostics';dest.mkdir(exist_ok=True)
    if (dest/'PLAN.json').exists():raise FileExistsError('Diagnostic already planned; preserve the existing run')
    write_json(dest/'PLAN.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'stage':'post_hoc_after_primary_results',
      'primary_evaluation_sha256':digest(OUT/'evaluation.json'),'converter_source_sha256':code_digest(),
      'measurement_grids_m':[1e-9,1e-8,1e-7,1e-6],
      'measurement_policy':'Snap the derived projected footprint and reference only, for a separate numerical sensitivity calculation. Do not change IFC or GML. Retain raw registered metrics.',
      'courtyard_union_grids_m':[1e-6,1e-7,1e-8,1e-9],'validator_snap_tolerances_m':[1e-6,1e-9],
      'hypothesis':'Rotated courtyard union triangulation creates edges shorter than validator snapping tolerance. Separate production union grid from validator snapping to isolate the effect.',
      'status_policy':'Candidate GML is diagnostic only. Never replace or relabel the failed primary exterior attempts.'})
    evaluation=json.loads((OUT/'evaluation.json').read_text());measurements=[]
    for row in evaluation['rows']:
        if row['status']!='passed':continue
        raw=shape(row['footprint_geojson']);expected=json.loads((INPUT/(row['case']+'.expected.json')).read_text())
        reference=shape(expected['footprint'])
        for grid in [1e-9,1e-8,1e-7,1e-6]:
            measured=set_precision(raw,grid);expected_copy={**expected,'footprint':mapping(set_precision(reference,grid))}
            measurements.append({'case':row['case'],'mode':row['mode'],'measurement_grid_m':grid,'raw_geometry_type':raw.geom_type,
               'raw_holes':row['footprint']['exported_holes'],'raw_area_m2':raw.area,'snapped_area_change_m2':measured.area-raw.area,
               **compare(measured,expected_copy)})
    write_json(dest/'measurement_precision.json',{'stage':'post_hoc','rows':measurements})
    validations=[]
    for unit in ['m','mm']:
        source=INPUT/f'courtyard_yaw30_{unit}.ifc'
        for grid in [1e-6,1e-7,1e-8,1e-9]:
            cfg=load_profile('exterior');cfg['geometry_tolerance_m']=grid
            config=dest/f'courtyard_{unit}_grid{grid}.profile.json';write_json(config,cfg)
            profile=prepare_profile(load_profile(config),source)
            extraction=extract_envelopes(source,profile)
            write_json(dest/f'courtyard_{unit}_grid{grid}.extraction.json',extraction)
            if extraction['status']!='passed':
                validations.append({'unit':unit,'union_grid_m':grid,'extraction_status':extraction['status']});continue
            data,links=create_exterior_document(extraction,profile)
            candidate=dest/f'courtyard_{unit}_grid{grid}.candidate.gml';candidate.write_bytes(data)
            for snap in [1e-6,1e-9]:
                result=validate_document(data,snap)
                report=dest/f'courtyard_{unit}_grid{grid}_snap{snap}.validation.json';write_json(report,result)
                external=result['external_validation']
                row={'unit':unit,'union_grid_m':grid,'validator_snap_m':snap,'schema_valid':result['schema_valid'],
                     'target_surface_status':result.get('independent_surface_validation'),'solid_status':result['independent_general_solid_validation'],
                     'errors':external['report']['all_errors'],'candidate':candidate.name,'candidate_sha256':digest(candidate),
                     'promoted_to_primary_result':False,'validation_report':report.name,
                     'ring_sha256':external['adapter']['ring_sha256'],'validator_parameters':external['report']['parameters']}
                if grid==1e-6 and snap==1e-6:
                    primary=json.loads((OUT/'conversions'/f'courtyard_yaw30_{unit}_exterior.report.json').read_text())
                    assert row['ring_sha256']==primary['validation']['external_validation']['adapter']['ring_sha256']
                validations.append(row);print(json.dumps({k:row[k] for k in ('unit','union_grid_m','validator_snap_m','target_surface_status','errors')}),flush=True)
    write_json(dest/'courtyard_grid_sensitivity.json',{'stage':'post_hoc','rows':validations})


if __name__=='__main__':main()
