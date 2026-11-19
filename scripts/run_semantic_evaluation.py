"""Execute authored semantic cases and independent audits of real benchmark outputs."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import ifcopenshell
import ifcopenshell.validate

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ifc_citygml.common import ROOT, code_digest, digest, write_json
from ifc_citygml.pipeline import convert
from scripts.generate_semantic_cases import make_case
from scripts.semantic_audit import audit


def main():
    folder = ROOT / "results/v0_6/semantic_evaluation"
    folder.mkdir(parents=True, exist_ok=True)
    records = []
    for schema in ("IFC4", "IFC2X3"):
        source = ROOT / f"data/raw/semantic_cases_v0_6/{schema.lower()}.ifc"
        make_case(source, schema)
        logger = ifcopenshell.validate.json_logger()
        ifcopenshell.validate.validate(ifcopenshell.open(str(source)), logger)
        if logger.statements:
            raise ValueError(f"Controlled IFC schema validation failed: {logger.statements}")
        output = folder / (schema.lower() + ".gml")
        convert(source, output, "source")
        result = audit(source, output, output.with_suffix(".source_links.json"), source.with_suffix(".expected.json"))
        result["case"] = "controlled_" + schema.lower()
        result["source_schema_attribute_validation"] = "passed"
        records.append(result)
        write_json(folder / (result["case"] + ".audit.json"), result)
        print(json.dumps({"case": result["case"], "status": result["status"], "issues": len(result["issues"])}), flush=True)
    index = json.loads((ROOT / "results/v0_6/benchmark_run/index.json").read_text())
    if index["status"] not in {"completed", "completed_with_failures"} or index["converter_source_sha256"] != code_digest():
        raise ValueError("Complete a current benchmark run before semantic evaluation")
    for case in ("duplex", "clinic", "gaia_renovation", "digitalhub"):
        engineering = case in ("gaia_renovation", "digitalhub")
        case_index = json.loads((ROOT / "results/v0_6/engineering_run/index.json").read_text()) if engineering else index
        mode = "engineering-source" if engineering else "source"
        attempt = next(r for r in case_index["cases"] if r["case"] == case and r["mode"] == mode)
        if attempt["status"] != "passed":
            raise ValueError(f"Cannot audit unsuccessful source conversion: {case}")
        output = ROOT / "results/v0_6" / ("engineering_run" if engineering else "benchmark_run") / f"{case}_{mode}.gml"
        if digest(output) != attempt["output_sha256"]:
            raise ValueError(f"Benchmark output changed: {case}")
        result = audit(Path(attempt["input"]), output, output.with_suffix(".source_links.json"))
        result["case"] = case
        result["mode"] = mode
        records.append(result)
        write_json(folder / (case + ".audit.json"), result)
        print(json.dumps({"case": case, "status": result["status"], "issues": len(result["issues"])}), flush=True)
    summary = {"status": "passed" if all(r["status"] == "passed" for r in records) else "failed",
               "generated_utc": datetime.now(timezone.utc).isoformat(), "converter_source_sha256": code_digest(),
               "mapping_spec_sha256": digest(ROOT / "docs/SEMANTIC_MAPPING.md"),
               "coordinate_policy_spec_sha256": digest(ROOT / "docs/ENGINEERING_FRAME.md"),
               "audit_source_sha256": digest(ROOT / "scripts/semantic_audit.py"),
               "fixture_author_sha256": digest(ROOT / "scripts/generate_semantic_cases.py"),
               "runner_source_sha256": digest(Path(__file__)),
               "cases": records}
    write_json(folder / "index.json", summary)
    lines = ["# Source-to-CityGML semantic and provenance evaluation", "",
             "Measured source-profile audits. Expected controlled classes/associations are authored separately from the converter; the auditor reads original IFC, actual XML and the sidecar.", "",
             "| Case | Audit | Expected / exported features | Features checked | Exact source triangles | Omitted elements | Mismatches |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for r in records:
        lines.append(f"| {r['case']} | {r['status']} | {r['expected_features']} / {r['exported_features']} | {r['selected_features']} | {r['triangles_checked']} | {len(r['omissions'])} | {len(r['issues'])} |")
    lines.extend(["", "## Associations and omissions", ""])
    for r in records:
        lines.append(f"- **{r['case']}**: associations `{json.dumps(r['by_association'], sort_keys=True)}`; omissions `{json.dumps(r['omission_reasons'], sort_keys=True)}`.")
    lines.extend(["", "## Interpretation", "",
        "Zero mismatches establishes agreement with the declared source mapping, exact fresh SDK tessellation, source identities, properties and opening/host relationships. It does not prove independently annotated real-building structural significance or exterior semantics. IFC classes are preserved as declared constructive candidates; LoadBearing does not imply CityGML isStructuralElement.", "",
        "The two controlled specimens each cover twelve constructive classes, a wall subclass, two buildings, selected/unrepresented/unselected hosts and standalone fillings. Their expected annotations are project-authored, not external expert labels. The fresh geometry audit shares the pinned IfcOpenShell kernel with conversion.", "",
        "Valid MultiSurface output can fail the stronger closed-Solid check. Clinic's separate envelope conversion remains failed; it is not counted as a semantic-audit success. No model is asserted to be a Torino building and no flood-exposure accuracy is inferred.", "",
        "[Mapping specification](../../../docs/SEMANTIC_MAPPING.md) and [engineering coordinate policy](../../../docs/ENGINEERING_FRAME.md). Per-feature checks, omission inventories, input/output/auditor hashes and all mismatches are retained in the JSON files. Reproduce with `scripts/run_semantic_evaluation.py`."])
    (folder / "EVALUATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    raise SystemExit(0 if summary["status"] == "passed" else 2)


if __name__ == "__main__":
    main()
