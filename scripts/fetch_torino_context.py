"""Retrieve a bounded, attributed Torino/Moncalieri GIS context sample.

No BIM identity is assigned to these footprints and no synthetic IFC is presented
as a real local building. All service responses and request URLs are retained.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
BDTRE = "https://geoservices.csi.it/ms/wfs/bdtre/rp-01/bdtrewfs/bdtre_aggr"
ARPA = "https://webgis.arpa.piemonte.it/server/rest/services/rischi_naturali/evento_alluvionale_2016/MapServer/8"
BBOX = [394000, 4981000, 396000, 4983000]


def get(url):
    try:
        with urlopen(Request(url, headers={"User-Agent": "IFC-CityGML-research/0.2"}), timeout=60) as response:
            return response.read()
    except HTTPError as exc:
        raise RuntimeError(f"Service returned HTTP {exc.code}: {exc.read().decode(errors='replace')[:1600]}") from None


def main():
    directory = ROOT / "data/raw/torino_context"
    directory.mkdir(parents=True, exist_ok=True)
    records = []

    def save(name, url):
        data = get(url)
        (directory / name).write_bytes(data)
        records.append({"path": str((directory / name).relative_to(ROOT)), "url": url,
                        "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        return data

    caps = save("bdtre_capabilities.xml", BDTRE + "?" + urlencode({"SERVICE": "WFS", "REQUEST": "GetCapabilities", "VERSION": "1.0.0"}))
    tree = ET.fromstring(caps)
    names = tree.xpath("//*[local-name()='FeatureType']/*[local-name()='Name']/text()")
    building_type = next((name for name in names if name.split(":")[-1] == "cs_edi"), None)
    if building_type is None:
        raise ValueError("Expected BDTRE building aggregate type is not advertised")
    pages = []
    def retrieve_buildings(bounds, depth=0):
        params = {"SERVICE": "WFS", "VERSION": "1.0.0", "REQUEST": "GetFeature", "TYPENAME": building_type,
                  "BBOX": ",".join(map(str, bounds)) + ",EPSG:32632", "SRSNAME": "EPSG:32632", "MAXFEATURES": 1000,
                  "OUTPUTFORMAT": "geojson"}
        name = f"buildings_response_{len(pages)}.geojson"
        page = json.loads(save(name, BDTRE + "?" + urlencode(params)).decode("latin-1"))
        pages.append(name)
        features = page.get("features", [])
        if len(features) < 1000:
            return features
        if depth >= 8:
            raise ValueError("Building service still capped after eight spatial subdivisions")
        x0, y0, x1, y1 = bounds
        if x1 - x0 >= y1 - y0:
            mid = (x0 + x1) / 2
            children = ([x0, y0, mid, y1], [mid, y0, x1, y1])
        else:
            mid = (y0 + y1) / 2
            children = ([x0, y0, x1, mid], [x0, mid, x1, y1])
        return [feature for child in children for feature in retrieve_buildings(child, depth + 1)]
    features = retrieve_buildings(BBOX)
    unique = {feature.get("id") or feature.get("properties", {}).get("uuid") or json.dumps(feature, sort_keys=True): feature for feature in features}
    buildings = {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:32632"}},
                 "features": list(unique.values())}
    (directory / "buildings.geojson").write_text(json.dumps(buildings, ensure_ascii=False), encoding="utf-8")
    arpa_params = {"where": "1=1", "geometry": ",".join(map(str, BBOX)), "geometryType": "esriGeometryEnvelope",
                   "inSR": 32632, "outSR": 32632, "spatialRel": "esriSpatialRelIntersects", "outFields": "*",
                   "returnGeometry": "true", "f": "geojson"}
    flood_raw = save("event_2016_extent.geojson", ARPA + "/query?" + urlencode(arpa_params))
    flood = json.loads(flood_raw)
    if flood.get("exceededTransferLimit") or "error" in flood:
        raise ValueError("Incomplete or failed ARPA event response")
    save("arpa_layer_metadata.json", ARPA + "?f=pjson")
    bdt_terms = get("https://relazione.ambiente.piemonte.it/2025/la-base-cartografica-regionale-bdtre")
    (directory / "bdtre_source_terms.html").write_bytes(bdt_terms)
    arpa_terms = get("https://webgis.arpa.piemonte.it/geoportalserver_arpa/catalog/search/resource/details.page?uuid=ARLPA_TO%3A07.03.33-D_2017-11-23-16%3A30")
    (directory / "arpa_source_terms.html").write_bytes(arpa_terms)
    manifest = {"retrieved_utc": datetime.now(timezone.utc).isoformat(), "bbox": BBOX, "crs": "EPSG:32632",
                "domain_area_km2": 4, "domain_status": "Operational 2 km x 2 km context sample, not final research boundary",
                "buildings_count": len(buildings.get("features", [])), "event_polygon_count": len(flood.get("features", [])),
                "bdtre_layer": "cs_edi (Cassoni edilizi)",
                "bdtre_terms": "Regional BDTRE source describes CC BY 2.5 transitioning to 4.0; preserve attribution and verify edition-specific terms before redistribution",
                "arpa_terms": "CC BY 2.5 Italia per event metadata; separate map-service conditions retained",
                "attribution": ["Regione Piemonte — BDTRE", "Arpa Piemonte, Regione Piemonte, CNR IRPI — Evento alluvionale novembre 2016"],
                "building_request_pages": pages, "completeness": "Spatially subdivided until every accepted leaf response has fewer than 1000 features; stable feature-ID deduplication",
                "not_ifc_source": True, "files": records}
    (directory / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"buildings": manifest["buildings_count"], "event_polygons": manifest["event_polygon_count"], "bbox": BBOX}))


if __name__ == "__main__":
    main()
