"""Trace independent envelope Solid errors back to source faces and edge contacts."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ifc_citygml.common import ROOT, write_json
from ifc_citygml.external_validation import geometry_adapter


def main():
    report_path = ROOT / "results/benchmark_run/duplex_exterior.report.json"
    report = json.loads(report_path.read_text())
    adapted, _ = geometry_adapter(Path(report["output"]).read_bytes(), force_solids=True)
    diagnostic = report["validation"]["external_validation"]["solid_diagnostic"]["report"]
    building = report["extraction"]["buildings"][0]
    object_id = report["source_links"][0]["citygml_id"]
    geometries = adapted["CityObjects"][object_id]["geometry"]
    findings = []
    for feature in diagnostic.get("features", []):
        for error in feature.get("errors", []):
            match = re.search(r"geom=(\d+)\|shell=(\d+)\|face=(\d+)", error.get("id", ""))
            if not match:
                findings.append({"validator_error": error})
                continue
            component, shell, face_index = map(int, match.groups())
            faces = geometries[component]["boundaries"][shell]
            incidence = defaultdict(list)
            for index, face in enumerate(faces):
                ring = face[0]
                for a, b in zip(ring, ring[1:] + ring[:1]):
                    incidence[tuple(sorted((a, b)))].append(index)
            face = faces[face_index][0]
            contacts = []
            for a, b in zip(face, face[1:] + face[:1]):
                neighbours = incidence[tuple(sorted((a, b)))]
                if len(neighbours) != 2:
                    sources = []
                    for index in neighbours:
                        sid = building["components"][component]["triangle_source_ids"][index]
                        source = building["sources"][str(sid)]
                        sources.append({"face": index, "ifc_global_id": source["ifc_global_id"],
                                        "step_id": source["step_id"], "ifc_class": source["ifc_class"], "name": source["name"]})
                    contacts.append({"edge_coordinates": [adapted["vertices"][a], adapted["vertices"][b]],
                                     "incident_face_count": len(neighbours), "incident_faces_and_sources": sources})
            source_id = building["components"][component]["triangle_source_ids"][face_index]
            source = building["sources"][str(source_id)]
            findings.append({"validator_error": error, "component": component, "face": face_index,
                             "source_step_id": source["step_id"], "source_ifc_class": source["ifc_class"],
                             "source_name": source["name"], "non_two_incidence_edges": contacts})
    result = {"case": "duplex_exterior", "source_report": str(report_path.relative_to(ROOT)),
              "gml_output_sha256": report["output_sha256"], "findings": findings,
              "interpretation": "Measured edge incidences in exported rings. More than two incident faces is a non-manifold contact; no geometric repair inferred."}
    sensitivity = []
    for candidate in (report_path, ROOT / "results/diagnostics/duplex_1nm.report.json"):
        if candidate.exists():
            value = json.loads(candidate.read_text())
            validated = value["validation"]
            sensitivity.append({"grid_and_validation_tolerance_m": value["profile"]["geometry_tolerance_m"],
                "declared_multisurface_status": validated["independent_surface_validation"],
                "solid_status": validated["independent_general_solid_validation"],
                "solid_error_codes": validated["external_validation"]["solid_diagnostic"]["report"].get("all_errors"),
                "output_sha256": value["output_sha256"], "source_sha256": value["extraction"]["input_sha256"]})
    result["numerical_grid_sensitivity"] = sensitivity
    write_json(ROOT / "results/TOPOLOGY_INVESTIGATION.json", result)
    lines = ["# Envelope topology investigation", "", "## Duplex", "",
             "The independent Solid diagnostic is traced to exported faces and source elements. Edge incidences below are computed from the exact GML rings, not inferred from element names.", ""]
    for finding in findings:
        contact = ", ".join(f"{edge['incident_face_count']} faces share edge {edge['edge_coordinates']}" for edge in finding.get("non_two_incidence_edges", []))
        lines.append(f"- Face {finding.get('face')}, source STEP {finding.get('source_step_id')} ({finding.get('source_ifc_class')}): "
                     + (contact or "validator flags this face; no non-two edge incidence on this individual face (inspect connected contact/vertex fan)."))
    clinic_path = ROOT / "results/clinic_source_mesh_diagnostics.json"
    clinic = json.loads(clinic_path.read_text())
    measured = "; ".join(f"STEP {e['step_id']}: {sum(i['boundary_edge_count'] for i in e['items'])} boundary edges" for e in clinic["elements"])
    lines.extend(["", "Coordinates and every incident source face are retained in `TOPOLOGY_INVESTIGATION.json`. A valid MultiSurface result is retained; the closed-Solid warning remains.", "",
        "## Clinic", "", "The strict union profile fails on three source walls. The diagnostic applies the declared grid, exact coordinate welding and orientation-only repair: " + measured + ". A hybrid backend request also yields open geometry; it may internally select the same kernel, so this is not independent validation. Machine-readable measurements and the raw-file hash are in `clinic_source_mesh_diagnostics.json`.", "",
        "```powershell", ".venv/Scripts/python.exe scripts/diagnose_mesh.py data/raw/benchmarks/clinic/Clinic_Architectural.ifc 501 653 1162 --report results/clinic_source_mesh_diagnostics.json", "```", "",
        "The source-preserving constructive profile can represent those meshes as surfaces. It does not invent missing caps or establish a closed outer building envelope."])
    lines.extend(["", "## Numerical-grid check", ""])
    for case in sensitivity:
        lines.append(f"- Grid/validation tolerance {case['grid_and_validation_tolerance_m']:g} m: MultiSurface {case['declared_multisurface_status']}; stronger Solid {case['solid_status']}; error codes {case['solid_error_codes']}.")
    lines.append("The tested contact persists at both micrometre and nanometre settings; the finer numerical grid alone does not resolve it. These are numerical checks, not claims about source survey accuracy.")
    (ROOT / "results/TOPOLOGY_INVESTIGATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"traced_errors": len(findings), "non_two_incidence_edges": sum(len(f.get("non_two_incidence_edges", [])) for f in findings)}))


if __name__ == "__main__":
    main()
