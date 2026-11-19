from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .common import write_json
from .extract import inspect_ifc
from .pipeline import convert
from .validation import validate_document
from . import __version__
from .common import BUILTIN_PROFILES
from .benchmark import run_benchmark
from .diagnostics import doctor
from .validator_tools import install_validator, validator_override


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Traceable IFC-to-CityGML 3.0 building conversion")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Inspect schema, units, hierarchy and georeferencing metadata")
    inspect.add_argument("input", type=Path)
    inspect.add_argument("--report", type=Path)
    converter = commands.add_parser("convert", help="Convert with a block, envelope or source-preserving profile")
    converter.add_argument("input", type=Path)
    converter.add_argument("--output", type=Path, required=True)
    profile = converter.add_mutually_exclusive_group()
    profile.add_argument("--config", type=Path, help="Custom JSON profile")
    profile.add_argument("--profile", choices=BUILTIN_PROFILES, help="Bundled profile (default: block)")
    converter.add_argument("--validator", type=Path, help="Explicit val3dity executable for this invocation")
    validator = commands.add_parser("validate", help="Validate XML, references and declared geometry")
    validator.add_argument("input", type=Path)
    validator.add_argument("--report", type=Path)
    validator.add_argument("--validator", type=Path)
    diagnostics = commands.add_parser("doctor", help="Check installed resources, profiles and independent validator")
    diagnostics.add_argument("--validator", type=Path)
    setup = commands.add_parser("setup-validator", help="Explicitly install the pinned Windows validator in a managed cache")
    setup.add_argument("--directory", type=Path)
    setup.add_argument("--archive", type=Path, help="Verified original release archive for offline setup")
    benchmark = commands.add_parser("benchmark", help="Execute a case/profile matrix from a JSON manifest")
    benchmark.add_argument("--manifest", type=Path, required=True)
    benchmark.add_argument("--output", type=Path, required=True)
    benchmark.add_argument("--profiles", nargs="+", help="Select profile names declared by the manifest")
    benchmark.add_argument("--allow-failures", action="store_true", help="Return zero after a complete benchmark even if cases fail; failures remain recorded")
    benchmark.add_argument("--validator", type=Path)
    args = parser.parse_args(argv)
    try:
        with validator_override(getattr(args, "validator", None)):
            return execute(args)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def execute(args) -> int:
    if args.command == "doctor":
        result = doctor()
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "passed" else 2
    if args.command == "setup-validator":
        result = install_validator(args.directory, args.archive)
        print(json.dumps(result, indent=2))
        return 0 if result["probe"]["status"] == "passed" else 2
    if args.command == "benchmark":
        def progress(case):
            print(json.dumps({"case": case["case"], "mode": case["mode"], "status": case["status"]}), file=sys.stderr, flush=True)
        result = run_benchmark(args.manifest, args.output, args.profiles, progress)
        print(json.dumps({"status": result["status"], "attempts": result["attempts"], "completed": result["completed"],
                          "failed": result["failed"], "index": str((args.output / "index.json").resolve())}))
        return 0 if not result["failed"] or args.allow_failures else 2
    if args.command == "inspect":
        result = inspect_ifc(args.input)
    elif args.command == "convert":
        result = convert(args.input, args.output, args.config or args.profile)
        print(json.dumps({"status": result["status"], "output": result["output"],
                          "buildings": len(result["source_links"]), "schema_valid": result["validation"]["schema_valid"],
                          "representation": result["profile"]["representation"],
                          "independent_solid_validation": result["validation"].get("independent_general_solid_validation"),
                          "quality_warnings": result["validation"].get("quality_warnings", [])}))
        return 0
    else:
        result = validate_document(args.input.read_bytes())
    if args.report:
        write_json(args.report, result)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result.get("status", "passed") == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())

