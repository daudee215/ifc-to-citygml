"""Check evaluation provenance before placing its findings in other artifacts."""
import json
from pathlib import Path

from ifc_citygml.common import ROOT, code_digest, digest


def verified_evaluation():
    path = ROOT / "results/v0_6/semantic_evaluation/index.json"
    evidence = json.loads(path.read_text())
    expected = {"converter_source_sha256": code_digest(),
                "mapping_spec_sha256": digest(ROOT / "docs/SEMANTIC_MAPPING.md"),
                "coordinate_policy_spec_sha256": digest(ROOT / "docs/ENGINEERING_FRAME.md"),
                "audit_source_sha256": digest(ROOT / "scripts/semantic_audit.py"),
                "fixture_author_sha256": digest(ROOT / "scripts/generate_semantic_cases.py"),
                "runner_source_sha256": digest(ROOT / "scripts/run_semantic_evaluation.py")}
    for key, value in expected.items():
        if evidence.get(key) != value:
            raise ValueError(f"Stale semantic evaluation: {key}; rerun scripts/run_semantic_evaluation.py")
    for result in evidence["cases"]:
        for name in ("input", "gml", "links", "expected_annotations"):
            if result.get(name) and digest(Path(result[name])) != result[name + "_sha256"]:
                raise ValueError(f"Semantic evidence changed: {result['case']} {name}")
        if result["audit_source_sha256"] != expected["audit_source_sha256"] or result["mapping_spec_sha256"] != expected["mapping_spec_sha256"]:
            raise ValueError("Semantic case used a different audit/specification")
    return evidence


def verified_block_evaluation():
    evidence = json.loads((ROOT / "results/v0_6/block_evaluation/index.json").read_text())
    expected = {"converter_source_sha256": code_digest(), "audit_source_sha256": digest(ROOT / "scripts/block_audit.py"),
                "membership_audit_source_sha256": digest(ROOT / "scripts/semantic_audit.py"),
                "policy_spec_sha256": digest(ROOT / "docs/BLOCK_REPRESENTATIONS.md")}
    for key, value in expected.items():
        if evidence.get(key) != value:
            raise ValueError("Stale block evaluation: " + key)
    for result in evidence["cases"]:
        for name in ("input", "gml", "links"):
            if digest(Path(result[name])) != result[name + "_sha256"]:
                raise ValueError("Changed block evidence: " + result["case"])
        if result["audit_source_sha256"] != expected["audit_source_sha256"]:
            raise ValueError("Block case audit version mismatch")
    return evidence
