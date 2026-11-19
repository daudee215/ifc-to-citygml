"""Summarise primary metrics and separately labelled post hoc diagnostics."""
import csv
import json
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np
from shapely.geometry import shape
from shape_fidelity_experiment import ROOT,OUT
from ifc_citygml.external_validation import geometry_adapter
from ifc_citygml.common import write_json,digest


def main():
    data=json.loads((OUT/'evaluation.json').read_text());rows=data['rows']
    successful=[r for r in rows if r['status']=='passed'];surfaces=[r for r in successful if r['mode']!='block'];blocks=[r for r in successful if r['mode']=='block']
    unit_comparisons=[]
    groups=defaultdict(dict)
    for row in successful:groups[(row['shape_family'],row['yaw_degrees'],row['mode'])][row['units']]=row
    for (family,yaw,mode),pair in groups.items():
        if len(pair)!=2:continue
        a=shape(pair['metre']['footprint_geojson']);b=shape(pair['millimetre']['footprint_geojson'])
        unit_comparisons.append({'family':family,'yaw':yaw,'mode':mode,'symmetric_difference_m2':a.symmetric_difference(b).area,'boundary_hausdorff_m':a.boundary.hausdorff_distance(b.boundary)})
    precision=json.loads((OUT/'diagnostics/measurement_precision.json').read_text())['rows']
    diagnostic=json.loads((OUT/'diagnostics/courtyard_grid_sensitivity.json').read_text())['rows']
    nearest=[]
    candidate=OUT/'diagnostics/courtyard_m_grid1e-06.candidate.gml'
    city,_=geometry_adapter(candidate.read_bytes());vertices=np.array(city['vertices'])
    for obj in city['CityObjects'].values():
        for gi,geometry in enumerate(obj['geometry']):
            for fi,face in enumerate(geometry['boundaries']):
                for ring in face:
                    for a,b in zip(ring,ring[1:]+ring[:1]):
                        length=float(np.linalg.norm(vertices[a]-vertices[b]))
                        if length<1e-6:nearest.append({'geometry_index':gi,'face_index':fi,'edge_m':length})
    summary={'primary':{'inputs':30,'design_families':5,'attempts':90,'completed':data['completed'],'failed':data['failed'],
      'by_profile':{m:{'attempts':30,'completed':sum(r['status']=='passed' for r in rows if r['mode']==m)} for m in ['block','exterior','source']},
      'all_blocks_match_analytic_aabb':all(r['matches_analytic_aabb'] for r in blocks),
      'max_block_footprint_overestimate_percent':max(r['footprint']['area_overestimate_percent'] for r in blocks),
      'max_block_volume_overestimate_percent':max(r['volume']['overestimate_percent'] for r in blocks),
      'min_block_iou':min(r['footprint']['intersection_over_union'] for r in blocks),
      'min_completed_surface_iou':min(r['footprint']['intersection_over_union'] for r in surfaces),
      'surface_registered_metrics_passed':sum(r['surface_footprint_within_registered_tolerance'] for r in surfaces),
      'surface_registered_metrics_evaluated':len(surfaces),
      'max_exterior_boundary_hausdorff_m':max(r['footprint']['boundary_hausdorff_m'] for r in surfaces if r['mode']=='exterior'),
      'raw_source_boundary_max_m':max(r['footprint']['boundary_hausdorff_m'] for r in surfaces if r['mode']=='source'),
      'completed_surface_solid_diagnostics':dict(Counter(r['solid_diagnostic'] for r in surfaces))},
      'post_hoc':{'grid_validation_attempts':len(diagnostic),'target_passes':sum(r['target_surface_status']=='passed' for r in diagnostic),
       'short_edges_on_reproduced_candidate':nearest,'measurement_grids_m':[1e-9,1e-8,1e-7,1e-6],
       'surface_metrics_passed_with_1nm_measurement_grid':sum(r['intersection_over_union']>=.999999 and r['boundary_hausdorff_m']<=5e-6 for r in precision if r['mode']!='block' and r['measurement_grid_m']==1e-9),
       'source_courtyard_holes_with_1nm_grid':[r['exported_holes'] for r in precision if r['mode']=='source' and r['case'].startswith('courtyard') and r['measurement_grid_m']==1e-9],
       'all_surface_courtyard_holes_with_1um_grid':[r['exported_holes'] for r in precision if r['mode']!='block' and r['case'].startswith('courtyard') and r['measurement_grid_m']==1e-6]},
      'unit_pairs':{'completed_pairs':len(unit_comparisons),'max_symmetric_difference_m2':max(r['symmetric_difference_m2'] for r in unit_comparisons),'max_boundary_hausdorff_m':max(r['boundary_hausdorff_m'] for r in unit_comparisons),'pairs':unit_comparisons},
      'evidence_hashes':{str(p.relative_to(ROOT)):digest(p) for p in [OUT/'PROTOCOL.json',OUT/'evaluation.json',OUT/'diagnostics/PLAN.json',OUT/'diagnostics/courtyard_grid_sensitivity.json']}}
    write_json(OUT/'summary.json',summary)
    fields=['case','shape_family','yaw_degrees','units','mode','status','intersection_over_union','area_overestimate_percent','boundary_hausdorff_m','reference_holes','exported_holes','volume_overestimate_percent']
    with (OUT/'metrics.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for row in rows:
            values={k:row[k] for k in fields if k in row};values.update({k:v for k,v in row.get('footprint',{}).items() if k in fields});values['volume_overestimate_percent']=row.get('volume',{}).get('overestimate_percent');writer.writerow(values)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['unit_pairs','evidence_hashes']}))


if __name__=='__main__':main()
