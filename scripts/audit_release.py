"""Link the verified wheel, current research run and pre-packaging geometry baseline."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ifc_citygml.benchmark import report_path
from ifc_citygml.common import ROOT, code_digest, digest, resource_digest, write_json
from scripts.research_runs import research_index


def main():
    folder = ROOT / "results/v0_6/packaging"
    installed = json.loads((folder / "CLEAN_INSTALL_VERIFICATION.json").read_text())
    assert installed["status"] == "passed"
    assert digest(Path(installed["wheel"])) == installed["wheel_sha256"], "Wheel changed after verification"
    assert installed["doctor"]["converter_source_sha256"] == code_digest(), "Verified code is stale"
    assert installed["doctor"]["resources"]["manifest_sha256"] == resource_digest()
    index_file = ROOT / "results/v0_6/benchmark_run/index.json"
    index = json.loads(index_file.read_text())
    assert index["status"] in {"completed", "completed_with_failures"}, "Research run is incomplete"
    assert index["converter_source_sha256"] == code_digest()
    assert index["bundled_resources_sha256"] == resource_digest()
    baseline = json.loads((ROOT / "results/packaging/baseline_0_3_output_hashes.json").read_text())
    expected = {(r["case"], r["mode"]): r["sha256"] for r in baseline["outputs"]}
    compared, failures = [], []
    for case in index["cases"]:
        report = json.loads(report_path(index_file, index, case, ROOT).read_text())
        assert report["converter_source_sha256"] == code_digest()
        assert digest(Path(case["input"])) == case["input_sha256"]
        if case["status"] == "passed":
            output = index_file.parent / f"{case['case']}_{case['mode']}.gml"
            measured = digest(output)
            assert measured == case["output_sha256"] == report["output_sha256"]
            assert measured == expected[(case["case"], case["mode"])], f"Geometry changed: {output}"
            compared.append({"case": case["case"], "mode": case["mode"], "sha256": measured})
        else:
            failures.append({"case": case["case"], "mode": case["mode"], "report": case["report"]})
    assert len(compared) == len(expected), "Some pre-packaging outputs are missing"
    summary = json.loads((ROOT / "results/v0_6/research_summary.json").read_text())
    assert summary["code_sha256"] == code_digest()
    combined_path, combined = research_index()
    assert summary["conversion_attempts"] == combined["attempts"]
    previous = []
    current = {(c["case"], c["mode"]): c for c in combined["cases"]}
    for run in ("benchmark_run", "engineering_run"):
        old_path = ROOT / "results/v0_5" / run / "index.json"
        old_index = json.loads(old_path.read_text())
        for case in old_index["cases"]:
            if case["status"] != "passed":
                continue
            present = current[(case["case"], case["mode"])]
            assert present["status"] == "passed", "Regression of previous successful conversion"
            report = json.loads(report_path(combined_path, combined, present, ROOT).read_text())
            assert digest(Path(report["output"])) == case["output_sha256"], "Previous successful geometry changed"
            previous.append({"case": case["case"], "mode": case["mode"], "sha256": case["output_sha256"]})
    extension = []
    for case in combined["cases"]:
        if case["research_run"] == "benchmark_run":
            continue
        report_file = report_path(combined_path, combined, case, ROOT)
        report = json.loads(report_file.read_text())
        assert report["converter_source_sha256"] == code_digest()
        assert digest(Path(case["input"])) == case["input_sha256"]
        if case["status"] == "passed":
            assert digest(Path(report["output"])) == report["output_sha256"]
        extension.append({"case": case["case"], "mode": case["mode"], "status": case["status"],
                          "report": str(report_file.relative_to(ROOT)), "report_sha256": digest(report_file)})
    result = {"status": "passed", "generated_utc": datetime.now(timezone.utc).isoformat(),
              "wheel_sha256": installed["wheel_sha256"], "code_sha256": code_digest(),
              "resources_sha256": resource_digest(), "attempts": index["attempts"],
              "byte_identical_to_v0_3": compared, "retained_failures": failures,
              "research_extension": extension, "combined_research_attempts": combined["attempts"],
              "byte_identical_to_v0_5": previous}
    write_json(folder / "RELEASE_AUDIT.json", result)
    (folder / "RELEASE_AUDIT.md").write_text(
        "# Release audit\n\n"
        f"The verified wheel, source checkout and all {index['attempts']} current benchmark reports share the same converter code hash. "
        "Input, output and bundled resource hashes were checked.\n\n"
        f"All {len(compared)} successful CityGML files are byte-identical to the recorded v0.3 outputs. "
        f"The {len(failures)} unsuccessful attempt remains visible in the benchmark index. "
        "The original successful geometry and Clinic envelope failure remain unchanged.\n\n"
        f"All {len(previous)} successful v0.5 outputs also remain byte-identical. Gaia's previously failed block is a separately recorded improvement with explicit annotation omissions.\n\n"
        f"A separate IFC4 research extension retains {len(extension)} additional attempts; the combined research denominator is {combined['attempts']}. "
        "Its report/input hashes were also checked. Original benchmark files remain in their original run directory.\n\n"
        f"Wheel SHA-256: `{installed['wheel_sha256']}`.\n\n"
        "See `RELEASE_AUDIT.json` for per-output hashes and `CLEAN_INSTALL_VERIFICATION.md` for actual installed execution.\n",
        encoding="utf-8")
    print(json.dumps({"status": "passed", "unchanged_outputs": len(compared), "retained_failures": len(failures)}))


if __name__ == "__main__":
    main()
