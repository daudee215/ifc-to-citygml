"""Freeze verified v0.4 source and evidence hashes before next-version development."""
import json
from pathlib import Path
import sys
import zipfile
import argparse
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ifc_citygml.common import ROOT, code_digest, digest, write_json


def main(version="0.4.0"):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Release version must have three numeric components")
    result_folder = ROOT / "results" if version == "0.4.0" else ROOT / "results" / ("v" + "_".join(version.split(".")[:2]))
    folder = ROOT / "releases" / version
    manifest_path = folder / "RELEASE_MANIFEST.json"
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text())
        for item in data["preserved_files"]:
            if digest(ROOT / item["path"]) != item["sha256"]:
                raise ValueError("Preserved release artifact changed: " + item["path"])
        print(f"Existing v{version} preservation manifest verified; no files overwritten.")
        return
    clean_path = result_folder / "packaging/CLEAN_INSTALL_VERIFICATION.json"
    clean = json.loads(clean_path.read_text())
    if clean["status"] != "passed" or clean["version"] != version or clean["doctor"]["converter_source_sha256"] != code_digest():
        raise ValueError("Freeze requires the verified converter source/version")
    if digest(Path(clean["wheel"])) != clean["wheel_sha256"]:
        raise ValueError("Verified release wheel changed")
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / "source.zip"
    candidates = [ROOT / n for n in ("pyproject.toml", "requirements.lock.txt", "README.md")]
    for directory in ("src", "config", "schemas", "scripts", "tests", "docs"):
        candidates.extend(p for p in (ROOT / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(candidates):
            zipped.write(path, path.relative_to(ROOT).as_posix())
    preserved = [archive, Path(clean["wheel"]), clean_path]
    for directory in ("benchmark_run", "benchmark_ifc4", "engineering_run", "semantic_evaluation", "block_evaluation"):
        preserved.extend(p for p in (result_folder / directory).glob("*") if p.is_file())
    if version != "0.4.0":
        preserved.extend(p for p in result_folder.glob("*") if p.is_file())
        preserved.extend(p for p in (result_folder / "review").glob("*") if p.is_file())
    records = [{"path": p.relative_to(ROOT).as_posix(), "sha256": digest(p)} for p in sorted(preserved)]
    write_json(manifest_path, {"version": version, "converter_source_sha256": code_digest(),
        "wheel_sha256": clean["wheel_sha256"], "source_archive": str(archive.relative_to(ROOT)), "preserved_files": records,
        "policy": "Do not overwrite listed artifacts; next-version results use separate directories. Raw benchmark inputs remain unchanged."})
    print(json.dumps({"status": "preserved", "archive": str(archive), "artifacts": len(records)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="0.4.0")
    main(parser.parse_args().version)
