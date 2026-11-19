"""Copy the pinned release resources into the installable package.

Upstream schemas remain byte-identical. The checkout's canonical inputs and the
bundled copies are compared by tests; no network retrieval occurs here.
"""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ("conversion_profile.json", "exterior_profile.json", "source_surfaces_profile.json", "map_conversion_profile.json",
            "engineering_block_profile.json", "engineering_exterior_profile.json", "engineering_source_profile.json")


def main():
    target = ROOT / "src/ifc_citygml/resources"
    (target / "profiles").mkdir(parents=True, exist_ok=True)
    for name in PROFILES:
        shutil.copyfile(ROOT / "config" / name, target / "profiles" / name)
    manifest = json.loads((ROOT / "schemas/manifest.json").read_text())
    records = []
    for entry in manifest["files"]:
        source = ROOT / "schemas" / entry["path"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Canonical schema checksum failed: {source}")
        destination = target / "schemas" / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    for name in ("manifest.json", "README.md"):
        shutil.copyfile(ROOT / "schemas" / name, target / "schemas" / name)
    for path in sorted(target.rglob("*")):
        if path.is_file() and path.name != "resource_manifest.json":
            records.append({"path": path.relative_to(target).as_posix(),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (target / "resource_manifest.json").write_text(json.dumps({"schema_count": len(manifest["files"]),
        "profile_count": len(PROFILES), "files": records}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"bundled_schemas": len(manifest["files"]), "bundled_profiles": len(PROFILES)}))


if __name__ == "__main__":
    main()
