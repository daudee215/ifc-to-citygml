"""Create a self-contained local inspection artifact from actual GML outputs.

The 3D pane uses exported polygons. The map pane shows genuine GIS context only;
it does not place benchmark buildings on real local footprints.
"""
from pathlib import Path
import hashlib
import json
import sys
import os

from lxml import etree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ifc_citygml.common import ROOT
from ifc_citygml.citygml_writer import NS
from ifc_citygml.benchmark import report_path
from scripts.evaluation_evidence import verified_evaluation, verified_block_evaluation
from scripts.research_runs import research_index


HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>IFC → CityGML · Conversion review</title>
<style>
:root{color-scheme:light;--ink:#183344;--muted:#607483;--line:#dce5ea;--accent:#087e84}*{box-sizing:border-box}body{margin:0;background:#eef3f5;color:var(--ink);font:15px system-ui,sans-serif}header{background:#132e40;color:#fff;padding:28px 4vw}header p{color:#bed1db;max-width:970px;line-height:1.6;margin-bottom:0}h1{font-size:29px;margin:5px 0}h2{font-size:19px;margin:0 0 15px}.eyebrow{font-size:12px;letter-spacing:2px;color:#8ed9d2}main{max-width:1500px;margin:auto;padding:25px 3vw}.grid{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(290px,1fr);gap:20px}.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:22px;margin-bottom:20px;overflow:hidden}.toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:14px}select,button{border:1px solid #b9ccd4;border-radius:6px;padding:9px;background:#fff;color:var(--ink);font:inherit}button{cursor:pointer}.badge{padding:5px 9px;background:#dff1ed;color:#146c57;border-radius:5px;font-size:12px}.warn{padding:12px;background:#fff1d8;border-left:3px solid #d58a1f;line-height:1.5}.small{font-size:12px;color:var(--muted);line-height:1.6}canvas{display:block;width:100%;touch-action:none;background:#f7fafb;border-radius:6px}#model{height:430px;cursor:grab}#map{height:330px}.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;margin:14px 0}.swatch{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:5px}dl{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:18px 0}dt{font-size:12px;color:var(--muted)}dd{font-size:22px;margin:4px 0 0}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:11px 8px;border-bottom:1px solid var(--line);text-align:left}th{color:var(--muted);font-weight:500}a{color:var(--accent)}code{font-size:12px}.good{color:#12745e}.bad{color:#b13e30}.note{line-height:1.65}.footer{padding:5px 0 24px;color:var(--muted);font-size:12px}@media(max-width:900px){.grid{grid-template-columns:1fr}#model{height:350px}}
</style></head><body><header><div class="eyebrow">REPRODUCIBLE CONVERSION RESEARCH · LOCAL REVIEW</div><h1>IFC → CityGML</h1><p>Inspect the geometry actually exported, compare a bounding block with source-linked thematic surfaces, and keep validation outcomes visible. Torino–Moncalieri GIS data provide a separate urban context.</p></header>
<main><div class="grid"><section class="card"><h2>Exported building geometry</h2><div class="toolbar"><select id="dataset" aria-label="Converted model"></select><button id="reset">Reset view</button><label><input id="edges" type="checkbox"> Triangle edges</label></div><canvas id="model" aria-label="Interactive exported building geometry"></canvas><div class="legend" id="legend"></div><p class="small">Drag to rotate · scroll to zoom. Local model coordinates in metres. Colours show conversion classifications; semantic accuracy still needs independent annotation.</p><div id="warning" class="warn"></div><p><a id="gml" href="#">Open CityGML</a> · <a id="report" href="#">Open validation and provenance report</a></p></section>
<aside><section class="card"><h2>Selected output</h2><span class="badge" id="profile"></span><dl id="stats"></dl><p class="note" id="validation"></p><p class="small" id="provenance"></p></section><section class="card"><h2>What the checks establish</h2><p class="note">XSD checks validate the XML structure. Independent geometry checks operate on the exact exported rings through a verified adapter. A valid MultiSurface can still fail a stronger closed-Solid check.</p><p class="small">No benchmark model is asserted to be an actual Torino building. IFC metadata transformation does not establish geographic accuracy without independent checkpoints.</p></section></aside></div>
<section class="card"><h2>Torino–Moncalieri: genuine open GIS context</h2><div class="toolbar"><span id="contextCount"></span><label><input id="event" type="checkbox"> Show mapped November 2016 event polygons</label></div><canvas id="map" aria-label="Local building outlines and optional historical flood evidence"></canvas><p class="small">Regione Piemonte — BDTRE building aggregates. Arpa Piemonte / Regione Piemonte / CNR IRPI — November 2016 event evidence. The operational sample is a 2 × 2 km rectangle in EPSG:32632. Event polygons are historical evidence, not water-depth estimates or a current risk forecast. IFC benchmarks are not placed on these footprints.</p></section>
<section class="card"><h2>Benchmark execution record</h2><p class="small">Failures stay in the denominator. The four generated fixtures test controlled cases; Duplex and Clinic are independent open benchmark projects. These six cases do not establish general conversion accuracy.</p><table><thead><tr><th>Case</th><th>Representation</th><th>Conversion</th><th>Independent surfaces</th><th>Closed-Solid diagnostic</th></tr></thead><tbody id="cases"></tbody></table></section><div class="footer">Self-contained artifact generated from local outputs and source manifests. No external scripts or basemap services are required.</div></main>
<script>const DATA=__DATA__;
const colours={Block:'#97b6c7',WallSurface:'#d1dce3',RoofSurface:'#2c9995',GroundSurface:'#73877a',DoorSurface:'#dd9549',WindowSurface:'#6eade0',OuterFloorSurface:'#a59acb',OuterCeilingSurface:'#9babb5',IfcWall:'#d1dce3',IfcWallStandardCase:'#d1dce3',IfcSlab:'#a59acb',IfcRoof:'#2c9995',IfcDoor:'#dd9549',IfcWindow:'#6eade0',IfcBeam:'#8799ad',IfcColumn:'#839c89',IfcStair:'#aa9d83',IfcStairFlight:'#aa9d83'};
const canvas=document.getElementById('model'),ctx=canvas.getContext('2d');let selected=0,yaw=-.65,pitch=.65,zoom=1,drag=null;
const menu=document.getElementById('dataset');DATA.models.forEach((m,i)=>{const o=document.createElement('option');o.value=i;o.textContent=m.label;menu.append(o)});
function dimensions(c){const r=c.getBoundingClientRect(),d=Math.min(devicePixelRatio||1,2);c.width=r.width*d;c.height=r.height*d;const x=c.getContext('2d');x.setTransform(d,0,0,d,0,0);return[r.width,r.height,x]}
function draw(){if(!DATA.models.length)return;const m=DATA.models[selected],[w,h]=dimensions(canvas);ctx.clearRect(0,0,w,h);let all=m.polygons.flatMap(p=>p.points),low=[Infinity,Infinity,Infinity],high=[-Infinity,-Infinity,-Infinity];all.forEach(p=>p.forEach((v,i)=>{low[i]=Math.min(low[i],v);high[i]=Math.max(high[i],v)}));const centre=low.map((v,i)=>(v+high[i])/2);function rawProject(p){let[x,y,z]=p.map((v,i)=>v-centre[i]),a=x*Math.cos(yaw)-y*Math.sin(yaw),b=x*Math.sin(yaw)+y*Math.cos(yaw);return[a,b*Math.sin(pitch)-z*Math.cos(pitch),b*Math.cos(pitch)+z*Math.sin(pitch)]}let lo=[Infinity,Infinity],hi=[-Infinity,-Infinity];for(const p of all){const q=rawProject(p);for(let i=0;i<2;i++){lo[i]=Math.min(lo[i],q[i]);hi[i]=Math.max(hi[i],q[i])}}const scale=Math.min((w-55)/(hi[0]-lo[0]||1),(h-55)/(hi[1]-lo[1]||1))*zoom,mid=lo.map((v,i)=>(v+hi[i])/2);
function project(p){const q=rawProject(p);return[w/2+(q[0]-mid[0])*scale,h/2+(q[1]-mid[1])*scale,q[2]]}
const polys=m.polygons.map(p=>{const q=p.points.map(project);return{q,kind:p.kind,depth:q.reduce((a,p)=>a+p[2],0)/q.length}}).sort((a,b)=>a.depth-b.depth);for(const p of polys){ctx.beginPath();p.q.forEach((q,i)=>i?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1]));ctx.closePath();ctx.fillStyle=colours[p.kind]||'#c6cbd0';ctx.fill();if(document.getElementById('edges').checked){ctx.strokeStyle='rgba(20,43,55,.28)';ctx.lineWidth=.5;ctx.stroke()}}ctx.fillStyle='#607483';ctx.font='12px system-ui';ctx.fillText('Geometry read from exported GML',15,h-15)}
function choose(){selected=+menu.value;const m=DATA.models[selected];document.documentElement.dataset.model=m.label;yaw=-.65;pitch=.65;zoom=1;document.getElementById('profile').textContent=m.representation;const stats=document.getElementById('stats');stats.replaceChildren();for(const[label,value]of[['Exported polygons',m.polygons.length],['Mapped features',m.featureCount],['Source schema',m.schema],['Runtime, seconds',m.seconds.toFixed(2)]]){let c=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;c.append(dt,dd);stats.append(c)}document.getElementById('validation').textContent='XSD: '+m.xsd+' · Independent declared geometry: '+m.independent+' · Closed-Solid diagnostic: '+m.solid;document.getElementById('provenance').textContent=m.provenance;document.getElementById('warning').textContent=m.warning||'No closed-Solid warning for this output. Semantic classes remain rule-derived; this is not a flood prediction.';document.getElementById('gml').href=m.gml;document.getElementById('report').href=m.report;const legend=document.getElementById('legend');legend.replaceChildren();for(const k of new Set(m.polygons.map(p=>p.kind))){let el=document.createElement('span'),s=document.createElement('span');s.className='swatch';s.style.background=colours[k]||'#ccc';el.append(s,document.createTextNode(k));legend.append(el)}draw()}
menu.onchange=choose;document.getElementById('edges').onchange=draw;document.getElementById('reset').onclick=choose;canvas.onpointerdown=e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId)};canvas.onpointerup=()=>drag=null;canvas.onpointercancel=()=>drag=null;canvas.onpointermove=e=>{if(!drag)return;yaw+=(e.clientX-drag[0])*.008;pitch=Math.max(.05,Math.min(1.5,pitch+(e.clientY-drag[1])*.006));drag=[e.clientX,e.clientY];draw()};canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.3,Math.min(6,zoom*Math.exp(-e.deltaY*.001)));draw()},{passive:false});
function drawMap(){const c=document.getElementById('map'),[w,h,x]=dimensions(c),b=DATA.context.bbox,scale=Math.min((w-30)/(b[2]-b[0]),(h-30)/(b[3]-b[1])),ox=(w-(b[2]-b[0])*scale)/2,oy=(h-(b[3]-b[1])*scale)/2;x.clearRect(0,0,w,h);const px=p=>[ox+(p[0]-b[0])*scale,h-oy-(p[1]-b[1])*scale];x.save();x.beginPath();x.rect(ox,oy,(b[2]-b[0])*scale,(b[3]-b[1])*scale);x.clip();function geo(g,fill,stroke){let polys=g.type==='Polygon'?[g.coordinates]:g.type==='MultiPolygon'?g.coordinates:[];for(const poly of polys){x.beginPath();for(const ring of poly)ring.forEach((p,i)=>{let q=px(p);i?x.lineTo(...q):x.moveTo(...q)});x.closePath();x.fillStyle=fill;x.fill('evenodd');if(stroke){x.strokeStyle=stroke;x.lineWidth=.5;x.stroke()}}}if(document.getElementById('event').checked)for(const f of DATA.context.flood.features)geo(f.geometry,'#b7dcea','#65a9c0');for(const f of DATA.context.buildings.features)geo(f.geometry,'#647d8c','#fff');x.restore();x.strokeStyle='#a6bbc5';x.strokeRect(ox,oy,(b[2]-b[0])*scale,(b[3]-b[1])*scale);x.fillStyle='#47616f';x.font='12px system-ui';x.fillText('N ↑',w-40,20);x.fillRect(ox+12,h-oy-18,200*scale,3);x.fillText('200 m',ox+12,h-oy-24)}
document.getElementById('contextCount').textContent=DATA.context.buildings.features.length+' building outlines · '+DATA.context.flood.features.length+' event polygons';document.getElementById('event').onchange=drawMap;for(const c of DATA.cases){const row=document.createElement('tr');for(const value of[c.case,c.mode,c.status,c.independent,c.solid]){const cell=document.createElement('td');cell.textContent=value;if(value==='failed')cell.className='bad';if(value==='passed')cell.className='good';row.append(cell)}document.getElementById('cases').append(row)}addEventListener('resize',()=>{draw();drawMap()});const requestedModel=new URLSearchParams(location.search).get('model');menu.value=Math.max(0,DATA.models.findIndex(m=>requestedModel?m.label.replace(' · ','-')===requestedModel:m.label==='duplex · source'));choose();drawMap();window.__viewerReady=true;document.documentElement.dataset.ready='true';
</script></body></html>'''


def main():
    index_path, index = research_index()
    target = ROOT / "results/v0_6/review/index.html"
    evaluation = verified_evaluation()
    block_evaluation = verified_block_evaluation()
    block_cases = {r["case"]: r for r in block_evaluation["cases"]}
    block_rows = "".join(f"<tr><td>{r['case']}</td><td>{r['status']}</td><td>{b['physical_contributors']}</td><td>{b['omitted']}</td><td>{b['annotation_only_omissions']}</td><td>{b['xml_max_corner_error_m']:.3g}</td></tr>" for r in block_evaluation["cases"] for b in r["buildings"])
    block_section = '<section class="card"><h2>Physical block selection audit</h2><p class="small">Body geometry contributes to the box; pure annotations are explicitly omitted. Mixed products retain their bodies. Invalid physical geometry still fails. The box bounds selected source geometry; its volume is not net building volume.</p><table><thead><tr><th>Case</th><th>Audit</th><th>Contributors</th><th>Omitted</th><th>Annotation-only</th><th>XML corner error, m</th></tr></thead><tbody>' + block_rows + '</tbody></table><p><a href="../block_evaluation/EVALUATION.md">Open block audit</a> · <a href="../../../docs/BLOCK_REPRESENTATIONS.md">Representation policy</a></p></section>'
    audit_cases = {r["case"]: r for r in evaluation["cases"]}
    semantic_rows = "".join(f"<tr><td>{r['case']}</td><td>{r['status']}</td><td>{r['selected_features']}</td><td>{r['triangles_checked']}</td><td>{len(r['omissions'])}</td><td>{len(r['issues'])}</td></tr>" for r in evaluation["cases"])
    semantic_section = '<section class="card" id="semantic-evaluation"><h2>Source mapping and provenance audit</h2><p class="small">A separate implementation reads original IFC relationships, actual CityGML and provenance. Controlled expectations are authored separately. These checks measure preservation of source information; real-building structural and exterior accuracy still require expert annotation.</p><table><thead><tr><th>Case</th><th>Audit</th><th>Elements</th><th>Triangles</th><th>Omissions</th><th>Mismatches</th></tr></thead><tbody>' + semantic_rows + '</tbody></table><p><a href="../semantic_evaluation/EVALUATION.md">Open measured evaluation</a> · <a href="../../docs/SEMANTIC_MAPPING.md">Mapping specification and limits</a></p></section>'
    models, cases = [], []
    for case in index["cases"]:
        path = report_path(index_path, index, case, ROOT)
        report = json.loads(path.read_text()) if path.exists() else {}
        validation = report.get("validation", {})
        independent = validation.get("independent_surface_validation", "not run")
        solid = validation.get("independent_general_solid_validation", "not run")
        cases.append({**case, "independent": independent, "solid": solid,
                      "detail": report.get("error", "Source extraction/geometry validation failed; see report." if case["status"] == "failed" else ""),
                      "reportHref": "../" + case["report"].replace("\\", "/")})
        if report.get("output_written") is not True or case["case"] not in ("fixture_m", "duplex", "clinic", "gaia_renovation", "digitalhub"):
            continue
        output = Path(report["output"])
        if hashlib.sha256(output.read_bytes()).hexdigest() != report["output_sha256"]:
            raise ValueError("Cannot preview output with mismatched report hash")
        root = ET.fromstring(output.read_bytes())
        polygons = []
        for polygon in root.findall(".//gml:Polygon", NS):
            positions = polygon.find("./gml:exterior/gml:LinearRing/gml:posList", NS)
            numbers = [float(v) for v in positions.text.split()]
            points = [numbers[i:i + 3] for i in range(0, len(numbers) - 3, 3)]
            kind = "Block"
            for parent in polygon.iterancestors():
                if ET.QName(parent).namespace == "http://www.opengis.net/citygml/construction/3.0":
                    kind = ET.QName(parent).localname
                    if kind in ("Door", "Window"):
                        kind = "Ifc" + kind
                    break
                if parent.tag == "{" + NS["bldg"] + "}BuildingConstructiveElement":
                    code = parent.find("bldg:class", NS)
                    kind = code.text if code is not None else "ConstructiveElement"
                    break
            polygons.append({"points": points, "kind": kind})
        semantic = audit_cases.get(case["case"]) if case["mode"].endswith("source") else None
        semantic_note = (f" Separate source audit: {semantic['status']}; {semantic['selected_features']} elements, {semantic['triangles_checked']} exact triangles, {len(semantic['omissions'])} explicit omissions, {len(semantic['issues'])} mismatches." if semantic else "")
        block_result = block_cases.get(case["case"]) if case["mode"].endswith("block") else None
        if block_result:
            b = block_result["buildings"][0]
            semantic_note += f" Block audit: {block_result['status']}; {b['physical_contributors']} physical contributors, {b['annotation_only_omissions']} annotation-only omissions, {len(block_result['issues'])} mismatches."
        models.append({"label": case["case"] + " · " + case["mode"], "representation": report["profile"]["representation"],
            "polygons": polygons, "schema": report["extraction"]["ifc_schema"], "xsd": "passed" if validation["schema_valid"] else "failed",
            "independent": independent, "solid": solid, "seconds": report["elapsed_seconds"],
            "featureCount": sum(len(l.get("contributors", [])) if case["mode"].endswith("block") else len(l.get("surface_links", [])) + len(l.get("element_links", [])) for l in report["source_links"]),
            "featureLabel": "Physical contributors" if case["mode"].endswith("block") else "Mapped features",
            "warning": " ".join(validation.get("quality_warnings", [])),
            "provenance": ("Generated controlled fixture" if case["case"].startswith("fixture") else str((case.get("provenance") or {}).get("attribution", "External building benchmark")) + ". " + str((case.get("provenance") or {}).get("physical_reality_status", "Not asserted to be a Torino building."))) + semantic_note,
            "gml": os.path.relpath(output, target.parent).replace("\\", "/"), "report": os.path.relpath(path, target.parent).replace("\\", "/")})
    folder = ROOT / "data/raw/torino_context"
    context = {"bbox": [394000, 4981000, 396000, 4983000],
               "buildings": json.loads((folder / "buildings.geojson").read_text(encoding="utf-8")),
               "flood": json.loads((folder / "event_2016_extent.geojson").read_text(encoding="utf-8"))}
    data = json.dumps({"models": models, "cases": cases, "context": context}, ensure_ascii=True).replace("<", "\\u003c")
    target.parent.mkdir(parents=True, exist_ok=True)
    page = HTML.replace("__DATA__", data).replace('<section class="card"><h2>Torino–Moncalieri:', block_section + semantic_section + '<section class="card"><h2>Torino–Moncalieri:')
    page = page.replace("['Mapped features',m.featureCount]", "[m.featureLabel||'Mapped features',m.featureCount]")
    page = page.replace('These six cases do not establish general conversion accuracy.', 'The IFC4 extension adds CHEK Gaia renovation and the fictional DigitalHub design. Strict-profile coordinate failures remain visible. Separate engineering profiles retain unapplied metadata and expose geometry failures. <a href="../IFC4_BENCHMARK_FINDINGS.md">Open IFC4 findings and source provenance</a>. These cases do not establish general conversion accuracy.')
    page = page.replace('href="../../docs/', 'href="../../../docs/')
    page = page.replace('<th>Closed-Solid diagnostic</th>', '<th>Closed-Solid diagnostic</th><th>Failure reason</th><th>Record</th>')
    page = page.replace('<h2>Benchmark execution record</h2>', '<h2 id="execution-record">Benchmark execution record</h2>')
    page = page.replace('[c.case,c.mode,c.status,c.independent,c.solid]', '[c.case,c.mode,c.status,c.independent,c.solid,c.detail]')
    page = page.replace("document.getElementById('cases').append(row)", "const recordCell=document.createElement('td'),recordLink=document.createElement('a');recordLink.textContent='Report';recordLink.href=c.reportHref;recordCell.append(recordLink);row.append(recordCell);document.getElementById('cases').append(row)")
    target.write_text(page, encoding="utf-8")
    print(json.dumps({"viewer": str(target), "models": len(models), "benchmark_cases": len(cases)}))


if __name__ == "__main__":
    main()

