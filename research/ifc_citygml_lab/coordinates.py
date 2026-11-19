"""Explicit engineering/map stages and independent-check residuals.

Metadata transforms establish coordinate behaviour, not surveyed accuracy.
"""
import math
from pathlib import Path
import ifcopenshell
import ifcopenshell.util.unit
import ifcopenshell.util.placement
import ifcopenshell.util.geolocation as geo
import numpy as np
from pyproj import CRS,Transformer
from ifc_citygml.common import digest

def apply_matrix(points,matrix):
    p=np.asarray(points,dtype=float);m=np.asarray(matrix,dtype=float)
    if p.ndim!=2 or p.shape[1]!=3 or m.shape!=(4,4) or not np.isfinite(p).all() or not np.isfinite(m).all():raise ValueError('Expected finite 3D points and a 4 by 4 matrix')
    if not np.allclose(m[3],[0,0,0,1],atol=1e-12,rtol=0):raise ValueError('Nonaffine matrix')
    if np.linalg.det(m[:3,:3])<=0:raise ValueError('Reflected or singular transform')
    return p@m[:3,:3].T+m[:3,3]

def audit_chain(path):
    path=Path(path);model=ifcopenshell.open(str(path));unit=ifcopenshell.util.unit.calculate_unit_scale(model)
    if not math.isfinite(unit) or unit<=0:raise ValueError('Invalid length unit')
    wcs=geo.get_wcs(model);wcs=np.eye(4) if wcs is None else np.asarray(wcs,float)
    placements=[]
    for building in model.by_type('IfcBuilding'):
        matrix=np.asarray(ifcopenshell.util.placement.get_local_placement(building.ObjectPlacement),float);matrix[:3,3]*=unit
        placements.append({'building':building.GlobalId,'matrix_project_placement_in_si':matrix.tolist(),'already_applied_by_world_geometry_sdk':True})
    result={'input_sha256':digest(path),'schema':model.schema,'source_unit_to_metre':unit,'context_wcs_project_units':wcs.tolist(),
        'building_placements':placements,'stages':[{'name':'source_units','to_metre':unit},{'name':'context_and_product_placements','applied_by':'IfcOpenShell world extraction; do not apply twice'}],
        'status':'engineering_only','horizontal_accuracy':'not independently established','vertical_status':'engineering_height_only','map_operation_applied':False}
    if not np.allclose(wcs,np.eye(4),atol=1e-12,rtol=0):
        result.update(status='unsupported_context',reason='Nonidentity context needs an independently tested interpretation; map application refused');return result
    operations=[] if model.schema=='IFC2X3' else model.by_type('IfcMapConversion')
    if not operations:return result
    if len(operations)!=1:result.update(status='ambiguous_map_operations',reason='Exactly one ordinary map operation required');return result
    operation=operations[0];target=operation.TargetCRS
    if not target.Name:result.update(status='missing_target_crs');return result
    crs=CRS.from_user_input(target.Name)
    if target.MapUnit is not None:
        map_unit=target.MapUnit
        if not map_unit.is_a('IfcSIUnit') or map_unit.Name!='METRE' or map_unit.Prefix is not None:
            raise ValueError('Only an explicit unprefixed metre map unit is supported')
    axes=crs.axis_info
    if len(axes)<2 or axes[0].direction!='east' or axes[1].direction!='north':raise ValueError('Expected easting/northing CRS')
    if not all(abs(a.unit_conversion_factor-1)<1e-12 for a in axes):raise ValueError('Target axes must be metres')
    if operation.Scale is not None and (not math.isfinite(operation.Scale) or operation.Scale<=0):raise ValueError('Invalid map scale')
    x=operation.XAxisAbscissa;y=operation.XAxisOrdinate
    if x is not None and y is not None and math.hypot(x,y)==0:raise ValueError('Zero map axis')
    base=np.asarray(geo.auto_xyz2enh(model,0,0,0),float);matrix=np.eye(4);matrix[:3,3]=base
    for k in range(3):
        point=np.zeros(3);point[k]=1/unit;matrix[:3,k]=np.asarray(geo.auto_xyz2enh(model,*point))-base
    apply_matrix(np.zeros((1,3)),matrix)
    result.update(status='metadata_transform_resolved',target_crs=crs.to_string(),target_crs_wkt=crs.to_wkt(),matrix_engineering_metres_to_map=matrix.tolist(),
        vertical_status='declared_complete_crs_not_independently_verified' if len(axes)==3 else 'unknown_geographic_vertical_datum',
        vertical_transform_performed=False,source_map_parameters={k:v for k,v in operation.get_info().items() if k not in ['SourceCRS','TargetCRS']})
    result['stages'].append({'name':'map_operation','matrix':matrix.tolist(),'applied':False,'target_crs':crs.to_string()})
    return result

def transform_engineering(points,chain,require_vertical=False):
    if chain['status']!='metadata_transform_resolved':raise ValueError('No resolved map operation')
    if require_vertical and not chain['vertical_status'].startswith('declared_complete_crs'):raise ValueError('Missing geographic vertical interpretation')
    return apply_matrix(points,chain['matrix_engineering_metres_to_map'])

def checkpoint_residuals(source_points,reference_points,matrix,reference_role,reference_provenance):
    if reference_role not in {'synthetic_truth','independent_check','calibration_fit'}:raise ValueError('Declare reference role')
    if not reference_provenance:raise ValueError('Reference provenance is required')
    predicted=apply_matrix(source_points,matrix);reference=np.asarray(reference_points,float)
    if not len(predicted):raise ValueError('At least one checkpoint is required')
    if predicted.shape!=reference.shape or not np.isfinite(reference).all():raise ValueError('Checkpoint shape or finite value mismatch')
    residual=predicted-reference;horizontal=np.linalg.norm(residual[:,:2],axis=1)
    return {'reference_role':reference_role,'reference_provenance':reference_provenance,'count':len(reference),'residual_vectors_m':residual.tolist(),
        'horizontal_rmse_m':float(np.sqrt(np.mean(horizontal**2))),'vertical_rmse_m':float(np.sqrt(np.mean(residual[:,2]**2))),
        'maximum_horizontal_m':float(horizontal.max()),'maximum_absolute_vertical_m':float(np.abs(residual[:,2]).max()),
        'accuracy_claim':'Synthetic arithmetic check' if reference_role=='synthetic_truth' else 'Fit residuals, not independent accuracy' if reference_role=='calibration_fit' else 'Independent-check status asserted by supplied reference provenance'}

def reproject_horizontal(points,source_crs,target_crs):
    points=np.asarray(points,float)
    transformer=Transformer.from_crs(source_crs,target_crs,always_xy=True)
    x,y=transformer.transform(points[:,0],points[:,1],errcheck=True)
    result=points.copy();result[:,:2]=np.column_stack([x,y]);return result
