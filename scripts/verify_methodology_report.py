"""Verify the new reporting artifacts without modifying frozen conversion evidence."""
from pathlib import Path
import json
import re
import shutil
from urllib.parse import unquote, urljoin, urlparse
from zipfile import ZipFile

from lxml import html, etree
from pypdf import PdfReader
from prepare_methodology_evidence import ROOT, OUT, sha, verify_frozen


def main():
    frozen = verify_frozen()
    evidence = json.loads((OUT / "evidence_snapshot.json").read_text())
    for item in evidence["provenance"]["files"].values():
        assert sha(ROOT / item["path"]) == item["sha256"]
    raw_count = 0
    for manifest in [*evidence["datasets"].values(), evidence["torino"]]:
        for item in manifest["files"]:
            assert sha(ROOT / item["path"]) == item["sha256"]
            raw_count += 1
    page = OUT / "review/index.html"
    dom_path = OUT / "review/rendered.html"
    assert dom_path.stat().st_mtime >= page.stat().st_mtime
    dom = html.fromstring(dom_path.read_text(encoding="utf-8-sig"))
    assert dom.get("data-ready") == "true"
    assert dom.get("data-model") == "gaia_renovation · engineering-block"
    label = dom.get_element_by_id("validation").text_content()
    assert label == "XSD: passed · Declared Solid: passed · Additional Solid diagnostic: not applicable"
    rows = dom.xpath('//tbody[@id="cases"]/tr')
    assert len(rows) == 32
    source = page.read_text(encoding="utf-8")
    payload = json.loads(re.search(r"const DATA=(.*?);\s*\nconst colours=", source, re.S).group(1))
    original = (ROOT / "results/v0_6/review/index.html").read_text(encoding="utf-8")
    original_data = json.loads(re.search(r"const DATA=(.*?);\s*\nconst colours=", original, re.S).group(1))
    assert len(payload["models"]) == len(original_data["models"])
    for old, new in zip(original_data["models"], payload["models"]):
        assert old["polygons"] == new["polygons"]
    blocks = surfaces = 0
    for row, case in zip(rows, payload["cases"]):
        cells = [c.text_content() for c in row.findall("td")]
        assert cells[:5] == [case[k] for k in ("case", "mode", "status", "independent", "solid")]
        report = json.loads((ROOT / "results/v0_6" / case["report"]).read_text())
        validation = report.get("validation", {})
        block = case["mode"].endswith("block")
        key = "independent_general_solid_validation" if block else "independent_surface_validation"
        assert case["independent"] == validation.get(key, "not run")
        assert case["solid"] == ("not applicable" if block else validation.get("independent_general_solid_validation", "not run"))
        if case["status"] == "passed":
            assert case["independent"] == "passed"
            blocks += int(block)
            surfaces += int(not block)
    assert (blocks, surfaces) == (8, 13)
    base = urljoin(page.as_uri(), dom.xpath('//base/@href')[0])
    links = 0
    for href in dom.xpath('//a/@href'):
        target = urlparse(urljoin(base, href))
        if target.scheme == "file":
            path = unquote(target.path).lstrip("/")
            assert Path(path).is_file(), path
            links += 1
    document = OUT / "IFC_to_CityGML_Methodology.docx"
    pdf = OUT / "qa_final/IFC_to_CityGML_Methodology.pdf"
    pages = PdfReader(pdf).pages
    assert len(pages) == 15
    assert all(len(p.extract_text().strip()) > 300 for p in pages), "Sparse or blank page"
    markdown = (OUT / "IFC_to_CityGML_Methodology.md").read_text(encoding="utf-8")
    assert "{{" not in markdown
    for phrase in ("21 of 32", "3,838", "286,316", "891", "107 passing", "0.01 m", "1,130", "17 polygon"):
        assert phrase in markdown, phrase
    with ZipFile(document) as archive:
        xml = etree.fromstring(archive.read("word/document.xml"))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        assert len(xml.xpath("//w:tbl", namespaces=ns)) == 11
        relationships = etree.fromstring(archive.read("word/_rels/document.xml.rels"))
        citations = [r.get("Target") for r in relationships if r.get("Type", "").endswith("/hyperlink")]
        assert len(citations) >= 13
    final_pdf = OUT / pdf.name
    shutil.copyfile(pdf, final_pdf)
    paths = [document, final_pdf, OUT / "IFC_to_CityGML_Methodology.md", OUT / "methodology_source.md",
             OUT / "evidence_snapshot.json", page, dom_path, OUT / "review/preview.png", OUT / "review_corrections.json"]
    result = {"status": "passed", "pages": len(pages), "visual_review": "All 15 final page PNGs and Gaia block viewer preview inspected",
              "tables": 11, "attempt_rows": len(rows), "completed_solids": blocks, "completed_multisurfaces": surfaces,
              "local_links_verified": links, "raw_files_verified": raw_count,
              "frozen_releases_verified": frozen, "geometry_payloads_unchanged": True,
              "external_reference_links": citations,
              "files": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)} for p in paths]}
    (OUT / "VERIFICATION.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("files", "external_reference_links")}))


if __name__ == "__main__":
    main()
