"""Fetch pinned CC-BY building benchmarks, following and verifying Git LFS pointers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen, Request

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "ca3a8e2b94ef79f1a8b28ca0863a7477fb1dd92d"
REPO = "buildingsmart-community/Community-Sample-Test-Files"
FOLDER = "IFC 2.3.0.1 (IFC 2x3)/Duplex Apartment"


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": "IFC-CityGML-research/0.2"}), timeout=60) as response:
        return response.read()


def fetch_case(case_name, folder, filename, attribution):
    directory = ROOT / "data" / "raw" / "benchmarks" / case_name
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    for filename in ("README.md", filename):
        path = folder + "/" + filename
        url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{quote(path)}"
        data = fetch(url)
        lfs = None
        if data.startswith(b"version https://git-lfs.github.com/spec/"):
            pointer = data.decode().splitlines()
            lfs = {line.split(" ", 1)[0]: line.split(" ", 1)[1] for line in pointer}
            url = f"https://media.githubusercontent.com/media/{REPO}/{COMMIT}/{quote(path)}"
            data = fetch(url)
            if len(data) != int(lfs["size"]) or hashlib.sha256(data).hexdigest() != lfs["oid"].split(":")[1]:
                raise RuntimeError("Git LFS object failed size/hash verification")
        (directory / filename).write_bytes(data)
        records.append({"path": str((directory / filename).relative_to(ROOT)), "source_url": url,
                        "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "lfs_pointer": lfs})
    manifest = {"repository": f"https://github.com/{REPO}", "commit": COMMIT, "license": "CC-BY-4.0",
                "attribution": attribution,
                "provenance_type": "non_local_open_building_benchmark", "not_a_torino_building": True,
                "modifications_to_raw": "none", "files": records}
    (directory / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "downloaded_and_hash_verified", "files": [{"path": r["path"], "bytes": r["bytes"]} for r in records]}))


def main():
    fetch_case("duplex", FOLDER, "Duplex_A_20110907.ifc",
               'BSI (2020) "Duplex Apartment Test Files," buildingSMART International')
    fetch_case("clinic", "IFC 2.3.0.1 (IFC 2x3)/Medical-Dental Clinic", "Clinic_Architectural.ifc",
               'BSI (2020) "Medical-Dental Test Files," buildingSMART International')


if __name__ == "__main__":
    main()
