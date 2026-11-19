"""Source-attributed solid union with explicit enclosed-cavity removal.

These are the external shells of selected material unions. Open interior spaces
can remain connected to the outside: an exterior-only building interpretation is
not guaranteed and is separately flagged.
"""
from collections import Counter
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.unit
import manifold3d as m
import numpy as np
import trimesh

from .common import digest


def _host_guid(element):
    for fill in getattr(element, "FillsVoids", ()):
        for void in getattr(fill.RelatingOpeningElement, "VoidsElements", ()):
            return void.RelatingBuildingElement.GlobalId
    return None


def oriented_source_solid(vertices, triangles, item_ids, original_id, tolerance):
    def construct(points, faces):
        return m.Manifold(m.Mesh64(np.ascontiguousarray(points, dtype=np.float64), np.ascontiguousarray(faces, dtype=np.uint64),
            run_index=np.array([0, faces.size], dtype=np.uint64),
            run_original_id=np.array([original_id], dtype=np.uint32), tolerance=tolerance))
    initial = construct(vertices, triangles)
    repairs = []
    if initial.status() == m.Error.NoError and not initial.is_empty() and initial.volume() > 0:
        return initial, repairs
    # Separate representation items before union: overlapping window/frame solids
    # are not a single manifold mesh even though each item can be valid.
    if len(item_ids) != len(triangles):
        raise ValueError("Missing item attribution for source repair")
    parts = []
    for item in sorted(set(item_ids.tolist())):
        selected = triangles[item_ids == item]
        # Exact coordinate welding only: no smoothing or hole filling.
        unique, inverse = np.unique(vertices, axis=0, return_inverse=True)
        faces = inverse[selected]
        mesh = trimesh.Trimesh(unique, faces.copy(), process=False)
        trimesh.repair.fix_normals(mesh, multibody=True)
        corrected = int(np.count_nonzero(np.any(mesh.faces != faces, axis=1)))
        # An orientation repair may change ring order, never triangle positions.
        if not np.array_equal(np.sort(mesh.faces, axis=1), np.sort(faces, axis=1)):
            raise ValueError("Orientation repair changed source triangle membership")
        part = construct(np.asarray(mesh.vertices), np.asarray(mesh.faces))
        if part.status() != m.Error.NoError or part.is_empty() or part.volume() <= 0:
            raise ValueError(f"Unsupported source topology after orientation-only repair: {part.status()}")
        parts.append(part)
        repairs.append({"representation_item_step_id": int(item), "orientation_corrected_triangles": corrected,
                        "exact_coordinate_welding": True, "triangle_coordinates_changed": False})
    return m.Manifold.batch_boolean(parts, m.OpType.Add), repairs


def classify_surface(source, normal, centre, minimum_z, tolerance):
    kind = source["ifc_class"]
    if kind == "IfcDoor":
        return "DoorSurface"
    if kind == "IfcWindow":
        return "WindowSurface"
    if normal[2] < -0.5 and abs(centre[2] - minimum_z) <= tolerance * 4:
        return "GroundSurface"
    if normal[2] > 0.05 and (kind == "IfcRoof" or source.get("predefined_type") == "ROOF"):
        return "RoofSurface"
    if abs(normal[2]) <= 0.5:
        return "WallSurface"
    return "OuterFloorSurface" if normal[2] > 0 else "OuterCeilingSurface"


def extract_envelopes(path: Path, profile: dict) -> dict:
    model = ifcopenshell.open(str(path))
    if model.schema not in profile["supported_ifc_schemas"]:
        raise ValueError(f"Unsupported IFC schema: {model.schema}")
    if profile["coordinate_mode"] not in ("ifc_map_conversion", "engineering_with_map_provenance") and model.schema != "IFC2X3" and model.by_type("IfcMapConversion"):
        raise ValueError("IfcMapConversion requires a verified geographic transformation; not implemented yet")
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    tolerance = profile["geometry_tolerance_m"]
    buildings, failures = [], []
    for building in sorted(model.by_type("IfcBuilding"), key=lambda b: b.GlobalId):
        solids, sources, omitted = [], {}, []
        for element in sorted(ifcopenshell.util.element.get_decomposition(building), key=lambda e: e.id()):
            if not element.is_a("IfcElement") or element.is_a("IfcFeatureElement"):
                continue
            record = {"ifc_global_id": element.GlobalId, "ifc_class": element.is_a(), "name": element.Name,
                      "step_id": element.id(), "host_global_id": _host_guid(element),
                      "predefined_type": getattr(element, "PredefinedType", None)}
            if not any(element.is_a(c) for c in profile["shell_ifc_classes"]):
                omitted.append({**record, "reason": "Excluded by shell element-class profile"})
                continue
            if not element.Representation:
                omitted.append({**record, "reason": "No source representation"})
                continue
            try:
                shape = ifcopenshell.geom.create_shape(settings, element)
                vertices = np.asarray(shape.geometry.verts, dtype=np.float64).reshape(-1, 3)
                triangles = np.asarray(shape.geometry.faces, dtype=np.uint64).reshape(-1, 3)
                if not len(triangles) or not np.isfinite(vertices).all():
                    raise ValueError("No finite triangulated geometry")
                snapped = np.round(vertices / tolerance) * tolerance
                maximum_move = float(np.linalg.norm(snapped - vertices, axis=1).max())
                original_id = m.Manifold.reserve_ids(1)
                solid, repairs = oriented_source_solid(snapped, triangles, np.asarray(shape.geometry.item_ids), original_id, tolerance)
                if solid.status() != m.Error.NoError or solid.is_empty() or solid.volume() <= 0:
                    raise ValueError(f"Invalid oriented source solid: {solid.status()}, volume={solid.volume()}")
                sources[original_id] = {**record, "maximum_grid_snap_displacement_m": maximum_move,
                                       "input_triangle_count": len(triangles), "input_material_volume_m3": solid.volume(),
                                       "source_repairs": repairs}
                solids.append(solid)
            except Exception as exc:
                failures.append({**record, "building": building.GlobalId, "reason": str(exc)})
        if not solids:
            failures.append({"building": building.GlobalId, "reason": "No supported oriented shell source solids"})
            continue
        union = m.Manifold.batch_boolean(solids, m.OpType.Add)
        if union.status() != m.Error.NoError:
            failures.append({"building": building.GlobalId, "reason": f"Boolean union failed: {union.status()}"})
            continue
        components, removed_cavities, removed_nested, outer = [], [], [], []
        positive = []
        for component in union.decompose():
            volume = component.volume()
            if volume < 0:
                removed_cavities.append({"signed_volume_m3": volume, "triangle_count": component.num_tri()})
                continue
            positive.append(component)
        # Filling a cavity for an outer envelope also hides positive material
        # islands inside it (for example internal doors). Retaining those islands
        # would incorrectly present interior objects as exterior boundary features.
        for component in sorted(positive, key=lambda c: c.volume(), reverse=True):
            bounds = np.array(component.bounding_box()).reshape(2, 3)
            nested = False
            for parent in outer:
                parent_bounds = np.array(parent.bounding_box()).reshape(2, 3)
                if np.all(bounds[0] >= parent_bounds[0] - tolerance) and np.all(bounds[1] <= parent_bounds[1] + tolerance):
                    intersection = component ^ parent
                    if intersection.status() == m.Error.NoError and abs(intersection.volume() - component.volume()) <= max(tolerance ** 3, component.volume() * 1e-8):
                        removed_nested.append({"volume_m3": component.volume(), "triangle_count": component.num_tri(),
                                               "reason": "Fully contained in a retained outer envelope shell"})
                        nested = True
                        break
            if not nested:
                outer.append(component)
        for component in outer:
            volume = component.volume()
            mesh = component.to_mesh64()
            vertices = np.asarray(mesh.vert_properties)[:, :3]
            faces = np.asarray(mesh.tri_verts)
            face_sources = np.full(len(faces), -1, dtype=np.int64)
            for start, end, original_id in zip(mesh.run_index[:-1], mesh.run_index[1:], mesh.run_original_id):
                face_sources[int(start) // 3:int(end) // 3] = original_id
            if any(int(i) not in sources for i in face_sources):
                raise ValueError("Boolean output lost source attribution")
            components.append({"vertices": vertices.tolist(), "triangles": faces.tolist(),
                               "triangle_source_ids": face_sources.tolist(), "volume_m3": volume})
        if not components:
            failures.append({"building": building.GlobalId, "reason": "No positive outer boundary component"})
            continue
        all_points = np.vstack([c["vertices"] for c in components])
        minimum_z = float(all_points[:, 2].min())
        semantic_counts, semantic_areas = Counter(), Counter()
        for component in components:
            points = np.array(component["vertices"])
            semantics = []
            for face, original_id in zip(component["triangles"], component["triangle_source_ids"]):
                triangle = points[face]
                normal = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
                length = np.linalg.norm(normal)
                if length == 0 or not np.isfinite(length):
                    semantics.append("invalid_degenerate_union_triangle")
                    failures.append({"building": building.GlobalId, "reason": "Union output contains a zero-area/non-finite triangle; no detailed output published"})
                    continue
                semantic = classify_surface(sources[original_id], normal / length, triangle.mean(axis=0), minimum_z, tolerance)
                semantics.append(semantic)
                semantic_counts[semantic] += 1
                semantic_areas[semantic] += length / 2
            component["triangle_semantics"] = semantics
        buildings.append({"source_building_global_id": building.GlobalId, "name": building.Name,
            "bounds_m": [all_points.min(axis=0).tolist(), all_points.max(axis=0).tolist()],
            "components": components, "sources": sources, "omitted": omitted,
            "material_union_volume_m3": union.volume(), "outer_shell_volume_m3": sum(c["volume_m3"] for c in components),
            "removed_enclosed_cavities": removed_cavities,
            "removed_nested_positive_components": removed_nested,
            "enclosure_status": "enclosed_cavities_removed" if removed_cavities else "open_or_unverified_enclosure",
            "semantic_triangle_counts": dict(semantic_counts), "semantic_surface_areas_m2": dict(semantic_areas),
            "semantic_policy": "Source class and normal/height heuristics; not independently annotated semantic ground truth"})
    return {"status": "failed" if failures or not buildings else "passed", "input": str(path.resolve()),
            "input_sha256": digest(path), "ifc_schema": model.schema,
            "length_unit_to_metre": ifcopenshell.util.unit.calculate_unit_scale(model),
            "representation": "union_outer_shells", "buildings": buildings, "failures": failures,
            "geometry_policy": "Selected material solid union; remove negative enclosed cavity shells; retain all positive components",
            "coordinate_frame": "IFC world engineering metres, no map conversion"}
