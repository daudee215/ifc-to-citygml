from copy import deepcopy
import math
from shapely.geometry import shape,mapping
from shapely import affinity
from ifc_citygml_lab.urban import exposure,compare_exposure
def profile_sensitivity(profiles,hazard,crs,coordinate_status,offsets,scenario_provenance):
    if not scenario_provenance:raise ValueError('Declare scenario provenance; no invented uncertainty distribution')
    if not offsets or any(len(o)!=2 or not all(math.isfinite(float(x)) for x in o) for o in offsets):raise ValueError('Finite horizontal scenario offsets required')
    base={name:exposure(features,hazard,crs,coordinate_status) for name,features in profiles.items()};rows=[]
    for name,features in profiles.items():
        for dx,dy in offsets:
            shifted=deepcopy(features)
            for f in shifted['features']:f['geometry']=mapping(affinity.translate(shape(f['geometry']),float(dx),float(dy)))
            result=exposure(shifted,hazard,crs,coordinate_status);rows.append({'profile':name,'dx_m':dx,'dy_m':dy,'union_exposed_area_m2':result['union_exposed_area_m2'],'positive_area_features':result['positive_area_features'],'hazard_sha256':result['hazard_sha256']})
    names=list(base);comparisons={name:compare_exposure(base[names[0]],base[name]) for name in names[1:]}
    return {'status':'computed_fixed_hazard_scenario_sensitivity','scenario_provenance':scenario_provenance,'baseline_profiles':base,'profile_differences':comparisons,'scenarios':rows,
        'ranges':{name:{'minimum_exposed_area_m2':min(r['union_exposed_area_m2'] for r in rows if r['profile']==name),'maximum_exposed_area_m2':max(r['union_exposed_area_m2'] for r in rows if r['profile']==name)} for name in names},
        'interpretation':'Deterministic declared scenarios, not confidence intervals, flood predictions or surveyed placement accuracy'}
