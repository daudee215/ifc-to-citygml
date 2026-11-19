"""Install a pinned upstream Windows validator release in the project tool cache."""
import hashlib
import io
import json
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
URL = "https://github.com/tudelft3d/val3dity/releases/download/2.7.0/val3dity-win64.zip"
SHA256 = "cf8d3f025cd52aafc9ea370296a2430baa4aa39ce44a8b3ba1d8b3a540d8a5a7"


def main():
    with urlopen(URL, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Validator archive checksum mismatch")
    target = (ROOT / "tools" / "val3dity").resolve()
    target.mkdir(parents=True, exist_ok=True)
    with ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            if not (target / name).resolve().is_relative_to(target):
                raise ValueError("Archive contains unsafe path")
        archive.extractall(target)
    # The published release currently wraps the executable archive in another ZIP.
    for nested in target.glob("*.zip"):
        with ZipFile(nested) as archive:
            for name in archive.namelist():
                if not (target / name).resolve().is_relative_to(target):
                    raise ValueError("Nested archive contains unsafe path")
            archive.extractall(target)
    (target / "source_manifest.json").write_text(json.dumps({"url": URL, "version": "2.7.0", "sha256": SHA256,
        "license_source": "https://github.com/tudelft3d/val3dity/blob/main/LICENSE"}, indent=2), encoding="utf-8")
    print(json.dumps({"downloaded": URL, "executables": [str(p) for p in target.rglob("*.exe")]}))


if __name__ == "__main__":
    main()
