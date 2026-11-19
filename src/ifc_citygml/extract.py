from __future__ import annotations

from collections import Counter
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.unit
import numpy as np

from .common import digest
from .representations import POLICY, select_block_representations


def inspect_ifc(path: Path) -> dict:
    model = ifcopenshell.open(str(path))
    return {
        "input": str(path.resolve()), "input_sha256": digest(path), "ifc_schema": model.schema,
        "length_unit_to_metre": ifcopenshell.util.unit.calculate_unit_scale(model),
        "entity_counts": dict(sorted(Counter(e.is_a() for e in model).items())),
        "buildings": [{"global_id": b.GlobalId, "name": b.Name} for b in model.by_type("IfcBuilding")],
        "map_conversion_count": len(model.by_type("IfcMapConversion")) if model.schema != "IFC2X3" else 0,
        "georeferencing_policy": "Local or synthetic by default; explicit IFC4 map profile requires a complete three-axis metre CRS and validated metadata handling",
    }


def extract_blocks(path: Path, profile: dict) -> dict:
    model = ifcopenshell.open(str(path))
    if model.schema not in profile["supported_ifc_schemas"]:
        raise ValueError(f"Unsupported IFC schema: {model.schema}")
    if profile["coordinate_mode"] not in ("ifc_map_conversion", "engineering_with_map_provenance") and model.schema != "IFC2X3" and model.by_type("IfcMapConversion"):
        raise ValueError("IfcMapConversion is present: automatic map conversion is not implemented; refusing ambiguous output")
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("convert-back-units", False)
    buildings, failures, all_guids = [], [], set()
    for building in sorted(model.by_type("IfcBuilding"), key=lambda b: b.GlobalId or ""):
        if not building.GlobalId or building.GlobalId in all_guids:
            failures.append({"building": building.GlobalId, "reason": "Missing or duplicate building GlobalId"})
            continue
        all_guids.add(building.GlobalId)
        descendants = ifcopenshell.util.element.get_decomposition(building)
        elements = sorted((e for e in descendants if e.is_a("IfcElement")
                           and not e.is_a("IfcFeatureElement")
                           and not e.is_a("IfcVirtualElement")), key=lambda e: e.id())
        # A few IFCs put a representation directly on the spatial building.
        if building.Representation:
            elements.insert(0, building)
        contributors, omitted, vertices = [], [], []
        for element in elements:
            record = {"ifc_global_id": element.GlobalId, "ifc_class": element.is_a(),
                      "name": element.Name, "step_id": element.id()}
            if not element.Representation:
                omitted.append({**record, "reason": "No source representation; not an exported semantic feature"})
                continue
            try:
                representations, selection = select_block_representations(element)
                if not representations:
                    omitted.append({**record, "reason": "Annotation-only source representation; excluded from physical bounding block",
                                    "representation_selection": selection})
                    continue
                parts = []
                for representation in representations:
                    shape = ifcopenshell.geom.create_shape(settings, element, repr=representation)
                    points = np.asarray(shape.geometry.verts, dtype=float).reshape(-1, 3)
                    if not len(points) or not np.isfinite(points).all():
                        raise ValueError("Selected physical representation has no finite vertices")
                    parts.append(points)
                points = np.vstack(parts)
                vertices.append(points)
                contributors.append({**record, "role": "aggregated_into_bounding_block",
                                     "vertex_count": len(points),
                                     "representation_selection": selection,
                                     "semantic_feature_preserved": False})
            except Exception as exc:
                failures.append({**record, "building": building.GlobalId, "reason": str(exc)})
        if not vertices:
            failures.append({"building": building.GlobalId, "reason": "No usable physical element geometry"})
            continue
        points = np.vstack(vertices)
        low, high = points.min(axis=0), points.max(axis=0)
        if np.any(high - low <= profile["geometry_tolerance_m"]):
            failures.append({"building": building.GlobalId, "reason": "Degenerate block extent"})
            continue
        buildings.append({
            "source_building_global_id": building.GlobalId, "name": building.Name,
            "bounds_m": [low.tolist(), high.tolist()],
            "source_vertex_count": len(points), "contributors": contributors, "omitted": omitted,
        })
    if not buildings:
        failures.append({"reason": "No convertible IfcBuilding found"})
    return {"status": "failed" if failures else "passed", "input_sha256": digest(path),
            "input": str(path.resolve()), "ifc_schema": model.schema,
            "length_unit_to_metre": ifcopenshell.util.unit.calculate_unit_scale(model),
            "coordinate_frame": "IFC world engineering coordinates in metres, prior to map conversion",
            "geometry_policy": "AABB of explicitly selected Body/Body-FallBack vertices; annotation-only products omitted with provenance; not an exterior envelope",
            "representation_selection_policy": POLICY,
            "buildings": buildings, "failures": failures}
