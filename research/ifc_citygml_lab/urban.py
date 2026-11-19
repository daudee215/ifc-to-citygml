"""Horizontal exposure and profile effects with explicit frame and data gates."""
from pathlib import Path
import json
import math
import hashlib
from shapely import union_all
from shapely.geometry import shape,box,mapping
from pyproj import CRS
from ifc_citygml.common import digest

def _collection_crs(collection,declared):
    crs=CRS.from_user_input(declared)
    name=collection.get('crs',{}).get('properties',{}).get('name')
    if name and CRS.from_user_input(name)!=crs:raise ValueError('Collection CRS conflicts with declared coordinate frame')
    if not crs.is_projected or not all(abs(a.unit_conversion_factor-1)<1e-12 for a in crs.axis_info[:2]):raise ValueError('Area analysis requires a projected metre CRS')
    return crs

def exposure(buildings,hazard,crs,coordinate_status,extent=None,allow_metadata_only=False):
    if coordinate_status not in {'independent_checks_available','official_context','synthetic_truth','metadata_only'}:raise ValueError('No established shared horizontal frame')
    if coordinate_status=='metadata_only' and not allow_metadata_only:raise ValueError('Metadata-only overlay needs explicit scoped opt in')
    _collection_crs(buildings,crs);_collection_crs(hazard,crs)
    hazards=[shape(f['geometry']) for f in hazard['features']]
    if any(not g.is_valid for g in hazards):raise ValueError('Invalid hazard geometry; no silent repair')
    mask=union_all(hazards)
    if extent is not None:mask=mask.intersection(box(*extent))
    rows=[];geometries=[];ids=set()
    for i,feature in enumerate(buildings['features']):
        g=shape(feature['geometry'])
        if not g.is_valid:raise ValueError('Invalid building geometry; no silent repair')
        if extent is not None:g=g.intersection(box(*extent))
        identifier=str(feature.get('id',feature.get('properties',{}).get('id',i)))
        if identifier in ids:raise ValueError('Duplicate analysis feature identity')
        ids.add(identifier);area=g.intersection(mask).area;geometries.append(g)
        rows.append({'feature_id':identifier,'footprint_area_m2':g.area,'intersected_area_m2':area,
                     'fraction_of_footprint':area/g.area if g.area else None,'touches_hazard':g.intersects(mask),'positive_area_intersection':area>0})
    combined=union_all(geometries)
    return {'status':'computed_horizontal_polygon_exposure','crs':CRS.from_user_input(crs).to_string(),'coordinate_status':coordinate_status,
        'hazard_sha256':hashlib.sha256(json.dumps(hazard,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'features':rows,'feature_count':len(rows),'positive_area_features':sum(r['positive_area_intersection'] for r in rows),
        'touching_only_features':sum(r['touches_hazard'] and not r['positive_area_intersection'] for r in rows),
        'union_footprint_area_m2':combined.area,'union_exposed_area_m2':combined.intersection(mask).area,'hazard_union_area_m2':mask.area,
        'limits':'Polygon intersection only; no water depth, damage, probability, surveyed IFC placement or individual-building count inferred'}

def compare_exposure(first,second):
    if first['crs']!=second['crs'] or first['coordinate_status']!=second['coordinate_status'] or first['hazard_sha256']!=second['hazard_sha256']:raise ValueError('Mismatched coordinate evidence or hazard input')
    a={r['feature_id']:r for r in first['features']};b={r['feature_id']:r for r in second['features']}
    if set(a)!=set(b):raise ValueError('Conversion effect comparison needs the same matched source feature identities')
    return {'status':'matched_profile_difference','features':[{'feature_id':key,'change_in_exposed_area_m2':b[key]['intersected_area_m2']-a[key]['intersected_area_m2'],
        'classification_changed':a[key]['positive_area_intersection']!=b[key]['positive_area_intersection']} for key in sorted(a)],
        'scope':'Requires callers to retain the same hazard and terrain inputs; compare run provenance hashes before attributing effects'}

def height_exposure(entrance_elevations,water_elevations,vertical_crs,reference_provenance):
    if not vertical_crs or not reference_provenance:raise ValueError('Compatible vertical datum and reference provenance required')
    crs=CRS.from_user_input(vertical_crs)
    if not crs.axis_info or crs.axis_info[-1].direction!='up' or abs(crs.axis_info[-1].unit_conversion_factor-1)>1e-12:raise ValueError('Expected a declared upward metre vertical axis')
    if entrance_elevations is None or water_elevations is None:raise ValueError('Actual entrance and water-level observations are required; terrain context cannot invent them')
    if set(entrance_elevations)!=set(water_elevations):raise ValueError('Mismatched entrance identities')
    rows=[]
    for key in entrance_elevations:
        a=float(entrance_elevations[key]);b=float(water_elevations[key])
        if not math.isfinite(a) or not math.isfinite(b):raise ValueError('Nonfinite elevation')
        rows.append({'id':key,'water_above_threshold_m':b-a,'threshold_exceeded':b>a})
    return {'status':'threshold_comparison','vertical_crs':vertical_crs,'reference_provenance':reference_provenance,'features':rows,
        'limits':'Difference of supplied levels; no hydraulic prediction or damage estimate'}

def torino_context(root):
    root=Path(root);folder=root/'data/raw/torino_context';manifest=json.loads((folder/'source_manifest.json').read_text())
    for item in manifest['files']:
        if digest(root/item['path'])!=item['sha256']:raise ValueError('Retained source hash changed')
    buildings=json.loads((folder/'buildings.geojson').read_text());hazard=json.loads((folder/'event_2016_extent.geojson').read_text())
    result=exposure(buildings,hazard,'EPSG:32632','official_context',extent=manifest['bbox'])
    result.update(dataset='BDTRE cs_edi outline aggregates and November 2016 event polygons',source_manifest_sha256=digest(folder/'source_manifest.json'),
        source_attribution=manifest['attribution'],genuine_ifc_validation=False,conversion_effect_established=False)
    return result
