"""Apply explicitly selected IFC4 map conversion with a complete metre 3D CRS.

This establishes coordinate transformation behaviour, not positional accuracy.
No external reprojection or vertical-datum transformation is inferred.
"""
import copy
import json

import ifcopenshell
import ifcopenshell.util.geolocation as geo
import ifcopenshell.util.unit
import numpy as np
from pyproj import CRS
from .common import digest

ENGINEERING_MODE = "engineering_with_map_provenance"
ENGINEERING_NOTICE = "Engineering coordinates only. Original IFC map metadata is retained in provenance and has not been applied. No geographic position or geographic height datum is established."


def prepare_profile(profile, input_path):
    result = copy.deepcopy(profile)
    if profile["coordinate_mode"] == ENGINEERING_MODE:
        model = ifcopenshell.open(str(input_path))
        if model.schema != "IFC4":
            raise ValueError("Explicit engineering-frame preservation currently supports IFC4 only")
        wcs = geo.get_wcs(model)
        if wcs is not None and not np.allclose(wcs, np.eye(4), atol=1e-12, rtol=0):
            raise ValueError("Non-identity context WorldCoordinateSystem needs additional placement validation; not supported yet")
        operations = model.by_type("IfcCoordinateOperation")
        result["georeferencing"] = {
            "policy": "retain_source_map_metadata_without_applying_it", "operation_applied": False,
            "source_input_sha256": digest(input_path), "geometry_frame": "IfcOpenShell world engineering coordinates in SI metres",
            "output_srs_name": profile["srs_name"], "source_length_unit_to_metre": ifcopenshell.util.unit.calculate_unit_scale(model),
            "original_coordinate_operations": [json.loads(json.dumps(op.get_info(recursive=True), allow_nan=False)) for op in operations],
            "original_projected_crs": [json.loads(json.dumps(crs.get_info(recursive=True), allow_nan=False)) for crs in model.by_type("IfcProjectedCRS")],
            "accuracy_status": "engineering_frame_only; geographic position not established",
            "vertical_policy": "Retain source engineering Z; no geographic vertical datum is asserted",
            "notice": ENGINEERING_NOTICE}
        return result
    if profile["coordinate_mode"] != "ifc_map_conversion":
        return result
    model = ifcopenshell.open(str(input_path))
    if model.schema != "IFC4":
        raise ValueError("Explicit map-conversion profile currently supports IFC4 only")
    operations = model.by_type("IfcCoordinateOperation")
    if len(operations) != 1 or operations[0].is_a() != "IfcMapConversion":
        raise ValueError("Requires exactly one ordinary IfcMapConversion")
    operation = operations[0]
    target = operation.TargetCRS
    if not target.is_a("IfcProjectedCRS") or not target.Name:
        raise ValueError("Map conversion must identify its target projected/compound CRS")
    crs = CRS.from_user_input(target.Name)
    if len(crs.axis_info) != 3 or not all(abs(a.unit_conversion_factor - 1) < 1e-12 for a in crs.axis_info):
        raise ValueError("Map profile requires a complete three-axis metre CRS; a 2D CRS does not establish the height datum")
    if crs.axis_info[0].direction != "east" or crs.axis_info[1].direction != "north":
        raise ValueError("Only easting,northing,height axis order is supported")
    authority = crs.to_authority()
    if not authority:
        raise ValueError("A resolvable authority CRS is required")
    map_unit = target.MapUnit
    if map_unit is not None and (not map_unit.is_a("IfcSIUnit") or map_unit.Name != "METRE" or map_unit.Prefix is not None):
        raise ValueError("Explicit target MapUnit must match the metre axes of the declared CRS")
    unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)
    if not np.isfinite(unit_scale) or unit_scale <= 0:
        raise ValueError("Invalid project length-unit scale")
    wcs = geo.get_wcs(model)
    if wcs is not None and not np.allclose(wcs, np.eye(4), atol=1e-12, rtol=0):
        raise ValueError("Non-identity context WorldCoordinateSystem needs additional placement validation; not supported yet")
    if operation.Scale is not None and operation.Scale <= 0:
        raise ValueError("Map conversion scale must be positive")
    if operation.XAxisAbscissa == 0 and operation.XAxisOrdinate == 0:
        raise ValueError("Map conversion X axis cannot have zero length")
    base = np.array(geo.auto_xyz2enh(model, 0, 0, 0), dtype=float)
    matrix = np.eye(4)
    matrix[:3, 3] = base
    for axis in range(3):
        p = np.zeros(3)
        p[axis] = 1 / unit_scale  # API inputs use source project units, geometry uses SI metres.
        matrix[:3, axis] = np.array(geo.auto_xyz2enh(model, *p)) - base
    if not np.isfinite(matrix).all() or np.linalg.det(matrix[:3, :3]) <= 0:
        raise ValueError("Invalid or reflected map transformation")
    result["srs_name"] = f"urn:ogc:def:crs:{authority[0]}::{authority[1]}"
    result["resolved_affine_matrix"] = matrix.tolist()
    result["georeferencing"] = {"source": "IFC4 IfcMapConversion and IfcProjectedCRS",
        "coordinate_operation_step_id": operation.id(), "target_crs_name": target.Name,
        "target_crs_wkt": crs.to_wkt(), "project_length_unit_to_metre": unit_scale,
        "source_parameters": operation.get_info(recursive=False),
        "accuracy_status": "metadata_transform_only; no independent checkpoints",
        "vertical_policy": "Uses declared 3D CRS; no vertical datum conversion performed"}
    result["georeferencing"]["source_parameters"].pop("SourceCRS", None)
    result["georeferencing"]["source_parameters"].pop("TargetCRS", None)
    return result
