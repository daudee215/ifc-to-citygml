from __future__ import annotations

import hashlib
import time
from pathlib import Path
from lxml import etree as ET

from .common import load_profile, software_versions, write_json, code_digest, resource_digest
from .extract import extract_blocks
from .envelope import extract_envelopes
from .citygml_writer import create_document
from .exterior_writer import create_exterior_document
from .validation import validate_document
from .georeferencing import prepare_profile, ENGINEERING_MODE, ENGINEERING_NOTICE
from .citygml_writer import NS, tag
from .source_surfaces import extract_source_surfaces, create_source_document


class ConversionFailure(RuntimeError):
    pass


def convert(input_path: Path, output_path: Path, config_path: Path | str | None = None) -> dict:
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Input and output paths must differ")
    start = time.perf_counter()
    profile = prepare_profile(load_profile(config_path), input_path)
    extractors = {"union_outer_shells": extract_envelopes, "axis_aligned_bounding_block": extract_blocks,
                  "source_constructive_surfaces": extract_source_surfaces}
    writers = {"union_outer_shells": create_exterior_document, "axis_aligned_bounding_block": create_document,
               "source_constructive_surfaces": create_source_document}
    extraction = extractors[profile["representation"]](input_path, profile)
    report_path = output_path.with_suffix(".report.json")
    report = {"profile": profile, "software": software_versions(), "converter_source_sha256": code_digest(),
              "bundled_resources_sha256": resource_digest(), "extraction": extraction,
              "output": str(output_path.resolve()), "status": "failed", "output_written": False}
    if extraction["status"] != "passed":
        report["elapsed_seconds"] = time.perf_counter() - start
        write_json(report_path, report)
        raise ConversionFailure(f"Extraction failed; see {report_path}")
    data, source_links = writers[profile["representation"]](extraction, profile)
    if profile["coordinate_mode"] == ENGINEERING_MODE:
        root = ET.fromstring(data)
        description = root.find("gml:description", NS)
        description.text = (description.text or "") + " " + ENGINEERING_NOTICE
        data = ET.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")
        for link in source_links:
            link["coordinate_provenance"] = profile["georeferencing"]
    validation = validate_document(data, profile["geometry_tolerance_m"])
    if profile["coordinate_mode"] == ENGINEERING_MODE:
        validation.setdefault("quality_warnings", []).append(ENGINEERING_NOTICE)
    report.update({"validation": validation, "source_links": source_links,
                   "elapsed_seconds": time.perf_counter() - start})
    if validation["status"] != "passed":
        write_json(report_path, report)
        raise ConversionFailure(f"Output validation failed; see {report_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    report.update({"status": "passed", "output_written": True,
                   "output_sha256": hashlib.sha256(data).hexdigest()})
    write_json(report_path, report)
    write_json(output_path.with_suffix(".source_links.json"), source_links)
    return report
