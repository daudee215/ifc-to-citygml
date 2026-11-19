"""Manifest-driven benchmark execution usable from any working directory."""
from __future__ import annotations

import json
from pathlib import Path
import re
import time

from .common import BUILTIN_PROFILES, code_digest, digest, profile_path, resource_digest, software_versions, write_json
from .pipeline import ConversionFailure, convert


def _name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value):
        raise ValueError("Case/profile names must be short filesystem-safe identifiers")
    return value


def _optional_digest(path):
    try:
        return digest(path) if path.is_file() else None
    except OSError:
        return None  # The attempt's actual read error remains in its failure record.


def run_benchmark(manifest_path: Path, output_directory: Path, selected_profiles: list[str] | None = None, progress=None) -> dict:
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict) or manifest.get("format_version", 1) != 1:
        raise ValueError("Unsupported benchmark manifest format")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Benchmark manifest requires a nonempty cases list")
    if any(not isinstance(c, dict) or not isinstance(c.get("input"), str) or not c["input"].strip() for c in cases):
        raise ValueError("Every benchmark case requires a nonempty input path")
    case_names = [_name(c["id"]) for c in cases]
    if len(case_names) != len({name.casefold() for name in case_names}):
        raise ValueError("Duplicate benchmark case identifier")
    profiles = {}
    entries = manifest.get("profiles", ["block", "exterior", "source"])
    if not isinstance(entries, list):
        raise ValueError("Benchmark profiles must be a list")
    for item in entries:
        if isinstance(item, str):
            name, reference = _name(item), item
            if reference not in BUILTIN_PROFILES:
                raise ValueError(f"Unknown built-in profile: {reference}")
        else:
            name = _name(item["name"])
            if "builtin" in item and "config" not in item:
                reference = item["builtin"]
                if reference not in BUILTIN_PROFILES:
                    raise ValueError(f"Unknown built-in profile: {reference}")
            elif "config" in item and "builtin" not in item:
                reference = (manifest_path.parent / item["config"]).resolve()
            else:
                raise ValueError("Profile entry requires exactly one of builtin or config")
        if name in profiles:
            raise ValueError("Duplicate benchmark profile identifier")
        profiles[name] = reference
    if selected_profiles:
        if len(selected_profiles) != len(set(selected_profiles)) or any(n not in profiles for n in selected_profiles):
            raise ValueError("Selected benchmark profiles must be unique names declared by the manifest")
        profiles = {name: profiles[name] for name in selected_profiles}
    if not profiles:
        raise ValueError("No benchmark profiles selected")
    filenames = [f"{name}_{mode}".casefold() for name in case_names for mode in profiles]
    if len(filenames) != len(set(filenames)):
        raise ValueError("Case/profile combinations collide as output filenames")
    output = output_directory.resolve()
    output.mkdir(parents=True, exist_ok=True)
    index = {"format_version": 1, "report_base": "index_directory", "status": "running", "manifest": str(manifest_path),
             "manifest_sha256": digest(manifest_path), "software": software_versions(),
             "converter_source_sha256": code_digest(), "bundled_resources_sha256": resource_digest(), "cases": []}
    index_path = output / "index.json"
    write_json(index_path, index)
    for case in cases:
        source = (manifest_path.parent / case["input"]).resolve()
        for mode, reference in profiles.items():
            target = output / f"{case['id']}_{mode}.gml"
            selected_profile = profile_path(reference)
            record = {"case": case["id"], "mode": mode, "input": str(source), "provenance": case.get("provenance"),
                      "requested_profile": str(reference),
                      "profile_file_sha256": _optional_digest(selected_profile)}
            started = time.perf_counter()
            try:
                report = convert(source, target, reference)
                record.update({"status": report["status"], "report": target.with_suffix(".report.json").name,
                               "input_sha256": report["extraction"]["input_sha256"], "output_sha256": report["output_sha256"],
                               "quality_warnings": report["validation"].get("quality_warnings", [])})
            except Exception as exc:
                failure_path = target.with_suffix(".failure.json")
                failure = {"status": "failed", "output_written": False, "input": str(source),
                           "input_sha256": _optional_digest(source),
                           "converter_source_sha256": code_digest(), "error_class": type(exc).__name__, "error": str(exc),
                           "requested_profile": str(reference), "profile_file_sha256": record["profile_file_sha256"],
                           "elapsed_seconds": time.perf_counter() - started}
                write_json(failure_path, failure)
                report_path = target.with_suffix(".report.json") if isinstance(exc, ConversionFailure) else failure_path
                record.update({"status": "failed", "error": str(exc), "report": report_path.name,
                               "failure_report": failure_path.name, "input_sha256": failure["input_sha256"]})
            record["wall_seconds"] = time.perf_counter() - started
            index["cases"].append(record)
            write_json(index_path, index)
            if progress:
                progress(record)
    index["attempts"] = len(index["cases"])
    index["completed"] = sum(c["status"] == "passed" for c in index["cases"])
    index["failed"] = index["attempts"] - index["completed"]
    index["status"] = "completed_with_failures" if index["failed"] else "completed"
    write_json(index_path, index)
    return index


def report_path(index_file: Path, index: dict, case: dict, checkout_root: Path | None = None) -> Path:
    """Resolve both portable indices and the historical checkout-only format."""
    path = Path(case["report"])
    if path.is_absolute():
        return path
    if index.get("report_base") == "index_directory":
        return index_file.parent / path
    if checkout_root is None:
        raise ValueError("Legacy benchmark index requires its original checkout root")
    return checkout_root / path
