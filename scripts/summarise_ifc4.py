"""Inspect original IFC4 metadata and explain all retained extension failures."""
import json
from pathlib import Path
import sys

import ifcopenshell
from pyproj import CRS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ifc_citygml.common import ROOT, code_digest, digest, write_json


def main():
    index_path = ROOT / "results/v0_6/benchmark_ifc4/index.json"
    index = json.loads(index_path.read_text())
    if index["converter_source_sha256"] != code_digest() or index["status"] == "running":
        raise ValueError("IFC4 run is stale/incomplete")
    models, lines = [], ["# Independently authored IFC4 benchmark findings", "",
        "The original 18-attempt v0.4 benchmark is retained unchanged. This extension evaluates original IFC4 files without editing their coordinate metadata. All attempted modes, including explicit native map conversion, remain in the denominator.", "",
        "## Sources and interpretation", "",
        "- **CHEK Gaia renovation**: Stojanov, T.; Martinez, B.; Muro, L.; Gonzalez, A. (2025), *CHEK Project Demonstration Models*, v1, [Zenodo DOI 10.5281/zenodo.17419355](https://zenodo.org/records/17419355), CC BY 4.0. The CHEK [demonstration methodology](https://chekdbp.eu/demonstration-methodology-toolchain/) describes real permit-workflow demonstrations. The file is a renovation demonstration model; independent survey/as-built agreement is not established.", "",
        "- **RWTH DigitalHub v2**: copyright (c) 2020 RWTH Aachen University – E3D, MIT license; [pinned repository](https://github.com/RWTH-E3D/DigitalHub/tree/36565d529b4dadeca625de2b793d7e16700171e9). The [RWTH thesis](https://publications.rwth-aachen.de/record/851025/files/851025.pdf), section 6.1.1, identifies it as a fictional teaching project. It supplies an external design benchmark, not an as-built building.", "",
        "These are original, independently authored BIM files, not project-generated fixtures. Neither is asserted to be a Torino building. Source notices, untouched input bytes, SHA-256 and upstream MD5/Git blob hashes are retained under `data/raw/benchmarks/`.", "",
        "## Inspected source metadata", "",
        "| Model | IFC schema | Building name | Elements | Target CRS | CRS axes | Vertical datum metadata |",
        "|---|---|---|---:|---|---:|---|"]
    for name in dict.fromkeys(r["case"] for r in index["cases"]):
        case = next(r for r in index["cases"] if r["case"] == name)
        source = Path(case["input"])
        if digest(source) != case["input_sha256"]:
            raise ValueError("IFC4 source changed")
        model = ifcopenshell.open(str(source))
        operations = model.by_type("IfcMapConversion")
        op = operations[0]
        target = op.TargetCRS
        record = {"case": name, "input_sha256": digest(source), "schema": model.schema,
                  "building_names": [b.Name for b in model.by_type("IfcBuilding")],
                  "elements": len(model.by_type("IfcElement")), "map_conversion_count": len(operations),
                  "crs": target.Name, "crs_axis_count": len(CRS.from_user_input(target.Name).axis_info),
                  "vertical_datum": target.VerticalDatum, "operation_parameters": {k: v for k, v in op.get_info().items() if k not in {"SourceCRS", "TargetCRS"}}}
        models.append(record)
        lines.append(f"| {name} | {record['schema']} | {', '.join(record['building_names'])} | {record['elements']} | {record['crs']} | {record['crs_axis_count']} | {record['vertical_datum'] or 'not specified'} |")
    lines.extend(["", "## All attempts", "", "| Case | Mode | Status | Reason |", "|---|---|---|---|"])
    failures = []
    for case in index["cases"]:
        report_path = index_path.parent / case["report"]
        report = json.loads(report_path.read_text())
        if report["converter_source_sha256"] != code_digest():
            raise ValueError("Stale attempt report")
        reason = report.get("error", "See full report")
        lines.append(f"| {case['case']} | {case['mode']} | {case['status']} | {reason} |")
        failures.append({"case": case["case"], "mode": case["mode"], "status": case["status"], "error": reason,
                         "report": str(report_path.relative_to(ROOT)), "report_sha256": digest(report_path)})
    engineering_path = ROOT / "results/v0_6/engineering_run/index.json"
    engineering = json.loads(engineering_path.read_text())
    if engineering["status"] == "running" or engineering["converter_source_sha256"] != code_digest():
        raise ValueError("Engineering run is incomplete/stale")
    lines.extend(["", "## Explicit engineering-frame comparison", "",
        "Version 0.5 adds opt-in engineering-frame profiles. They resolve source placements/units while retaining original map metadata without applying it, and label the GML/provenance accordingly. Raw input bytes are unchanged. No geographic position or height datum is asserted.", "",
        "| Case | Engineering mode | Status | Selected geometry/extraction failures |", "|---|---|---|---|"])
    engineering_records = []
    from collections import Counter
    for case in engineering["cases"]:
        path = engineering_path.parent / case["report"]
        report = json.loads(path.read_text())
        reasons = dict(Counter(f["reason"].split(". Product:")[0] for f in report.get("extraction", {}).get("failures", [])))
        lines.append(f"| {case['case']} | {case['mode']} | {case['status']} | `{json.dumps(reasons, sort_keys=True)}` |")
        engineering_records.append({"case": case["case"], "mode": case["mode"], "status": case["status"],
                                    "failure_reasons": reasons, "report_sha256": digest(path), "input_sha256": case["input_sha256"]})
    lines.extend(["", "## Consequence for conversion and auditing", "",
        "Both inputs have an IfcMapConversion and a two-axis horizontal CRS without a vertical datum. Legacy local profiles still require explicit handling; strict map conversion still requires a complete three-axis metre CRS. Those eight strict-profile attempts remain failed before extraction. The engineering attempts are counted separately, not used to replace or relabel the strict failures.", "",
        "Version 0.6 fixes Gaia block extraction by explicitly omitting 32 annotation-only products and aggregating physical Body representations. Mixed products retain their physical bodies. The independent block audit checks contributor/omission records, bounds, XML box faces and unapplied coordinate metadata. Envelope attempts still retain mesh/union failures; they are not repaired by annotation selection.", "",
        "Successful engineering source outputs receive independent implementation audits of fresh source triangles, XML host/class/identity relationships, omissions and the original unapplied coordinate metadata. These establish source preservation, not real-building structural accuracy or geographic accuracy. The verified v0.4 wheel and its original benchmark directories remain unchanged.", "",
        "## Reproduce", "", "```powershell",
        ".venv/Scripts/python.exe scripts/fetch_ifc4_benchmark.py",
        ".venv/Scripts/python.exe scripts/fetch_digitalhub.py",
        ".venv/Scripts/python.exe scripts/run_ifc4_benchmarks.py  # nonzero while unsupported",
        ".venv/Scripts/python.exe scripts/run_engineering_benchmarks.py  # retains geometry failures",
        ".venv/Scripts/python.exe scripts/run_semantic_evaluation.py",
        ".venv/Scripts/python.exe scripts/summarise_ifc4.py", "```", "",
        "The combined research index references both retained runs. Original benchmark results, topology diagnostics and four successful semantic audits remain available separately."])
    write_json(ROOT / "results/v0_6/ifc4_benchmark_findings.json", {"models": models, "attempts": failures, "engineering_attempts": engineering_records,
               "converter_source_sha256": code_digest(), "index_sha256": digest(index_path)})
    (ROOT / "results/v0_6/IFC4_BENCHMARK_FINDINGS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"models": len(models), "attempts": len(failures), "completed": index["completed"], "failed": index["failed"]}))


if __name__ == "__main__":
    main()
