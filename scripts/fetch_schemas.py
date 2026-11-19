"""Cache the official XSD dependency closure for offline validation.

The upstream bytes are retained unchanged; an lxml resolver maps imports to
this cache at validation time. Manifest hashes pin the exact fetched bytes.
"""
from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ENTRY = "https://schemas.opengis.net/citygml/building/3.0/building.xsd"


def canonical(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported schema URI: {url}")
    return urlunsplit(("https", parts.netloc.lower(), parts.path, "", ""))


def retrieve(url: str) -> tuple[str, bytes, list[str]]:
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": "IFC-CityGML-research/0.1"}), timeout=30) as response:
                data = response.read()
            tree = ET.fromstring(data)
            deps = [canonical(urljoin(url, node.attrib["schemaLocation"]))
                    for node in tree if node.tag in {
                        "{http://www.w3.org/2001/XMLSchema}import",
                        "{http://www.w3.org/2001/XMLSchema}include",
                        "{http://www.w3.org/2001/XMLSchema}redefine",
                    } and "schemaLocation" in node.attrib]
            return url, data, deps
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise RuntimeError("Unreachable")


def main() -> None:
    destination = ROOT / "schemas"
    todo, seen, entries = {ENTRY}, set(), []
    with ThreadPoolExecutor(max_workers=8) as pool:
        while todo:
            batch = sorted(todo - seen)
            todo = set()
            if not batch:
                break
            for url, data, deps in pool.map(retrieve, batch):
                seen.add(url)
                parts = urlsplit(url)
                relative = Path("vendor") / parts.netloc / parts.path.lstrip("/")
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                entries.append({"url": url, "path": relative.as_posix(),
                                "sha256": hashlib.sha256(data).hexdigest()})
                todo.update(set(deps) - seen)
            print(f"Cached {len(seen)} schemas; next batch {len(todo)}", flush=True)
    manifest = {"entry_url": ENTRY, "files": sorted(entries, key=lambda item: item["url"]),
                "terms": "https://www.ogc.org/about-ogc/legal-notices-term-and-conditions/"}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
