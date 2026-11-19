"""Install a built wheel in a fresh external venv and execute real CLI checks.

No editable install, source PYTHONPATH or system-site-packages is used. The
temporary environment is retained for inspection; summary/logs are copied into
the research results directory. Requires Python 3.13 and network/cache access
for pinned public dependencies and the explicitly invoked validator installer.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from zipfile import ZipFile

import ifcopenshell
import ifcopenshell.guid
import numpy as np
from lxml import etree as ET

from ifc_citygml import __version__
from ifc_citygml.common import ROOT, BUILTIN_PROFILES, code_digest, digest, resource_digest, write_json
from ifc_citygml.pipeline import convert


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path, required=True)
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    output = ROOT / "results" / ("v" + "_".join(__version__.split(".")[:2])) / "packaging"
    output.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="ifc_citygml_wheel_verify_")).resolve()
    if work.is_relative_to(ROOT.resolve()):
        raise RuntimeError("Clean-install verification must run outside the checkout")
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "PIP_TARGET", "PIP_PREFIX", "PIP_USER", "IFC_CITYGML_VAL3DITY"):
        environment.pop(name, None)
    environment["IFC_CITYGML_CACHE_DIR"] = str(work / "managed_cache")
    logs = work / "logs"
    logs.mkdir()
    records = []

    def run(label, command, expected=(0,)):
        start = time.perf_counter()
        result = subprocess.run([str(v) for v in command], cwd=work, env=environment,
                                capture_output=True, text=True, errors="replace", timeout=300)
        (logs / f"{label}.stdout.txt").write_text(result.stdout, encoding="utf-8")
        (logs / f"{label}.stderr.txt").write_text(result.stderr, encoding="utf-8")
        records.append({"stage": label, "exit_code": result.returncode, "seconds": time.perf_counter() - start})
        print(json.dumps(records[-1]), flush=True)
        if result.returncode not in expected:
            raise RuntimeError(f"{label} failed; see {logs}: {result.stderr[-1500:]}")
        return result

    with ZipFile(wheel) as package:
        names = package.namelist()
        schema_files = [n for n in names if n.startswith("ifc_citygml/resources/schemas/vendor/")]
        profiles = [n for n in names if n.startswith("ifc_citygml/resources/profiles/") and n.endswith(".json")]
        if len(schema_files) != 62 or len(profiles) != len(BUILTIN_PROFILES):
            raise RuntimeError("Built wheel does not contain the complete pinned resource set")
    inputs = work / "inputs"
    inputs.mkdir()
    base = inputs / "building_m.ifc"
    shutil.copyfile(ROOT / "data/raw/fixtures/building_m.ifc", base)
    invalid = ifcopenshell.open(str(base))
    for rectangle in invalid.by_type("IfcRectangleProfileDef"):
        rectangle.XDim = 0.0
    invalid.write(str(inputs / "degenerate.ifc"))
    mapped = ifcopenshell.open(str(base))
    metre = mapped.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    crs = mapped.create_entity("IfcProjectedCRS", Name="EPSG:7415", MapUnit=metre)
    mapped.create_entity("IfcMapConversion", SourceCRS=mapped.by_type("IfcGeometricRepresentationContext")[0],
        TargetCRS=crs, Eastings=120000.0, Northings=450000.0, OrthogonalHeight=220.0,
        XAxisAbscissa=0.0, XAxisOrdinate=1.0, Scale=1.0)
    mapped.write(str(inputs / "mapped.ifc"))
    crs.Name = "EPSG:3763"
    mapped.write(str(inputs / "mapped_2d.ifc"))
    annotated = ifcopenshell.open(str(inputs / "mapped_2d.ifc"))
    context = annotated.by_type("IfcGeometricRepresentationContext", include_subtypes=False)[0]
    line = annotated.create_entity("IfcPolyline", Points=[annotated.create_entity("IfcCartesianPoint", Coordinates=p)
        for p in ((10000., 10000., 0.), (20000., 10000., 0.))])
    curves = annotated.create_entity("IfcGeometricCurveSet", Elements=[line])
    annotation = annotated.create_entity("IfcShapeRepresentation", ContextOfItems=context,
        RepresentationIdentifier="Annotation", RepresentationType="GeometricSet", Items=[curves])
    door = annotated.by_type("IfcDoor")[0]
    proxy = annotated.create_entity("IfcBuildingElementProxy", GlobalId=ifcopenshell.guid.new(), OwnerHistory=door.OwnerHistory,
        Name="Annotation-only installation test", ObjectPlacement=door.ObjectPlacement,
        Representation=annotated.create_entity("IfcProductDefinitionShape", Representations=[annotation]))
    contained = annotated.by_type("IfcRelContainedInSpatialStructure")[0]
    contained.RelatedElements = (*contained.RelatedElements, proxy)
    wall = annotated.by_type("IfcWall")[0]
    wall.Representation.Representations = (*wall.Representation.Representations, annotation)
    annotated.write(str(inputs / "annotation_mixed.ifc"))
    annotation_input_sha = digest(inputs / "annotation_mixed.ifc")
    annotation_reference = convert(inputs / "annotation_mixed.ifc", output / "checkout_reference/annotation_mixed.gml", "engineering-block")
    references = {}
    profile_inputs = {name: "building_m.ifc" for name in ("block", "exterior", "source")}
    profile_inputs.update({name: "mapped_2d.ifc" for name in ("engineering-block", "engineering-exterior", "engineering-source")})
    for profile, filename in profile_inputs.items():
        report = convert(inputs / filename, output / "checkout_reference" / f"{profile}.gml", profile)
        references[profile] = report["output_sha256"]
    shutil.copyfile(ROOT / "requirements.lock.txt", work / "constraints.txt")
    run("create_environment", [sys.executable, "-m", "venv", str(work / "venv")])
    python = work / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    cli = [python, "-m", "ifc_citygml.cli"]
    run("install_wheel", [python, "-m", "pip", "install", "--constraint", "constraints.txt", str(wheel)])
    run("pip_check", [python, "-m", "pip", "check"])
    before = run("doctor_before_setup", [*cli, "doctor"], expected=(2,))
    initial = json.loads(before.stdout)
    if initial["installation_mode"] != "installed_package" or initial["status"] != "needs_validator":
        raise RuntimeError("Fresh environment unexpectedly depends on a checkout or pre-existing validator")
    run("setup_validator", [*cli, "setup-validator"])
    checked = run("doctor_after_setup", [*cli, "doctor"])
    doctor = json.loads(checked.stdout)
    if doctor["software"]["ifc-citygml"] != __version__ or doctor["converter_source_sha256"] != code_digest():
        raise RuntimeError("Wheel version/code differs from the tested source")
    if doctor["resources"]["manifest_sha256"] != resource_digest() or doctor["validator"]["origin"] != "managed_cache":
        raise RuntimeError("Wheel resources or validator do not come from their verified installation")
    if Path(doctor["package_directory"]).is_relative_to(ROOT.resolve()):
        raise RuntimeError("Source checkout leaked into fresh-package imports")
    equivalence = {}
    for profile in references:
        run(f"convert_{profile}", [*cli, "convert", "inputs/" + profile_inputs[profile], "--profile", profile, "--output", f"outputs/{profile}.gml"])
        target = work / f"outputs/{profile}.gml"
        report = json.loads(target.with_suffix(".report.json").read_text())
        if digest(target) != references[profile] or report["status"] != "passed":
            raise RuntimeError(f"Wheel conversion differs from checkout: {profile}")
        equivalence[profile] = {"sha256": digest(target), "byte_identical_to_checkout": True,
                                "schema_valid": report["validation"]["schema_valid"]}
        if profile.startswith("engineering-"):
            if report["profile"]["georeferencing"]["operation_applied"] is not False:
                raise RuntimeError("Engineering wheel conversion applied map metadata")
            document = ET.parse(str(target))
            if "has not been applied" not in document.find("{http://www.opengis.net/gml/3.2}description").text:
                raise RuntimeError("Engineering output omits coordinate-frame notice")
    run("strict_source_still_rejects_map_metadata", [*cli, "convert", "inputs/mapped_2d.ifc", "--profile", "source", "--output", "outputs/strict_source.gml"], expected=(2,))
    run("strict_map_still_rejects_2d_crs", [*cli, "convert", "inputs/mapped_2d.ifc", "--profile", "map", "--output", "outputs/strict_map.gml"], expected=(2,))
    run("annotation_mixed_block", [*cli, "convert", "inputs/annotation_mixed.ifc", "--profile", "engineering-block", "--output", "outputs/annotation_mixed.gml"])
    annotation_report = json.loads((work / "outputs/annotation_mixed.report.json").read_text())
    omitted_annotations = [o for o in annotation_report["source_links"][0]["omitted"] if o["reason"].startswith("Annotation-only")]
    if len(omitted_annotations) != 1 or digest(work / "outputs/annotation_mixed.gml") != annotation_reference["output_sha256"]:
        raise RuntimeError("Installed annotation/mixed-body selection differs from checkout")
    if digest(inputs / "annotation_mixed.ifc") != annotation_input_sha:
        raise RuntimeError("Installed conversion changed the source IFC")
    run("validate_installed_output", [*cli, "validate", "outputs/source.gml", "--report", "outputs/validation.json"])
    run("convert_map", [*cli, "convert", "inputs/mapped.ifc", "--profile", "map", "--output", "outputs/map.gml"])
    root = ET.parse(str(work / "outputs/map.gml"))
    values = [np.array([float(v) for v in p.text.split()]).reshape(-1, 3) for p in root.findall(".//{http://www.opengis.net/gml/3.2}posList")]
    points = np.vstack(values)
    np.testing.assert_allclose(points.min(axis=0), [119785, 450105, 233], atol=1e-7, rtol=0)
    np.testing.assert_allclose(points.max(axis=0), [119793, 450117, 239], atol=1e-7, rtol=0)
    write_json(work / "benchmark.json", {"profiles": ["block", "source"], "cases": [
        {"id": "valid", "input": "inputs/building_m.ifc", "provenance": {"kind": "controlled_fixture"}},
        {"id": "degenerate", "input": "inputs/degenerate.ifc", "provenance": {"kind": "intentionally_invalid_geometry"}}]})
    run("benchmark_failures_visible", [*cli, "benchmark", "--manifest", "benchmark.json", "--output", "benchmark"], expected=(2,))
    index = json.loads((work / "benchmark/index.json").read_text())
    if index["completed"] != 2 or index["failed"] != 2 or index["report_base"] != "index_directory":
        raise RuntimeError("Installed benchmark failed to preserve expected failures")
    run("benchmark_explicit_allow_failures", [*cli, "benchmark", "--manifest", "benchmark.json", "--output", "benchmark_allow", "--allow-failures"])
    run("inspect_installed", [*cli, "inspect", "inputs/building_m.ifc", "--report", "outputs/inspection.json"])
    summary = {"status": "passed", "wheel": str(wheel), "wheel_sha256": digest(wheel), "version": __version__,
        "verification_working_directory": str(work), "source_checkout": str(ROOT), "doctor": doctor,
        "schema_files_in_wheel": len(schema_files), "profiles_in_wheel": len(profiles), "conversions": equivalence,
        "map_fixture_bounds_verified": True, "benchmark_expected_failures_preserved": True,
        "annotation_body_policy_verified": True,
        "editable_install_used": False, "source_pythonpath_used": False, "stages": records}
    write_json(output / "CLEAN_INSTALL_VERIFICATION.json", summary)
    shutil.copytree(logs, output / "clean_install_logs", dirs_exist_ok=True)
    (output / "CLEAN_INSTALL_VERIFICATION.md").write_text(
        "# Clean wheel installation verification\n\n"
        f"Verified wheel `{wheel.name}` in a new Python virtual environment at `{work}` outside the source checkout. "
        "No editable installation, source PYTHONPATH or system-site-packages was used.\n\n"
        f"- All 62 pinned schemas and {len(profiles)} profiles are present and pass resource checks.\n"
        "- Doctor detects a missing validator before setup and a verified managed-cache installation afterwards.\n"
        "- Legacy and explicit engineering block/exterior/source outputs are byte-identical to checkout outputs.\n"
        "- Engineering outputs retain unapplied coordinate metadata; strict source/map modes still reject incomplete georeferencing.\n"
        "- Annotation-only products are explicitly omitted and mixed products retain their bodies in an actual installed CLI conversion.\n"
        "- Independent validation and the explicit 3D map fixture pass.\n"
        "- The installed benchmark records two successful and two deliberately failed attempts; default exit is nonzero.\n"
        "- Explicit allow-failures changes the exit policy while retaining failed cases.\n\n"
        "Raw command results and dependency/tool provenance are in the JSON report and accompanying logs. "
        "The external environment is retained for inspection. This verifies the current Windows/Python 3.13 environment, not every platform.\n",
        encoding="utf-8")
    print(json.dumps({"status": "passed", "wheel": wheel.name, "report": str(output / "CLEAN_INSTALL_VERIFICATION.md")}))


if __name__ == "__main__":
    main()
