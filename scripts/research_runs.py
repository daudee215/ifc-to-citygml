"""Combine retained research runs without overwriting original benchmark evidence."""
import json
from pathlib import Path

from ifc_citygml.benchmark import report_path
from ifc_citygml.common import ROOT, code_digest, digest, write_json

RUNS = ("benchmark_run", "benchmark_ifc4", "engineering_run")


def research_index():
    target = ROOT / "results/v0_6/research_index.json"
    combined = {"format_version": 1, "report_base": "index_directory", "runs": [], "cases": []}
    seen = set()
    for name in RUNS:
        path = target.parent / name / "index.json"
        index = json.loads(path.read_text())
        if index["status"] not in {"completed", "completed_with_failures"}:
            raise ValueError("Research run is incomplete: " + name)
        if index["converter_source_sha256"] != code_digest():
            raise ValueError("Research run used different converter code: " + name)
        combined["runs"].append({"path": str(path.relative_to(target.parent)), "sha256": digest(path)})
        for case in index["cases"]:
            key = (case["case"], case["mode"])
            if key in seen:
                raise ValueError("Duplicate research attempt: " + str(key))
            seen.add(key)
            record = {**case, "research_run": name, "report": str(report_path(path, index, case, ROOT).relative_to(target.parent))}
            combined["cases"].append(record)
    combined.update({"converter_source_sha256": code_digest(), "attempts": len(combined["cases"]),
                     "completed": sum(c["status"] == "passed" for c in combined["cases"])})
    combined["failed"] = combined["attempts"] - combined["completed"]
    combined["status"] = "completed_with_failures" if combined["failed"] else "completed"
    write_json(target, combined)
    return target, combined
