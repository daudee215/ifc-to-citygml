"""Read frozen v0.6 evidence and create a separate reporting snapshot and review."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/methodology_v0_6"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_frozen():
    records = []
    for version in ("0.4.0", "0.5.0", "0.6.0"):
        path = ROOT / "releases" / version / "RELEASE_MANIFEST.json"
        manifest = json.loads(path.read_text())
        for item in manifest["preserved_files"]:
            if sha(ROOT / item["path"]) != item["sha256"]:
                raise ValueError("Frozen artifact changed: " + item["path"])
        records.append({"version": version, "manifest_sha256": sha(path), "artifacts_verified": len(manifest["preserved_files"])})
    return records


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frozen = verify_frozen()
    base = ROOT / "results/v0_6"
    files = {"research": base / "research_summary.json", "attempts": base / "research_index.json",
             "source_audits": base / "semantic_evaluation/index.json", "block_audits": base / "block_evaluation/index.json",
             "clean_install": base / "packaging/CLEAN_INSTALL_VERIFICATION.json", "release_audit": base / "packaging/RELEASE_AUDIT.json",
             "torino": ROOT / "data/raw/torino_context/source_manifest.json"}
    evidence = {name: json.loads(path.read_text()) for name, path in files.items()}
    evidence["provenance"] = {"frozen_releases": frozen, "files": {name: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)} for name, path in files.items()}}
    report_file = base / "engineering_run/gaia_renovation_engineering-block.report.json"
    evidence["validator_parameters"] = json.loads(report_file.read_text())["validation"]["external_validation"]["report"]["parameters"]
    evidence["datasets"] = {p.parent.name: json.loads(p.read_text()) for p in (ROOT / "data/raw/benchmarks").glob("*/source_manifest.json")}
    for manifest in evidence["datasets"].values():
        for item in manifest["files"]:
            if sha(ROOT / item["path"]) != item["sha256"]:
                raise ValueError("Raw benchmark input/metadata changed")
    for item in evidence["torino"]["files"]:
        if sha(ROOT / item["path"]) != item["sha256"]:
            raise ValueError("Raw Torino response changed")
    (OUT / "evidence_snapshot.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

    original = base / "review/index.html"
    page = original.read_text(encoding="utf-8")
    match = re.search(r"const DATA=(.*?);\s*\nconst colours=", page, re.S)
    if not match:
        raise ValueError("Cannot locate frozen review data")
    data = json.loads(match.group(1))
    corrections = []
    for model in data["models"]:
        report_path = (original.parent / model["report"]).resolve()
        validation = json.loads(report_path.read_text())["validation"]
        is_block = model["representation"] == "axis_aligned_bounding_block"
        model["independent"] = validation.get("independent_general_solid_validation", "not run") if is_block else validation.get("independent_surface_validation", "not run")
        model["solid"] = "not applicable" if is_block else validation.get("independent_general_solid_validation", "not run")
        if is_block:
            corrections.append({"model": model["label"], "declared_geometry": "Solid", "target_check": model["independent"], "additional_solid_check": "not applicable"})
    for case in data["cases"]:
        path = base / case["report"]
        # Frozen combined case paths are relative to results/v0_6.
        validation = json.loads(path.read_text()).get("validation", {})
        is_block = case["mode"].endswith("block")
        case["independent"] = validation.get("independent_general_solid_validation", "not run") if is_block else validation.get("independent_surface_validation", "not run")
        case["solid"] = "not applicable" if is_block else validation.get("independent_general_solid_validation", "not run")
    payload = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c")
    page = page[:match.start(1)] + payload + page[match.end(1):]
    page = page.replace("<head>", '<head><base href="../../../results/v0_6/review/">', 1)
    old_label = "'XSD: '+m.xsd+' · Independent declared geometry: '+m.independent+' · Closed-Solid diagnostic: '+m.solid"
    new_label = "'XSD: '+m.xsd+(m.representation==='axis_aligned_bounding_block'?' · Declared Solid: '+m.independent+' · Additional Solid diagnostic: not applicable':' · Declared MultiSurface: '+m.independent+' · Stronger Solid diagnostic: '+m.solid)"
    if old_label not in page:
        raise ValueError("Cannot locate original validation label")
    page = page.replace(old_label, new_label)
    page = page.replace("<th>Independent surfaces</th>", "<th>Declared geometry check</th>")
    page = page.replace("<th>Closed-Solid diagnostic</th>", "<th>Additional Solid diagnostic</th>")
    review = OUT / "review"
    review.mkdir(exist_ok=True)
    (review / "index.html").write_text(page, encoding="utf-8")
    (OUT / "review_corrections.json").write_text(json.dumps({"source_html_sha256": sha(original), "new_html_sha256": sha(review / "index.html"),
        "geometry_payload_unchanged": all(a["polygons"] == b["polygons"] for a, b in zip(json.loads(match.group(1))["models"], data["models"])),
        "corrections": corrections}, indent=2) + "\n", encoding="utf-8")
    verify_frozen()
    print(json.dumps({"snapshot": str(OUT / "evidence_snapshot.json"), "models_relabelled": len(corrections), "frozen_releases_unchanged": True}))


if __name__ == "__main__":
    main()
