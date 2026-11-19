"""Verify executed browser DOM against the combined benchmark record."""
import argparse
import json
from pathlib import Path
import sys
from urllib.parse import unquote

from lxml import html

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ifc_citygml.common import ROOT, digest, write_json
from scripts.research_runs import research_index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dom", type=Path, required=True)
    args = parser.parse_args()
    page = ROOT / "results/v0_6/review/index.html"
    if args.dom.stat().st_mtime < page.stat().st_mtime:
        raise ValueError("Rendered browser DOM predates the generated page")
    root = html.fromstring(args.dom.read_text(encoding="utf-8"))
    assert root.get("data-ready") == "true", "Browser JavaScript did not become ready"
    _, combined = research_index()
    rows = root.xpath('//tbody[@id="cases"]/tr')
    assert len(rows) == combined["attempts"]
    for row, case in zip(rows, combined["cases"]):
        cells = row.findall("td")
        assert len(cells) == 7
        assert [c.text_content() for c in cells[:3]] == [case["case"], case["mode"], case["status"]]
        if case["status"] == "failed":
            assert cells[5].text_content().strip(), "Failed attempt has no visible reason"
        assert cells[6].find("a") is not None
    local_links = 0
    for link in root.xpath('//a[@href]'):
        href = link.get("href")
        if href.startswith(("#", "http:", "https:")):
            continue
        target = (page.parent / unquote(href.split("#")[0])).resolve()
        assert target.is_file(), "Broken local link: " + str(target)
        local_links += 1
    result = {"status": "passed", "html_sha256": digest(page), "rendered_dom_sha256": digest(args.dom),
              "benchmark_rows": len(rows), "completed": combined["completed"], "failed": combined["failed"],
              "local_links_verified": local_links}
    write_json(ROOT / "results/v0_6/review/render_verification.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
