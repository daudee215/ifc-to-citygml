"""Record all strict conversion attempts on new IFC4 inputs without changing raw data."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ifc_citygml.benchmark import run_benchmark
from ifc_citygml.common import ROOT, digest, write_json


def main():
    manifest_path = ROOT / "data/manifests/ifc4_benchmarks_v0_6.json"
    cases = []
    for name, filename in (("gaia_renovation", "0_Gaia Rennovation Demo Building.ifc"),
                           ("digitalhub", "DigitalHub_FM-ARC_v2.ifc")):
        folder = ROOT / "data/raw/benchmarks" / name
        metadata = json.loads((folder / "source_manifest.json").read_text())
        source = folder / filename
        expected = next(f["sha256"] for f in metadata["files"] if Path(f["path"]).name == filename)
        if digest(source) != expected:
            raise ValueError("Raw benchmark input changed: " + name)
        cases.append({"id": name, "input": os.path.relpath(source, manifest_path.parent).replace("\\", "/"),
                      "provenance": {k: metadata[k] for k in ("repository", "commit", "license", "attribution", "provenance_type", "physical_reality_status", "not_a_torino_building")}})
    write_json(manifest_path, {"format_version": 1, "profiles": ["block", "exterior", "source", "map"], "cases": cases})
    index = run_benchmark(manifest_path, ROOT / "results/v0_6/benchmark_ifc4", progress=lambda r: print(json.dumps({k: r[k] for k in ("case", "mode", "status", "report")}), flush=True))
    print(json.dumps({"status": index["status"], "attempts": index["attempts"], "completed": index["completed"], "failed": index["failed"]}))
    return 2 if index["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
