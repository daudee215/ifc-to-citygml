"""Deliver a curated larger figure edition and all 404 controlled attempts."""
import csv
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from zipfile import ZipFile,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/publication_figures_004';EXP=ROOT/'results/experiments/frame_alignment_004'
rows=json.loads((EXP/'index.json').read_text())['cases'];stress=[]
for row in rows:
    r={k:row[k] for k in ['case','arm','shape_family','contents_yaw_degrees','building_yaw_degrees','units','status','expected_topology','all_guards_passed','report']}
    r['mode']='exterior';r['cohort']='oblique_controls';r['input_sha256']=row['input_sha256'];r['output_sha256']=row.get('output_sha256','')
    for k,v in row.get('mesh_audit',{}).items():r['mesh_'+k]=v
    for precision in ['raw','measurement_1nm','measurement_1um']:
        for k,v in row.get('metrics',{}).get(precision,{}).items():r[precision+'_'+k]=v
    for k,v in row.get('metrics',{}).get('volume',{}).items():r['volume_'+k]=v
    stress.append(r)
combined=list(csv.DictReader((ROOT/'reports/local_frame_003/combined_controlled_340.csv').open(encoding='utf-8')))+stress
assert len(combined)==404 and len(stress)==64
for name,data in [('stress_comparison_64.csv',stress),('complete_controlled_404.csv',combined)]:
    with (OUT/name).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in data for k in r)));writer.writeheader();writer.writerows(data)
figures=sorted((OUT/'figures').glob('*.svg'));assert len(figures)==9
captions=['# IFC to CityGML figure captions','']
index=[]
for path in figures:
    svg=ET.parse(path);texts=[x.text or '' for x in svg.iter('{http://www.w3.org/2000/svg}text')]
    captions.extend(['## '+path.stem[:2]+' '+texts[1],texts[2],'',texts[-2],texts[-1],''])
    index.append({'svg':path.name,'png':path.with_suffix('.png').name,'title':texts[1],'subtitle':texts[2],'source':texts[-2],'scope_note':texts[-1],
                  'canvas_pixels':[1600,1000],'png_pixels':[3200,2000],'font':'Palatino Linotype','rendering':'Native SVG text and paths; real exported models rendered with WebGL depth testing'})
(OUT/'Figure_Captions.md').write_text('\n'.join(captions),encoding='utf-8')
(OUT/'figure_index.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
intro='''<section class="intro"><div class="kicker">IFC to CityGML / Research figure edition / 3 November 2026</div>
<h1>Geometry robustness and urban context</h1><p class="subtitle">Nine larger Palatino plates supported by preserved conversions and a prospective stress experiment</p>
<div class="columns"><article><h2>What the figures make visible</h2><p>Actual exported building geometry now carries the comparison. The Duplex roof and openings are readable at a larger scale. Component colours reveal disconnected courtyard shells whose footprint area still appears accurate.</p>
<p>Area and volume matrices use one shared colour scale. Separate figures distinguish validity from topology, raw from precision adjusted measurement, and source failures from union failures. The Torino and Moncalieri map retains real projected geometry and historical event labels.</p>
<h2>A stronger methodological result</h2><p>The new study rotates source geometry within the building frame. This tests a limitation absent from the earlier aligned controls. Both methods use the same 1 µm union grid and validator snapping.</p>
<p>The experiment adds 32 IFC inputs and 64 attempts. Across four studies, the project now retains 404 controlled attempts on 112 related analytical inputs.</p></article>
<article><h2>Successful validation does not settle fidelity</h2><p>The local frame method passes the surface and component Solid checks in all 32 oblique cases, but meets all reference and mesh guards in only 16. The world frame baseline validates 28 of 32 and meets all guards in 14.</p>
<p>This narrows the earlier result: all 80 aligned local frame controls still pass, but that success does not generalise to oblique contents. The adapter remains experimental and the installed converter is unchanged.</p>
<h2>Scope of the urban evidence</h2><p>Torino open data provide a separate context rather than surveyed IFC placement. The map contains building aggregates and November 2016 inundation polygons. It establishes neither flood depth nor current flood probability.</p>
<p>Public benchmark failures remain visible. All 129 checkout tests pass; source hashes, failed candidates and previous releases are preserved.</p></article></div>
<footer>Figure quality and acceptance criteria are checked separately · SVG text remains editable · Full measurements accompany the figure pack</footer></section>
<section class="intro"><div class="kicker">Research methodology / Frame alignment study 004</div>
<h1>Stress design and interpretation</h1><p class="subtitle">A fixed policy comparison recorded before generating the new controls</p>
<div class="columns"><article><h2>Inputs and analytical reference</h2><p>Four forms—L shape, U shape, courtyard and setback—receive contents rotations of 7° or 23°, independent of building placement rotations of 0° or 37°. Metre and millimetre versions give 32 inputs, each converted by the world frame baseline and unchanged building frame adapter.</p>
<p>The reference rotates declared nonoverlapping prisms by the sum of both angles and retains their known translation. Four additional tests independently check composed world coordinates against freshly extracted source corners.</p>
<h2>Acceptance criteria</h2><p>In addition to geometry checks, each result is tested against reference footprint IoU ≥ 0.999999, discrete boundary distance ≤ 5 µm and absolute relative volume error below 10⁻⁶. The footprint comparison uses the recorded 1 nm measurement grid, while raw results remain available.</p>
<p>Mesh diagnostics require one component, Euler characteristic 0 for the courtyard or 2 otherwise, and no edges shorter than 1 µm. Equal Euler characteristic alone does not prove topology equivalence.</p></article>
<article><h2>Granularity explains the apparent contradiction</h2><p>The stronger Solid diagnostic tests retained components as volumes. Separate closed components may validate while failing to form the intended connected building shell. All 32 local frame stress cases pass those geometry checks; sixteen still fail reference topology correspondence.</p>
<p>For the courtyard at contents rotation 7° and building placement 37°, the baseline has four components and Euler sum 8. The local frame has two components and Euler sum 4. The intended shell has one component and Euler characteristic 0.</p>
<h2>How the edition should be used</h2><p>The nine plates are a curated reading set. Earlier atlases remain preserved. Every plate identifies its evidence and limits; the CSV contains all 404 controlled attempts, including failed rows. External file checks remain a separate evidence stratum.</p>
<p>These are parameterised massing designs rather than independent real buildings. No geographic or hydraulic accuracy follows from the numerical agreement.</p></article></div>
<footer>Detailed definitions and results: Methods_and_Results.md · Captions and figure index included · No post outcome tolerance tuning</footer></section>'''
style='''@page{size:16.6666667in 10.4166667in;margin:0}*{box-sizing:border-box}body{margin:0;font-family:"Palatino Linotype",Palatino,serif;color:#1d3034}section{width:1600px;height:1000px;overflow:hidden;break-after:page}section:last-child{break-after:auto}svg{display:block;width:1600px;height:1000px}.intro{padding:48px 80px;position:relative}.kicker{font-size:20px;color:#65716f}h1{font-size:46px;font-weight:400;color:#101e21;margin:31px 0 15px}.subtitle{font-size:24px;color:#65716f;margin:0 0 43px}.columns{display:grid;grid-template-columns:1fr 1fr;gap:90px}h2{font-size:29px;font-weight:400;color:#101e21;margin:16px 0 17px}p{font-size:21px;line-height:1.32;margin:0 0 18px}footer{position:absolute;bottom:38px;left:80px;font-size:20px;color:#65716f}'''
page=OUT/'Research_Figure_Edition.html';page.write_text('<!doctype html><html><head><meta charset="utf-8"><title>IFC to CityGML research figure edition</title><style>'+style+'</style></head><body>'+intro+''.join('<section>'+p.read_text(encoding='utf-8')+'</section>' for p in figures)+'</body></html>',encoding='utf-8')
subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless','--disable-gpu','--no-pdf-header-footer',f'--print-to-pdf={OUT/"Research_Figure_Edition_Palatino.pdf"}',page.as_uri()],capture_output=True,check=True)
with ZipFile(OUT/'Editable_Figures_and_Evidence.zip','w',ZIP_DEFLATED) as z:
    for path in [*sorted((OUT/'figures').glob('*')),OUT/'Methods_and_Results.md',OUT/'Figure_Captions.md',OUT/'figure_index.json',OUT/'geometry_sources.json',OUT/'stress_comparison_64.csv',OUT/'complete_controlled_404.csv']:
        z.write(path,path.relative_to(OUT))
print('Created eleven page figure edition, nine SVG and PNG plates, and complete evidence pack')

