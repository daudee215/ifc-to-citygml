"""Fetch an independently authored IFC4 design benchmark with its MIT notice."""
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "36565d529b4dadeca625de2b793d7e16700171e9"
FILES = {"README.md": "a2afbe688e2ff58f4d0ba7281a05470c3078ef06", "LICENSE": "14122c2ad0ffd9bedb31b11eeeaab9df1541796c",
         "Version_2/DigitalHub_FM-ARC_v2.ifc": "c3951b5061cdabecdeaf7eaa0f957175221200f5"}


def main():
    folder = ROOT / "data/raw/benchmarks/digitalhub"
    folder.mkdir(parents=True, exist_ok=True)
    records = []
    for path, expected in FILES.items():
        url = f"https://raw.githubusercontent.com/RWTH-E3D/DigitalHub/{COMMIT}/{path}"
        target = folder / Path(path).name
        data = target.read_bytes() if target.exists() else urlopen(Request(url, headers={"User-Agent": "IFC-CityGML-research/0.4"}), timeout=60).read()
        git_sha = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if git_sha != expected:
            raise ValueError("Pinned Git blob hash mismatch: " + path)
        target.write_bytes(data)
        records.append({"path": str(target.relative_to(ROOT)), "source_url": url, "git_blob_sha1": git_sha,
                        "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    metadata = {"repository": "https://github.com/RWTH-E3D/DigitalHub", "commit": COMMIT, "license": "MIT",
        "attribution": "Copyright (c) 2020 RWTH Aachen University - E3D Institute of Energy Efficiency and Sustainable Building",
        "provenance_type": "independent_fictional_teaching_design_benchmark", "not_a_torino_building": True,
        "physical_reality_status": "Fictional teaching design, not an as-built building; see RWTH thesis record 851025, section 6.1.1",
        "modifications_to_raw": "none", "files": records}
    (folder / "source_manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "downloaded_and_hash_verified", "files": len(records)}))


if __name__ == "__main__":
    main()
