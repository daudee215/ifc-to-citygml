"""Resource eligibility is explicit; no triangle truncation or silent partial export."""
def geometry_eligibility(vertices,triangles,maximum_triangles=20000,maximum_convex_matrix_entries=1000000):
    if vertices<1 or triangles<1:return {'status':'unsupported','reason':'Empty source mesh'}
    if triangles>maximum_triangles or vertices*triangles>maximum_convex_matrix_entries:
        return {'status':'resource_budget_exceeded','vertices':vertices,'triangles':triangles,'convex_matrix_entries':vertices*triangles,
            'maximum_triangles':maximum_triangles,'maximum_convex_matrix_entries':maximum_convex_matrix_entries,
            'reason':'Unqualified source complexity; full vertex/face halfspace allocation refused, no truncation performed'}
    return {'status':'eligible'}
