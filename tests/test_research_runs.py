import json

import pytest

from scripts import research_runs


def write_run(root, directory, case, status="passed", code="current"):
    folder = root / "results/v0_6" / directory
    folder.mkdir(parents=True)
    (folder / "index.json").write_text(json.dumps({"format_version": 1, "report_base": "index_directory",
        "status": "completed" if status == "passed" else "completed_with_failures", "converter_source_sha256": code,
        "cases": [{"case": case, "mode": "source", "status": status, "report": case + ".report.json"}]}))


def test_combined_research_keeps_failures_and_resolves_each_original_report(tmp_path, monkeypatch):
    monkeypatch.setattr(research_runs, "ROOT", tmp_path)
    monkeypatch.setattr(research_runs, "RUNS", ("benchmark_run", "benchmark_ifc4"))
    monkeypatch.setattr(research_runs, "code_digest", lambda: "current")
    write_run(tmp_path, "benchmark_run", "original")
    write_run(tmp_path, "benchmark_ifc4", "extension", "failed")
    original_bytes = (tmp_path / "results/v0_6/benchmark_run/index.json").read_bytes()
    path, result = research_runs.research_index()
    assert path == tmp_path / "results/v0_6/research_index.json"
    assert result["attempts"] == 2 and result["completed"] == 1 and result["failed"] == 1
    assert result["status"] == "completed_with_failures"
    assert result["cases"][1]["report"].replace("\\", "/") == "benchmark_ifc4/extension.report.json"
    assert (tmp_path / "results/v0_6/benchmark_run/index.json").read_bytes() == original_bytes


@pytest.mark.parametrize("problem", ["duplicate", "stale"])
def test_combining_research_rejects_ambiguous_or_stale_evidence(tmp_path, monkeypatch, problem):
    monkeypatch.setattr(research_runs, "ROOT", tmp_path)
    monkeypatch.setattr(research_runs, "RUNS", ("benchmark_run", "benchmark_ifc4"))
    monkeypatch.setattr(research_runs, "code_digest", lambda: "current")
    write_run(tmp_path, "benchmark_run", "original")
    write_run(tmp_path, "benchmark_ifc4", "original" if problem == "duplicate" else "extension", code="old" if problem == "stale" else "current")
    with pytest.raises(ValueError):
        research_runs.research_index()
