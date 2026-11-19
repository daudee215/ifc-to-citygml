"""Execute reproducible synthetic and open-building conversion comparisons.

Failures remain in the aggregate results. This script does not silently replace
failed detailed conversions with blocks.
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ifc_citygml.common import ROOT, write_json, software_versions
from ifc_citygml.benchmark import run_benchmark
import os
from scripts.generate_fixtures import main as fixtures


def main():
    if not (ROOT / "data/raw/fixtures/building_ifc2x3.ifc").exists():
        fixtures()
    candidates = [("fixture_m", ROOT / "data/raw/fixtures/building_m.ifc"),
                  ("fixture_mm", ROOT / "data/raw/fixtures/building_mm.ifc"),
                  ("fixture_rotated", ROOT / "data/raw/fixtures/building_rotated.ifc"),
                  ("fixture_ifc2x3", ROOT / "data/raw/fixtures/building_ifc2x3.ifc"),
                  ("duplex", ROOT / "data/raw/benchmarks/duplex/Duplex_A_20110907.ifc"),
                  ("clinic", ROOT / "data/raw/benchmarks/clinic/Clinic_Architectural.ifc")]
    manifest_path = ROOT / "data/manifests/benchmark_v0_6.json"
    cases = []
    for name, source in candidates:
        provenance = {"kind": "controlled_fixture" if name.startswith("fixture") else "non_local_open_building_benchmark"}
        source_manifest = source.parent / "source_manifest.json"
        if source_manifest.exists():
            metadata = json.loads(source_manifest.read_text())
            provenance.update({key: metadata[key] for key in ("repository", "commit", "license", "attribution", "not_a_torino_building")})
        cases.append({"id": name, "input": os.path.relpath(source, manifest_path.parent).replace("\\", "/"), "provenance": provenance})
    write_json(manifest_path, {"format_version": 1, "profiles": ["block", "exterior", "source"], "cases": cases})
    index = run_benchmark(manifest_path, ROOT / "results/v0_6/benchmark_run", progress=lambda c: print(json.dumps({k: c[k] for k in ("case", "mode", "status", "report")}), flush=True))
    print(json.dumps({"status": index["status"], "completed": index["completed"], "failed": index["failed"]}))
    # The research wrapper deliberately collects the known envelope failure.
    # The installed CLI returns nonzero unless --allow-failures is explicit.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
