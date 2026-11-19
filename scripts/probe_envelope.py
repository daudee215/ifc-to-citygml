"""Development probe for source-attributed solid union; not a benchmark result."""
import ifcopenshell
import ifcopenshell.geom
import manifold3d as m
import numpy as np

f = ifcopenshell.open("data/raw/fixtures/building_m.ifc")
settings = ifcopenshell.geom.settings()
settings.set("use-world-coords", True)
solids = []
for element in f.by_type("IfcElement"):
    if element.is_a("IfcFeatureElement"):
        continue
    shape = ifcopenshell.geom.create_shape(settings, element)
    vertices = np.array(shape.geometry.verts, dtype=np.float64).reshape(-1, 3)
    vertices = np.round(vertices / 1e-6) * 1e-6
    faces = np.array(shape.geometry.faces, dtype=np.uint64).reshape(-1, 3)
    origin = m.Manifold.reserve_ids(1)
    mesh = m.Mesh64(vertices, faces, run_index=np.array([0, faces.size], dtype=np.uint64),
                    run_original_id=np.array([origin], dtype=np.uint32), tolerance=1e-6)
    solid = m.Manifold(mesh)
    print(element.is_a(), solid.status(), solid.volume(), origin)
    solids.append(solid)
union = m.Manifold.batch_boolean(solids, m.OpType.Add)
print("union", union.status(), union.volume())
for c in union.decompose():
    mesh = c.to_mesh64()
    print("component", c.volume(), c.num_tri(), list(mesh.run_original_id), list(mesh.run_index))
