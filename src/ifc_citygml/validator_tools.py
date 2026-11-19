"""Locate, probe and explicitly install the pinned independent validator."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from contextlib import contextmanager
from contextvars import ContextVar
from urllib.request import Request, urlopen
from zipfile import ZipFile

from .common import CHECKOUT_ROOT, digest, write_json

VERSION = "2.7.0"
ARCHIVE_URL = "https://github.com/tudelft3d/val3dity/releases/download/2.7.0/val3dity-win64.zip"
ARCHIVE_SHA256 = "cf8d3f025cd52aafc9ea370296a2430baa4aa39ce44a8b3ba1d8b3a540d8a5a7"
_override = ContextVar("ifc_citygml_validator_override", default=None)


@contextmanager
def validator_override(path: Path | None):
    if path is None:
        yield
        return
    token = _override.set(path)
    try:
        yield
    finally:
        _override.reset(token)


def cache_directory() -> Path:
    override = os.environ.get("IFC_CITYGML_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return base / "ifc-citygml"


def managed_validator_directory() -> Path:
    return cache_directory() / "tools" / "val3dity" / VERSION


def find_validator(explicit: Path | None = None) -> dict:
    requested = explicit or _override.get() or os.environ.get("IFC_CITYGML_VAL3DITY")
    if requested:
        path = Path(requested).expanduser().resolve()
        if not path.is_file():
            return {"status": "unavailable", "reason": f"Explicit validator does not exist: {path}", "executable": str(path)}
        return {"status": "found", "executable": str(path), "origin": "explicit" if explicit or _override.get() else "environment"}
    executable_name = "val3dity.exe" if os.name == "nt" else "val3dity"
    candidates = []
    if CHECKOUT_ROOT:
        candidates.append((CHECKOUT_ROOT / "tools/val3dity" / executable_name, "checkout"))
    candidates.append((managed_validator_directory() / executable_name, "managed_cache"))
    on_path = shutil.which("val3dity")
    if on_path:
        candidates.append((Path(on_path), "PATH"))
    for path, origin in candidates:
        if path.is_file():
            return {"status": "found", "executable": str(path.resolve()), "origin": origin}
    return {"status": "unavailable", "reason": "Independent validator not found; run ifc-citygml setup-validator or set IFC_CITYGML_VAL3DITY",
            "managed_directory": str(managed_validator_directory())}


def validator_environment() -> tuple[dict, dict]:
    environment = os.environ.copy()
    candidates = []
    override = environment.get("VAL3DITY_RUNTIME_DIR")
    if override:
        candidates.append(Path(override))
    git = shutil.which("git")
    if git:
        git_root = Path(git).resolve().parent.parent
        candidates.extend([git_root / "mingw64/bin", git_root / "usr/bin"])
    if os.name == "nt":
        candidates.append(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/mingw64/bin")
    runtime = next((p for p in candidates if (p / "libgcc_s_seh-1.dll").is_file()), None)
    hashes = {}
    if runtime:
        environment["PATH"] = str(runtime) + os.pathsep + environment.get("PATH", "")
        hashes = {p.name: digest(p) for p in (runtime / "libgcc_s_seh-1.dll", runtime / "libwinpthread-1.dll") if p.is_file()}
    return environment, {"runtime_dependency_directory": str(runtime) if runtime else None, "runtime_dependency_hashes": hashes}


def probe_validator(explicit: Path | None = None) -> dict:
    location = find_validator(explicit)
    if location["status"] != "found":
        return location
    executable = Path(location["executable"])
    environment, runtime = validator_environment()
    try:
        manifest_path = executable.parent / "source_manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for item in manifest.get("installed_files", []):
                path = (executable.parent / item["path"]).resolve()
                if not path.is_relative_to(executable.parent.resolve()) or digest(path) != item["sha256"]:
                    raise ValueError(f"Validator cache integrity failed: {item['path']}")
        result = subprocess.run([str(executable), "--version"], capture_output=True, text=True, env=environment, timeout=15)
        match = re.search(r"\bversion:\s*([^\s]+)", result.stdout + result.stderr)
        actual_version = match.group(1) if match else None
        if result.returncode != 0 or actual_version != VERSION:
            return {**location, **runtime, "status": "unavailable", "version": actual_version,
                    "exit_code": result.returncode, "reason": f"Expected runnable val3dity {VERSION}; check runtime dependencies/version",
                    "stderr": result.stderr[-1000:]}
        return {**location, **runtime, "status": "passed", "version": actual_version, "executable_sha256": digest(executable)}
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {**location, **runtime, "status": "unavailable", "reason": str(exc)}


def install_validator(directory: Path | None = None, archive: Path | None = None) -> dict:
    if os.name != "nt":
        raise ValueError("Automatic setup currently provides the pinned Windows build; supply a native 2.7.0 binary with IFC_CITYGML_VAL3DITY on other platforms")
    target = (directory or managed_validator_directory()).expanduser().resolve()
    if archive:
        data = archive.read_bytes()
    else:
        request = Request(ARCHIVE_URL, headers={"User-Agent": "ifc-citygml/0.4"})
        with urlopen(request, timeout=60) as response:
            data = response.read()
    if hashlib.sha256(data).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Validator release archive checksum mismatch; nothing extracted")
    target.mkdir(parents=True, exist_ok=True)
    installed = []

    def extract(content: bytes, depth: int = 0):
        if depth > 2:
            raise ValueError("Unexpected validator archive nesting")
        with ZipFile(io.BytesIO(content)) as source:
            for entry in source.infolist():
                path = (target / entry.filename).resolve()
                if not path.is_relative_to(target):
                    raise ValueError("Unsafe path in validator archive")
                if entry.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                    continue
                payload = source.read(entry)
                if path.suffix.lower() == ".zip":
                    extract(payload, depth + 1)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(payload)
                    installed.append({"path": path.relative_to(target).as_posix(), "sha256": hashlib.sha256(payload).hexdigest()})
    extract(data)
    (target / "release.original.zip").write_bytes(data)
    write_json(target / "source_manifest.json", {"url": ARCHIVE_URL, "version": VERSION, "sha256": ARCHIVE_SHA256,
        "license_source": "https://github.com/tudelft3d/val3dity/blob/main/LICENSE", "installed_files": installed})
    executable = target / "val3dity.exe"
    return {"status": "installed", "directory": str(target), "archive_sha256": ARCHIVE_SHA256,
            "probe": probe_validator(executable)}
