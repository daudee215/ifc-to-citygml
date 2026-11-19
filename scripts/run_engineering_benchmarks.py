"""Run explicit engineering-frame v0.5 profiles, leaving v0.4 evidence untouched."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ifc_citygml.benchmark import run_benchmark
from ifc_citygml.common import ROOT, digest, write_json


def main():
    manifest = ROOT / "data/manifests/engineering_v0_6.json"
    cases = []
    for name, filename in (("gaia_renovation", "0_Gaia Rennovation Demo Building.ifc"), ("digitalhub", "DigitalHub_FM-ARC_v2.ifc")):
        folder = ROOT / "data/raw/benchmarks" / name
        metadata = json.loads((folder / "source_manifest.json").read_text())
        source = folder / filename
        pinned = next(r["sha256"] for r in metadata["files"] if Path(r["path"]).name == filename)
        if digest(source) != pinned:
            raise ValueError("Original input changed: " + name)
        cases.append({"id": name, "input": os.path.relpath(source, manifest.parent).replace("\\", "/"), "provenance": metadata})
    write_json(manifest, {"format_version": 1, "profiles": ["engineering-block", "engineering-exterior", "engineering-source"], "cases": cases})
    index = run_benchmark(manifest, ROOT / "results/v0_6/engineering_run", progress=lambda r: print(json.dumps({k: r[k] for k in ("case", "mode", "status", "report")}), flush=True))
    print(json.dumps({k: index[k] for k in ("status", "attempts", "completed", "failed")}))
    return 2 if index["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
