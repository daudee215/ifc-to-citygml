"""Inspect difficult source meshes without changing raw IFC."""
from collections import Counter
import argparse
import sys
from pathlib import Path
import ifcopenshell
import ifcopenshell.geom
import manifold3d as m
import numpy as np
import trimesh
from ifc_citygml.common import ROOT, digest, write_json

parser = argparse.ArgumentParser()
parser.add_argument("input", type=Path)
parser.add_argument("steps", type=int, nargs="+")
parser.add_argument("--report", type=Path, default=ROOT / "results/source_mesh_diagnostics.json")
parser.add_argument("--tolerance", type=float, default=1e-6)
args = parser.parse_args()
model = ifcopenshell.open(str(args.input))
records = []
settings = ifcopenshell.geom.settings()
settings.set("use-world-coords", True)
for step in args.steps:
    shape = ifcopenshell.geom.create_shape(settings, model.by_id(step))
    raw = np.asarray(shape.geometry.verts).reshape(-1, 3)
    vertices = np.round(raw / args.tolerance) * args.tolerance
    faces = np.asarray(shape.geometry.faces).reshape(-1, 3)
    mesh = trimesh.Trimesh(vertices, faces, process=True)
    print(step, "verts/faces", len(vertices), len(faces), "watertight", mesh.is_watertight,
          "winding", mesh.is_winding_consistent, "volume", mesh.volume)
    ids = np.array(shape.geometry.item_ids)
    record = {"step_id": step, "ifc_global_id": model.by_id(step).GlobalId, "ifc_class": model.by_id(step).is_a(),
              "input_triangle_count": len(faces), "maximum_grid_displacement_m": float(np.linalg.norm(vertices - raw, axis=1).max()), "items": []}
    print("items", Counter(ids.tolist()))
    for item in sorted(set(ids)):
        selected = faces[ids == item]
        indices = np.unique(selected)
        remap = np.full(len(vertices), -1)
        remap[indices] = np.arange(len(indices))
        sub = m.Manifold(m.Mesh64(np.ascontiguousarray(vertices[indices]), np.ascontiguousarray(remap[selected], dtype=np.uint64)))
        print("item", item, "status", sub.status(), "volume", sub.volume())
        unique, inverse = np.unique(vertices, axis=0, return_inverse=True)
        repaired = trimesh.Trimesh(unique, inverse[selected], process=False)
        before = repaired.faces.copy()
        trimesh.repair.fix_normals(repaired, multibody=True)
        fixed = m.Manifold(m.Mesh64(np.ascontiguousarray(repaired.vertices), np.ascontiguousarray(repaired.faces, dtype=np.uint64)))
        print("oriented", repaired.is_watertight, repaired.is_winding_consistent, fixed.status(), fixed.volume())
        print("area_min", repaired.area_faces.min(), "zero_area", int((repaired.area_faces == 0).sum()),
              "edge_incidence_histogram", dict(Counter(np.bincount(repaired.edges_unique_inverse).tolist())))
        counts = Counter(np.bincount(repaired.edges_unique_inverse).tolist())
        record["items"].append({"representation_item_step_id": int(item), "boundary_edge_count": counts.get(1, 0),
            "edge_incidence_histogram": dict(counts), "watertight": bool(repaired.is_watertight),
            "orientation_corrected_triangles": int(np.count_nonzero(np.any(before != repaired.faces, axis=1))),
            "manifold_status": str(fixed.status()), "zero_area_triangle_count": int((repaired.area_faces == 0).sum())})
    try:
        alternate = ifcopenshell.geom.create_shape(settings, model.by_id(step), geometry_library="hybrid-cgal-simple-opencascade")
        points = np.asarray(alternate.geometry.verts).reshape(-1, 3)
        faces = np.asarray(alternate.geometry.faces).reshape(-1, 3)
        mesh = trimesh.Trimesh(points, faces, process=True)
        trimesh.repair.fix_normals(mesh, multibody=True)
        fixed = m.Manifold(m.Mesh64(np.ascontiguousarray(mesh.vertices), np.ascontiguousarray(mesh.faces, dtype=np.uint64)))
        print("alternate_backend", mesh.is_watertight, fixed.status(), fixed.volume())
        record["alternate_requested_backend"] = {"name": "hybrid-cgal-simple-opencascade", "watertight": bool(mesh.is_watertight),
            "manifold_status": str(fixed.status()), "note": "Hybrid backend may select the same kernel internally; not proof of independent-kernel validation"}
    except Exception as exc:
        print("alternate_backend_error", str(exc)[:200])
        record["alternate_requested_backend"] = {"error": str(exc)}
    records.append(record)
write_json(args.report, {"input": str(args.input.resolve()), "input_sha256": digest(args.input),
    "ifcopenshell_version": ifcopenshell.version, "diagnostic_grid_m": args.tolerance,
    "operations": ["declared grid snap for diagnostic parity", "exact coordinate welding", "orientation-only repair"],
    "raw_input_modified": False, "elements": records})
print("Diagnostic report:", args.report)
