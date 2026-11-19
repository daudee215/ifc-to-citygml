"""Reproduce synthetic IFC-to-CityGML experiments and their measured report."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import ifcopenshell
import ifcopenshell.validate
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.generate_fixtures import main as generate
from ifc_citygml.common import digest, load_profile, software_versions, write_json
from ifc_citygml.extract import inspect_ifc
from ifc_citygml.pipeline import convert

ROOT = Path(__file__).resolve().parents[1]


def main():
    generate()
    raw = ROOT / "data" / "raw" / "fixtures"
    output = ROOT / "results" / "citygml"
    cases = []
    for source in sorted(raw.glob("*.ifc")):
        expected = json.loads(source.with_suffix(".expected.json").read_text())
        logger = ifcopenshell.validate.json_logger()
        ifcopenshell.validate.validate(ifcopenshell.open(str(source)), logger, express_rules=True)
        issues = [{"level": item["level"], "message": item["message"]} for item in logger.statements]
        write_json(ROOT / "results" / "inspection" / (source.stem + ".json"),
                   {**inspect_ifc(source), "ifc_validation_issues": issues})
        if issues:
            raise RuntimeError(f"Input fixture failed IFC validation: {source.name}")
        report = convert(source, output / (source.stem + ".gml"))
        measured = report["validation"]["geometry"][0]
        np.testing.assert_allclose(measured["bounds_m"], expected["expected_ifc_world_bounds_m"], atol=1e-7, rtol=0)
        if abs(measured["volume_m3"] - expected["expected_bounding_volume_m3"]) > 1e-7:
            raise RuntimeError("Unexpected bounding-block volume")
        cases.append({"case": source.stem, "ifc_schema": expected["ifc_schema"],
                      "source_unit": expected["length_unit"], "status": report["status"],
                      "schema_valid": report["validation"]["schema_valid"],
                      "ifc_validation_issue_count": len(issues), "bounds_m": measured["bounds_m"],
                      "volume_m3": measured["volume_m3"], "input_sha256": digest(source),
                      "output_sha256": report["output_sha256"], "runtime_seconds": report["elapsed_seconds"],
                      "physical_geometry_contributors": len(report["source_links"][0]["contributors"])})
    synthetic = load_profile()
    synthetic.update({"profile_id": "citygml3-synthetic-placement-0.1", "coordinate_mode": "synthetic_transform",
                      "srs_name": "urn:ifc-citygml:crs:synthetic-placement-metres"})
    synthetic["transform"] = {"translation_m": [395000, 4980000, 220], "yaw_degrees": 30, "scale": 1}
    config = ROOT / "config" / "synthetic_placement.json"
    write_json(config, synthetic)
    synthetic_report = convert(raw / "building_m.ifc", output / "building_synthetic_placement.gml", config)
    summary = {"status": "passed", "provenance_type": "synthetic_fixtures_only",
               "software": software_versions(), "cases": cases,
               "synthetic_placement_status": synthetic_report["status"],
               "independent_general_solid_validation": "not_run",
               "geographic_accuracy_validation": "not_run; no real building locations used",
               "limitations": ["Only derived bounding blocks are exported", "No thematic surfaces or openings preserved yet",
                               "Geometry checks are limited to convex six-face shells",
                               "No measured Torino buildings or flood results"]}
    write_json(ROOT / "results" / "pilot_summary.json", summary)
    rows = ["| Case | IFC | Source units | XSD | Block volume (m³) | Runtime (s) |",
            "|---|---|---|---|---:|---:|"]
    for case in cases:
        rows.append(f"| {case['case']} | {case['ifc_schema']} | {case['source_unit']} | pass | {case['volume_m3']:.6f} | {case['runtime_seconds']:.3f} |")
    text = """# Pilot results

Executed synthetic conversion experiments. Run timestamps are deliberately omitted
from the GML to keep geometry outputs deterministic. Runtimes are measurements of
this run on the local workstation, not a performance benchmark.

""" + "\n".join(rows) + """

Each input passes IfcOpenShell attribute and EXPRESS-rule validation. Each output
passes offline validation against the cached official CityGML 3.0 schemas and the
project's bounded convex-shell checks. Each expected bounding volume is 576 m³;
this is the derived block volume, not the sum of wall/slab material volumes.

The baseline nested placements produce bounds [105, 207, 13] to [117, 215, 19] m.
A 90-degree source rotation produces bounds [85, 205, 13] to [93, 217, 19] m.
The additional synthetic-placement output applies a known 30-degree rotation and
translation once. It has no asserted real-world building location or EPSG CRS.

Source links retain building identity and identify seven contributing physical
elements. Element-level shape, thematic surfaces, openings and interiors are
explicitly recorded as omitted from these block outputs.

Independent general-solid validation, real-building conversion evaluation and
geographic checkpoint validation remain outstanding. The project validator checks
the pilot convex shells; it does not establish general CityGML conformance.

Reproduce with `.venv/Scripts/python.exe scripts/run_pilot.py` from the project root.
Detailed measurements and hashes are in `pilot_summary.json`; per-building reports
and source links are beside the GML files in `citygml/`.
"""
    (ROOT / "results" / "PILOT_RESULTS.md").write_text(text, encoding="utf-8")
    print(json.dumps({"status": "passed", "fixture_cases": len(cases), "gml_outputs": len(cases) + 1,
                      "report": str(ROOT / "results" / "PILOT_RESULTS.md")}, indent=2))


if __name__ == "__main__":
    main()
