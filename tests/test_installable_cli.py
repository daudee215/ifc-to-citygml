import json
from pathlib import Path
import shutil

import pytest

from ifc_citygml import common
from ifc_citygml.cli import main
from ifc_citygml.validator_tools import find_validator, install_validator, probe_validator, validator_override
from scripts.generate_fixtures import make_fixture


def test_bundled_resources_match_pinned_checkout_inputs():
    checked = common.verify_resources()
    assert checked["schema_count"] == 62
    assert checked["profile_count"] == 7
    canonical = json.loads((common.ROOT / "schemas/manifest.json").read_text())
    for item in canonical["files"]:
        assert common.digest(common.SCHEMA_DIR / item["path"]) == item["sha256"]
    for alias, name in common.BUILTIN_PROFILES.items():
        assert common.load_profile(alias) == common.load_profile(common.ROOT / "config" / name)


def test_builtin_profile_detects_resource_tampering(tmp_path, monkeypatch):
    resources = tmp_path / "resources"
    shutil.copytree(common.RESOURCE_DIR, resources)
    selected = resources / "profiles/source_surfaces_profile.json"
    selected.write_text(selected.read_text() + "\n")
    monkeypatch.setattr(common, "RESOURCE_DIR", resources)
    with pytest.raises(ValueError, match="integrity"):
        common.load_profile("source")


def test_builtin_conversion_works_from_an_unrelated_directory(tmp_path, monkeypatch):
    source = tmp_path / "input.ifc"
    make_fixture(source)
    working = tmp_path / "unrelated"
    working.mkdir()
    monkeypatch.chdir(working)
    assert main(["convert", str(source), "--profile", "source", "--output", "result.gml"]) == 0
    report = json.loads(Path("result.report.json").read_text())
    assert report["bundled_resources_sha256"] == common.resource_digest()
    assert report["extraction"]["serialization_fidelity"]["exact_transformed_float64_rings"]


def test_benchmark_resolves_inputs_and_custom_profiles_relative_to_manifest(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    make_fixture(data / "building.ifc")
    (data / "source.json").write_text(json.dumps(common.load_profile("source")))
    manifest = data / "cases.json"
    manifest.write_text(json.dumps({"profiles": [{"name": "custom", "config": "source.json"}],
        "cases": [{"id": "one", "input": "building.ifc", "provenance": {"kind": "controlled_fixture"}}]}))
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)
    assert main(["benchmark", "--manifest", str(manifest), "--output", "bench"]) == 0
    index = json.loads(Path("bench/index.json").read_text())
    assert index["report_base"] == "index_directory"
    assert index["completed"] == 1 and index["failed"] == 0
    report = json.loads((Path("bench") / index["cases"][0]["report"]).read_text())
    assert report["validation"]["independent_surface_validation"] == "passed"
    assert index["cases"][0]["provenance"]["kind"] == "controlled_fixture"


def test_benchmark_failure_is_nonzero_visible_and_does_not_reference_stale_success(tmp_path):
    source = tmp_path / "building.ifc"
    make_fixture(source)
    manifest = tmp_path / "cases.json"
    manifest.write_text(json.dumps({"profiles": ["block"], "cases": [
        {"id": "valid", "input": "building.ifc"}, {"id": "missing", "input": "absent.ifc"}]}))
    output = tmp_path / "benchmark"
    output.mkdir()
    stale = output / "missing_block.report.json"
    stale.write_text('{"status":"passed","output_written":true}')
    arguments = ["benchmark", "--manifest", str(manifest), "--output", str(output)]
    assert main(arguments) == 2
    index = json.loads((output / "index.json").read_text())
    assert index["status"] == "completed_with_failures"
    assert index["completed"] == 1 and index["failed"] == 1
    failure = index["cases"][1]
    assert failure["report"] == "missing_block.failure.json"
    current = json.loads((output / failure["report"]).read_text())
    assert current["status"] == "failed" and current["output_written"] is False
    assert json.loads(stale.read_text())["status"] == "passed"  # Historical file is not cited by the new index.
    assert main([*arguments, "--allow-failures"]) == 0
    assert json.loads((output / "index.json").read_text())["failed"] == 1


def test_benchmark_rejects_filename_collisions_before_running(tmp_path):
    manifest = tmp_path / "cases.json"
    manifest.write_text(json.dumps({"cases": [{"id": "Case", "input": "a.ifc"}, {"id": "case", "input": "b.ifc"}]}))
    target = tmp_path / "out"
    assert main(["benchmark", "--manifest", str(manifest), "--output", str(target)]) == 2
    assert not target.exists()


def test_invalid_case_input_is_rejected_before_a_running_index_is_written(tmp_path):
    manifest = tmp_path / "invalid.json"
    manifest.write_text(json.dumps({"cases": [{"id": "invalid", "input": None}]}))
    target = tmp_path / "out"
    assert main(["benchmark", "--manifest", str(manifest), "--output", str(target)]) == 2
    assert not (target / "index.json").exists()


def test_explicit_missing_validator_does_not_fall_back_and_context_is_restored(tmp_path):
    baseline = find_validator()
    missing = tmp_path / "missing-validator.exe"
    with validator_override(missing):
        result = probe_validator()
        assert result["status"] == "unavailable" and str(missing) in result["reason"]
    assert find_validator() == baseline
    assert main(["doctor", "--validator", str(missing)]) == 2
    assert find_validator() == baseline


def test_bad_validator_archive_fails_before_extracting(tmp_path):
    if __import__("os").name != "nt":
        pytest.skip("Pinned automatic installer is Windows-specific")
    archive = tmp_path / "bad.zip"
    archive.write_bytes(b"not the pinned archive")
    target = tmp_path / "install"
    with pytest.raises(ValueError, match="checksum"):
        install_validator(target, archive)
    assert not target.exists()
