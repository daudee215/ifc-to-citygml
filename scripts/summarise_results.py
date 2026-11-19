"""Summarise measured conversion outcomes, including strict failures."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ifc_citygml.common import ROOT, code_digest, digest, write_json
from ifc_citygml.benchmark import report_path
from scripts.evaluation_evidence import verified_evaluation, verified_block_evaluation
from scripts.research_runs import research_index


def main():
    index_path, index = research_index()
    records, lines = [], []
    lines.extend(["# Research implementation progress", "", "Measured local execution results; generated from benchmark reports.", "",
                  "The main research focus is IFC-to-CityGML conversion. Local urban data are a separate context layer.", "",
                  "## Conversion results", "",
                  "| Case | Mode | Conversion | XSD | Independent target geometry | Stronger Solid check | Time (s) |",
                  "|---|---|---|---|---|---|---:|"])
    current_code = code_digest()
    for case in index["cases"]:
        path = report_path(index_path, index, case, ROOT)
        report = json.loads(path.read_text())
        validation = report.get("validation", {})
        if report.get("converter_source_sha256") != current_code:
            raise ValueError(f"Stale converter code hash in {path}; rerun the benchmark")
        extraction = report.get("extraction", report)
        if extraction["input_sha256"] != digest(Path(extraction["input"])):
            raise ValueError(f"Stale input hash in {path}")
        record = {"case": case["case"], "mode": case["mode"], "conversion_status": case["status"],
                  "base_mode": case["mode"].removeprefix("engineering-"),
                  "schema_valid": validation.get("schema_valid"),
                  "independent_target_status": validation.get("independent_surface_validation", validation.get("independent_general_solid_validation", "not_run")),
                  "solid_diagnostic_status": validation.get("independent_general_solid_validation", "not_run"),
                  "runtime_seconds": report["elapsed_seconds"], "source_sha256": extraction["input_sha256"],
                  "output_sha256": report.get("output_sha256"), "code_sha256": report["converter_source_sha256"],
                  "report": str(path.relative_to(ROOT)), "failure_reasons": dict(Counter(f["reason"] for f in extraction.get("failures", []))),
                  "pre_extraction_error": report.get("error"), "research_run": case["research_run"]}
        if record["base_mode"] == "exterior" and "extraction" in report:
            buildings = report["extraction"]["buildings"]
            record.update({"selected_source_solids": sum(len(b["sources"]) for b in buildings),
                "orientation_repaired_source_count": sum(bool(s["source_repairs"]) for b in buildings for s in b["sources"].values()),
                "union_boundary_triangles_before_failed_export": sum(len(c["triangles"]) for b in buildings for c in b["components"]),
                "enclosed_cavities_removed": sum(len(b["removed_enclosed_cavities"]) for b in buildings),
                "interior_positive_components_removed": sum(len(b["removed_nested_positive_components"]) for b in buildings)})
            if case["status"] == "passed":
                links = [s for b in report["source_links"] for s in b["surface_links"]]
                record["exported_thematic_features"] = len(links)
                record["exported_features_by_class"] = dict(Counter(s["target_class"] for s in links))
                record["source_features_with_exterior_contribution"] = len({s["ifc_global_id"] for s in links})
                record["semantic_accuracy_status"] = "Rule-derived; no independent real-building semantic ground truth yet"
        if record["base_mode"] == "source" and "extraction" in report:
            buildings = report["extraction"]["buildings"]
            record["serialization_fidelity"] = report["extraction"].get("serialization_fidelity")
            record["selected_source_elements"] = sum(len(b["elements"]) for b in buildings)
            record["source_triangle_count"] = sum(len(e["triangles"]) for b in buildings for e in b["elements"])
            record["source_omissions_by_reason"] = dict(Counter(o["reason"] for b in buildings for o in b["omitted"]))
            if case["status"] == "passed":
                links = [e for b in report["source_links"] for e in b["element_links"]]
                record["exported_features_by_class"] = dict(Counter(e["target_class"] for e in links))
                record["hosted_filling_count"] = sum(e["association"] == "source_host_construction_filling" for e in links)
                record["unhosted_filling_count"] = sum(e["association"].startswith("standalone_filling") for e in links)
        records.append(record)
        schema = "pass" if record["schema_valid"] else "not published"
        lines.append(f"| {record['case']} | {record['mode']} | {record['conversion_status']} | {schema} | {record['independent_target_status']} | {record['solid_diagnostic_status']} | {record['runtime_seconds']:.3f} |")
    passed = sum(r["conversion_status"] == "passed" for r in records)
    lines.extend(["", f"**{passed}/{len(records)} conversion attempts completed.** Four synthetic fixture variants represent controlled tests of one generated building. Duplex and Clinic are separate open benchmark projects. The independently authored IFC4 extension adds CHEK Gaia renovation and the fictional RWTH DigitalHub design; its eight strict attempts all fail before geometry extraction because current profiles cannot accept their incomplete 3D georeferencing metadata. Modes are paired attempts, not additional independent buildings.", "",
        "## Findings", "",
        "- Controlled metre/millimetre and placement cases preserve known dimensions. The detailed fixture retains a 2.1 m² exposed door surface and 96 m² roof/ground surfaces. Its recessed doorway explains the envelope volume of 575.9475 m³ versus the 576 m³ block.",
        "- The detailed Duplex output passes the official schema and independent MultiSurface validation. Its stronger Solid diagnostic finds non-manifold contacts (303), so it is not presented as a validated closed solid for volume-dependent analysis.",
        "- Three Duplex source meshes require recorded orientation/item-separation repairs. Triangle coordinates are not changed by the orientation repair; initial grid snapping is measured separately.",
        "- Clinic block conversion succeeds. Strict detailed conversion fails on unsupported wall topology and degenerate union triangles. No detailed Clinic GML is published; these failures remain in the benchmark.",
        "- The source-preserving profile exports constructive elements and native Door/Window fillings without solid union or invented caps. It preserves source opening cuts and checks every exported float64 triangle coordinate exactly. This surface representation can succeed on the Clinic while its separate envelope representation fails.",
        "- Real-model semantic precision/recall is not established. Feature counts measure what is exported, not annotation accuracy.", "", "## Successful detailed outputs", ""])
    for r in records:
        if r["base_mode"] == "exterior" and r["conversion_status"] == "passed":
            lines.append(f"- **{r['case']}**: {r['exported_thematic_features']} thematic features, {r['union_boundary_triangles_before_failed_export']} triangles; class counts: `{json.dumps(r['exported_features_by_class'], sort_keys=True)}`.")
    lines.extend(["", "## Source-preserving outputs", ""])
    for r in records:
        if r["base_mode"] == "source" and r["conversion_status"] == "passed":
            lines.append(f"- **{r['case']}**: {r['selected_source_elements']} represented elements and {r['source_triangle_count']} triangles; exact exported-coordinate check: {r['serialization_fidelity']['exact_transformed_float64_rings']}. Hosted fillings: {r['hosted_filling_count']}; unhosted fillings explicitly standalone: {r['unhosted_filling_count']}. Target counts: `{json.dumps(r['exported_features_by_class'], sort_keys=True)}`. Omission reasons/counts: `{json.dumps(r['source_omissions_by_reason'], sort_keys=True)}`.")
    lines.extend(["", "## IFC4 extension: unsupported coordinate metadata", "",
                  "[IFC4 benchmark findings](IFC4_BENCHMARK_FINDINGS.md) retain source/license provenance and all eight strict-profile failures. Separate explicit engineering-frame profiles now preserve source coordinates and unapplied metadata on the unchanged raw inputs. Their six additional attempts retain geometry failures; successful source outputs have separate exact geometry/provenance audits. The original v0.4 benchmark and wheel remain frozen."])
    for r in records:
        if r["pre_extraction_error"]:
            lines.append(f"- **{r['case']} / {r['mode']}**: {r['pre_extraction_error']}. Report: `{r['report']}`.")
    lines.extend(["", "## Topology investigation", "", "[Measured topology investigation](TOPOLOGY_INVESTIGATION.md) traces the Duplex Solid errors to source faces, including an edge shared by four foundation-wall/slab faces. Clinic source-wall diagnostics retain boundary-edge measurements and the immutable input hash. These findings explain limitations; they are not suppressed to improve the pass rate."])
    evaluation = verified_evaluation()
    block_evaluation = verified_block_evaluation()
    lines.extend(["", "## Physical block representation audit", "",
                  "[Block evaluation](block_evaluation/EVALUATION.md) independently checks selected bodies, annotation-only omissions, original engineering provenance and the exported box geometry.", "",
                  "| Case | Audit | Contributors | Omitted products | Annotation-only omissions | Max XML corner error (m) |",
                  "|---|---|---:|---:|---:|---:|"])
    for result in block_evaluation["cases"]:
        for building in result["buildings"]:
            lines.append(f"| {result['case']} | {result['status']} | {building['physical_contributors']} | {building['omitted']} | {building['annotation_only_omissions']} | {building['xml_max_corner_error_m']:.3g} |")
    lines.extend(["", "## Independent implementation audit of source mapping", "",
                  "[Semantic/provenance evaluation](semantic_evaluation/EVALUATION.md) checks original IFC relationships, actual XML features and the source sidecar without importing the production mapper. Two separately authored controlled specimens also test explicit expected classes and associations.", "",
                  "| Case | Audit | Expected / exported elements | Triangles checked | Explicit omissions | Mismatches |",
                  "|---|---|---:|---:|---:|---:|"])
    for result in evaluation["cases"]:
        lines.append(f"| {result['case']} | {result['status']} | {result['expected_features']} / {result['exported_features']} | {result['triangles_checked']} | {len(result['omissions'])} | {len(result['issues'])} |")
    lines.extend(["", "This measures agreement with the declared source mapping and fresh SDK tessellation. It does not independently establish real-building structural significance or exterior classification. The original source profile and its closed-Solid limitations remain unchanged."])
    context = json.loads((ROOT / "data/raw/torino_context/source_manifest.json").read_text())
    lines.extend(["", "## Torino–Moncalieri context", "",
        f"Downloaded {context['buildings_count']} BDTRE building-outline aggregate features and {context['event_polygon_count']} ARPA 2016 event polygons for a 4 km² operational sample. WFS requests were subdivided to avoid the 1,000-feature cap; overlapping responses were deduplicated. Original response pages, queries, checksums and source terms are retained.", "",
        "These are genuine local GIS features. They are not BIM, do not establish building interiors or entrance elevations, and are not used to assign a Torino identity to a non-local benchmark model. No flood-depth prediction or entrance-exposure result is claimed.", "",
        "## Review and reproduction", "",
        "Open [the local interactive review](review/index.html) to inspect actual exported polygons and the separate local context. The page is self-contained and has been rendered in headless Chrome; the stored preview is `review/preview.png`.", "",
        "Run `scripts/run_benchmark.py`, `scripts/run_ifc4_benchmarks.py`, `scripts/run_engineering_benchmarks.py` (nonzero exits retain known failures), `scripts/run_semantic_evaluation.py`, `scripts/run_block_evaluation.py`, `scripts/summarise_ifc4.py`, then `scripts/summarise_results.py` and `scripts/build_review.py`. Version 0.6 uses separate directories; `results/v0_6/research_index.json` combines their records. Version 0.4/v0.5 results remain frozen. Input, output, audit/specification and converter-code hashes link measurements to the executed source. Dependency pins are in `requirements.lock.txt`; schema and benchmark manifests preserve upstream provenance.", "",
        "## Next work", "",
        "Investigate Clinic's three failing source walls without silently filling holes, resolve or characterise Duplex's closed-Solid contacts, extend independently annotated semantic evaluation, and obtain additional source projects. Geographic accuracy still requires independent checkpoints. The explicit IFC4 map-conversion path is verified on controlled metre/millimetre fixtures with a complete 3D CRS, not on surveyed Torino BIM."])
    write_json(ROOT / "results/v0_6/research_summary.json", {"generated_utc": datetime.now(timezone.utc).isoformat(),
               "code_sha256": current_code, "conversion_attempts": len(records), "completed": passed, "cases": records,
               "semantic_evaluation": {"status": evaluation["status"], "index_sha256": digest(ROOT / "results/v0_6/semantic_evaluation/index.json")},
               "block_evaluation": {"status": block_evaluation["status"], "index_sha256": digest(ROOT / "results/v0_6/block_evaluation/index.json")},
               "torino_context": {k: context[k] for k in ("bbox", "crs", "buildings_count", "event_polygon_count")}})
    (ROOT / "results/v0_6/RESEARCH_PROGRESS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"completed": passed, "attempts": len(records), "report": "results/v0_6/RESEARCH_PROGRESS.md"}))


if __name__ == "__main__":
    main()
