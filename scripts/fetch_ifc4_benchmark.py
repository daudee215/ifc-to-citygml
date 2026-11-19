"""Fetch the pinned CHEK Gaia renovation demonstration IFC and original metadata."""
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RECORD = "17419355"
FILENAME = "0_Gaia Rennovation Demo Building.ifc"
EXPECTED_SIZE = 5869811
EXPECTED_MD5 = "739f20a1a27a3c2b90ca4bd26c9f5246"
EXPECTED_SHA256 = "999ad93d9fc6be62e843a0778369cdd5a2feb4d7a8586fd67ea2a1ebe6888646"


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": "IFC-CityGML-research/0.4"}), timeout=60) as response:
        return response.read()


def main():
    folder = ROOT / "data/raw/benchmarks/gaia_renovation"
    folder.mkdir(parents=True, exist_ok=True)
    metadata_url = f"https://zenodo.org/api/records/{RECORD}"
    metadata_bytes = fetch(metadata_url)
    metadata = json.loads(metadata_bytes)
    if metadata["metadata"]["license"]["id"] != "cc-by-4.0":
        raise ValueError("Upstream license metadata changed; review the terms")
    item = next(f for f in metadata["files"] if f["key"] == FILENAME)
    if item["checksum"] != "md5:" + EXPECTED_MD5 or item["size"] != EXPECTED_SIZE:
        raise ValueError("Pinned upstream file metadata changed")
    target = folder / FILENAME
    data = target.read_bytes() if target.exists() else fetch(item["links"]["self"])
    if len(data) != EXPECTED_SIZE or hashlib.md5(data).hexdigest() != EXPECTED_MD5 or hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
        raise ValueError("Downloaded original IFC failed pinned size/checksum verification")
    if not data.startswith(b"ISO-10303-21"):
        raise ValueError("Expected an IFC STEP file")
    target.write_bytes(data)
    (folder / "record_metadata.json").write_bytes(metadata_bytes)
    manifest = {"repository": f"https://zenodo.org/records/{RECORD}", "commit": "Zenodo record " + RECORD + " version v1",
        "doi": "10.5281/zenodo." + RECORD, "license": "CC-BY-4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "Stojanov, T.; Martinez, B.; Muro, L.; Gonzalez, A. (2025). CHEK Project Demonstration Models, v1. Zenodo. DOI: 10.5281/zenodo.17419355",
        "provenance_type": "independent_permit_demonstration_building_model", "not_a_torino_building": True,
        "physical_reality_status": "Published renovation demonstration model; independent survey/as-built agreement not established",
        "modifications_to_raw": "none", "files": [
            {"path": str(target.relative_to(ROOT)), "source_url": item["links"]["self"], "bytes": len(data),
             "sha256": hashlib.sha256(data).hexdigest(), "upstream_md5": EXPECTED_MD5},
            {"path": str((folder / "record_metadata.json").relative_to(ROOT)), "source_url": metadata_url,
             "bytes": len(metadata_bytes), "sha256": hashlib.sha256(metadata_bytes).hexdigest()}]}
    (folder / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (folder / "README.md").write_text("# CHEK Gaia renovation demonstration\n\n" + manifest["attribution"] + "\n\n"
        "License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Original bytes are unchanged; CityGML outputs are derived conversions. "
        "This is an independently authored permit-demonstration model, not a project-generated fixture. "
        "It is not a Torino building and is not independently verified as a surveyed/as-built record. "
        "The original filename contains the spelling 'Rennovation'.\n\n"
        "Published record: https://zenodo.org/records/17419355. Project context: https://chekdbp.eu/demonstration-methodology-toolchain/. "
        "Raw record metadata, upstream checksum and SHA-256 are retained in source_manifest.json.\n", encoding="utf-8")
    print(json.dumps({"status": "downloaded_and_hash_verified", "file": FILENAME, "bytes": len(data), "sha256": manifest["files"][0]["sha256"]}))


if __name__ == "__main__":
    main()
