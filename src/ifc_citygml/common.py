from __future__ import annotations

import hashlib
import json
import math
from importlib.metadata import version
from pathlib import Path

import numpy as np

PACKAGE_DIR = Path(__file__).resolve().parent
_candidate_root = PACKAGE_DIR.parents[1]
CHECKOUT_ROOT = _candidate_root if (_candidate_root / "pyproject.toml").is_file() and (_candidate_root / "src/ifc_citygml").resolve() == PACKAGE_DIR else None
# Legacy research scripts use ROOT. Runtime resources never depend on this path.
ROOT = CHECKOUT_ROOT or Path.cwd()
RESOURCE_DIR = PACKAGE_DIR / "resources"
SCHEMA_DIR = RESOURCE_DIR / "schemas"
BUILTIN_PROFILES = {"block": "conversion_profile.json", "exterior": "exterior_profile.json",
                    "source": "source_surfaces_profile.json", "map": "map_conversion_profile.json",
                    "engineering-block": "engineering_block_profile.json",
                    "engineering-exterior": "engineering_exterior_profile.json",
                    "engineering-source": "engineering_source_profile.json"}
DEFAULT_PROFILE = RESOURCE_DIR / "profiles" / BUILTIN_PROFILES["block"]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def software_versions() -> dict:
    return {name: version(name) for name in ("ifc-citygml", "ifcopenshell", "numpy", "lxml", "shapely", "manifold3d", "trimesh", "networkx", "pyproj")}


def code_digest() -> str:
    checksum = hashlib.sha256()
    for path in sorted(PACKAGE_DIR.glob("*.py")):
        checksum.update(path.name.encode())
        checksum.update(path.read_bytes())
    return checksum.hexdigest()


def profile_path(value: Path | str | None = None) -> Path:
    if value is None:
        return DEFAULT_PROFILE
    if isinstance(value, str) and value in BUILTIN_PROFILES:
        return RESOURCE_DIR / "profiles" / BUILTIN_PROFILES[value]
    return Path(value)


def resource_digest() -> str:
    return digest(RESOURCE_DIR / "resource_manifest.json")


def verify_resources() -> dict:
    manifest = json.loads((RESOURCE_DIR / "resource_manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        path = (RESOURCE_DIR / item["path"]).resolve()
        if not path.is_relative_to(RESOURCE_DIR.resolve()) or digest(path) != item["sha256"]:
            raise ValueError(f"Bundled resource integrity failed: {item['path']}")
    return {"status": "passed", "manifest_sha256": resource_digest(),
            "schema_count": manifest["schema_count"], "profile_count": manifest["profile_count"]}


def load_profile(path: Path | str | None = None) -> dict:
    selected = profile_path(path)
    if selected.resolve().is_relative_to((RESOURCE_DIR / "profiles").resolve()):
        relative = selected.resolve().relative_to(RESOURCE_DIR.resolve()).as_posix()
        manifest = json.loads((RESOURCE_DIR / "resource_manifest.json").read_text(encoding="utf-8"))
        expected = next((item["sha256"] for item in manifest["files"] if item["path"] == relative), None)
        if expected is None or digest(selected) != expected:
            raise ValueError(f"Bundled profile integrity failed: {relative}")
    profile = json.loads(selected.read_text(encoding="utf-8"))
    if profile["representation"] not in ("axis_aligned_bounding_block", "union_outer_shells", "source_constructive_surfaces"):
        raise ValueError("Unsupported representation")
    if profile["representation"] == "axis_aligned_bounding_block":
        selection = profile.setdefault("physical_representation_policy", "explicit_body_with_annotation_omissions_v1")
        if selection != "explicit_body_with_annotation_omissions_v1":
            raise ValueError("Unsupported physical representation selection policy")
    if profile["coordinate_mode"] not in ("local_engineering", "synthetic_transform", "ifc_map_conversion", "engineering_with_map_provenance"):
        raise ValueError("Unsupported coordinate mode")
    if profile["coordinate_mode"] == "ifc_map_conversion" and profile["srs_name"] != "auto":
        raise ValueError("Map-conversion CRS must be resolved from IFC metadata")
    if profile["coordinate_mode"] != "ifc_map_conversion" and not profile["srs_name"].startswith("urn:ifc-citygml:crs:"):
        raise ValueError("Pilot output must use an explicit project engineering CRS, not an unverified EPSG CRS")
    if profile["coordinate_mode"] == "engineering_with_map_provenance" and profile["srs_name"] != "urn:ifc-citygml:crs:local-engineering-metres":
        raise ValueError("Engineering-frame preservation requires the explicit local engineering metre CRS")
    transform = profile["transform"]
    values = [*transform["translation_m"], transform["yaw_degrees"], transform["scale"],
              profile["geometry_tolerance_m"]]
    if len(transform["translation_m"]) != 3 or not all(math.isfinite(float(v)) for v in values):
        raise ValueError("Transform must contain three finite translations and finite numeric parameters")
    if transform["scale"] <= 0 or not 1e-9 <= profile["geometry_tolerance_m"] <= 0.01:
        raise ValueError("Scale must be positive; geometry tolerance must be between 1e-9 and 0.01 m")
    if profile["coordinate_mode"] in ("local_engineering", "ifc_map_conversion", "engineering_with_map_provenance") and (
        any(transform["translation_m"]) or transform["yaw_degrees"] != 0 or transform["scale"] != 1
    ):
        raise ValueError("A non-identity transform requires coordinate_mode=synthetic_transform")
    if profile.get("allow_partial", False):
        raise ValueError("Partial export is not implemented; the pilot fails closed on extraction errors")
    return profile


def transform_points(points: np.ndarray, profile: dict) -> np.ndarray:
    if profile["coordinate_mode"] == "ifc_map_conversion":
        matrix = np.array(profile["resolved_affine_matrix"])
        return points @ matrix[:3, :3].T + matrix[:3, 3]
    transform = profile["transform"]
    angle = math.radians(transform["yaw_degrees"])
    cosine, sine = math.cos(angle), math.sin(angle)
    rotation = np.array([[cosine, -sine, 0], [sine, cosine, 0], [0, 0, 1]])
    return points @ rotation.T * transform["scale"] + np.array(transform["translation_m"])
