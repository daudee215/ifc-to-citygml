"""Audit current block outputs without overwriting earlier evaluation versions."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ifc_citygml.common import ROOT, code_digest, digest, write_json
from scripts.block_audit import audit


def main():
    folder = ROOT / "results/v0_6/block_evaluation"
    folder.mkdir(parents=True, exist_ok=True)
    cases = []
    for case, run, mode in (("fixture_m", "benchmark_run", "block"), ("gaia_renovation", "engineering_run", "engineering-block"),
                            ("digitalhub", "engineering_run", "engineering-block")):
        index = json.loads((folder.parent / run / "index.json").read_text())
        if index["status"] == "running" or index["converter_source_sha256"] != code_digest():
            raise ValueError("Incomplete/stale block conversion run")
        attempt = next(r for r in index["cases"] if r["case"] == case and r["mode"] == mode)
        if attempt["status"] != "passed":
            raise ValueError("Block output unavailable for audit: " + case)
        gml = folder.parent / run / f"{case}_{mode}.gml"
        if digest(gml) != attempt["output_sha256"]:
            raise ValueError("Block output hash changed")
        result = audit(Path(attempt["input"]), gml, gml.with_suffix(".source_links.json"))
        result.update({"case": case, "mode": mode})
        cases.append(result)
        write_json(folder / (case + ".audit.json"), result)
        print(json.dumps({"case": case, "status": result["status"], "buildings": result["buildings"], "issues": len(result["issues"])}), flush=True)
    result = {"status": "passed" if all(r["status"] == "passed" for r in cases) else "failed",
              "converter_source_sha256": code_digest(), "audit_source_sha256": digest(ROOT / "scripts/block_audit.py"),
              "membership_audit_source_sha256": digest(ROOT / "scripts/semantic_audit.py"),
              "policy_spec_sha256": digest(ROOT / "docs/BLOCK_REPRESENTATIONS.md"), "cases": cases}
    write_json(folder / "index.json", result)
    lines = ["# Physical block audit", "", "Original IFC → actual block GML and source sidecar. Separate audit implementation; selected source bounds are reconstructed using the pinned SDK.", "",
        "| Case | Audit | Physical contributors | Omitted products | Annotation-only omissions | XML max corner error (m) |",
        "|---|---|---:|---:|---:|---:|"]
    for r in cases:
        for b in r["buildings"]:
            lines.append(f"| {r['case']} | {r['status']} | {b['physical_contributors']} | {b['omitted']} | {b['annotation_only_omissions']} | {b['xml_max_corner_error_m']:.3g} |")
    lines.extend(["", "The audit checks membership, every contributor/omission identity, selection and exclusion records, original unapplied map metadata, exact sidecar source bounds and six outward box faces within 1e-6 metre XML serialization tolerance. No source bytes are changed. Raw geometry and complete per-element inventory remain inspectable through the conversion reports/sidecars.", "",
        "A valid block is an axis-aligned aggregate of selected source bodies. Its volume is box volume, not net building volume. These results do not establish surveyed geographic position, vertical datum, independent real-building semantics or flood accuracy.", "",
        "[Selection policy](../../../docs/BLOCK_REPRESENTATIONS.md). Reproduce with `scripts/run_block_evaluation.py`."])
    (folder / "EVALUATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    raise SystemExit(0 if result["status"] == "passed" else 2)


if __name__ == "__main__":
    main()
