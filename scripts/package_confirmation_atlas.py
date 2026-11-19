"""Package editable figures and a searchable Palatino research atlas."""
import csv
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/shape_fidelity_002'
D=json.loads((OUT/'plot_data.json').read_text())
records=[]
for arm,key in [('baseline','baseline'),('candidate','candidate')]:
    for r in D[key]:
        row={k:r[k] for k in ['case','mode','shape_family','yaw_degrees','units','status']};row['arm']=arm;row['report']=r['report']
        m=r.get('metrics',{})
        for precision in ['raw','measurement_1nm','measurement_1um']:
            for k,v in m.get(precision,{}).items():row[precision+'_'+k]=v
        for k,v in m.get('volume',{}).items():row['volume_'+k]=v
        records.append(row)
with (OUT/'metrics_240.csv').open('w',newline='',encoding='utf-8') as f:
    writer=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in records for k in r)));writer.writeheader();writer.writerows(records)
intro='''<section class="intro"><div class="kicker">Research update / 3 November 2026</div>
<h1>IFC to CityGML conversion fidelity</h1><p class="subtitle">Expanded methods and results with ten research figures</p>
<div class="columns"><article><h2>What the expanded study establishes</h2>
<p>The study now contains 60 controlled IFC inputs and 240 conversion attempts. It separates successful conversion from faithful representation using independent analytical footprints and volumes.</p>
<p>All 60 bounding blocks validate. Their largest footprint increase is 203.0%, while the largest volume increase is 233.3%. The unrotated setback matches the reference footprint but adds 60% to the volume.</p>
<p>These outcomes support evaluating area, volume and topology separately. A valid output can still alter a building substantially.</p>
<h2>How the evidence is organised</h2><p>Figures 1–5 present the controlled design and geometric changes. Figures 6–8 compare validation and measurement policies. Figures 9–10 retain the earlier numerical diagnostic and external benchmark evidence as separate strata.</p>
</article><article><h2>The candidate does not support adoption</h2>
<p>A finer exterior union grid increases successful conversions from 52 to 54 of 60. The matched comparison records 50 retained passes, four resolved failures, two new failures and four retained failures.</p>
<p>The candidate resolves the tested courtyard failures but introduces U shape failures at 45 degrees. It fails the recorded no regression hypothesis. The production default remains unchanged.</p>
<h2>What the results cover</h2><p>The five massing forms, six orientations and two units are related analytical controls. They do not represent 60 independently sampled buildings. Additional angles were specified after study 001 and before study 002 execution.</p>
<p>Torino remains the intended urban context. No geographic accuracy, flood depth or hydraulic result is inferred from these controls.</p></article></div><footer>Preserved v0.6 converter · 120 passing tests · Protocols and every failed attempt retained</footer></section>
<section class="intro"><div class="kicker">Research methodology / Controlled geometry extension</div>
<h1>Measurements and reproducibility</h1><p class="subtitle">Separate representation error, numerical sensitivity and declared geometry validity</p>
<div class="columns"><article><h2>Experimental comparisons</h2>
<p>Rectangle, L shape, U shape, courtyard and setback forms are evaluated at 0, 15, 30, 45, 60 and 75 degrees in metres and millimetres. Each input is converted to a bounding block, union derived exterior and source preserving surfaces.</p>
<p>The 180 baseline attempts include the earlier 90 plus 90 additional attempts. Sixty experimental exterior attempts compare a 0.1 µm union grid with the 1 µm default, holding validator snapping at 1 µm.</p>
<h2>Analytical references</h2><p>Reference footprints come from declared prism dimensions and rigid placements. Volumes sum nonoverlapping component prisms. Exported rings provide the measured geometry; a local origin stabilises signed volume integration.</p>
<p>Volume is reported for blocks and exteriors with a passing stronger Solid diagnostic. Per feature source solids are not treated as one aggregate envelope.</p>
</article><article><h2>Acceptance and sensitivity</h2>
<p>Surface footprint comparisons require intersection over union ≥ 0.999999 and discrete boundary Hausdorff distance ≤ 5 µm. Study 002 uses a 1 nm grid on derived footprints and references; raw values and a 1 µm topology probe remain visible.</p>
<p>All 112 completed baseline surface cases and all 54 completed candidate cases meet the 1 nm comparison thresholds. This is conditional on completion: failed conversions remain in every attempt denominator.</p>
<h2>Audit trail and limits</h2><p>Input and output hashes, runner hashes, software versions, protocols, validator parameters and rejected candidate GML are retained. The CSV contains all 240 attempts, including blank fidelity values for failed outputs.</p>
<p>Schema validity, declared MultiSurface validity, additional Solid diagnostics and source correspondence are distinct checks. None alone establishes real building semantic accuracy or surveyed geographic accuracy.</p>
</article></div><footer>Detailed methods and exact source paths accompany this atlas in Methods_and_Results.md and plot_data.json</footer></section>'''
figures=sorted((OUT/'figures').glob('*.svg'));assert len(figures)==10
html='''<!doctype html><html><head><meta charset="utf-8"><title>IFC to CityGML conversion fidelity</title><style>
@page{size:12.5in 9.1666667in;margin:0}*{box-sizing:border-box}body{margin:0;font-family:"Palatino Linotype",Palatino,serif;color:#243536}section{width:1200px;height:880px;break-after:page;overflow:hidden}section:last-child{break-after:auto}svg{display:block;width:1200px;height:880px}.intro{padding:45px 55px;position:relative}.kicker{font-size:17px;color:#626b69}h1{font-size:34px;font-weight:400;color:#000;margin:28px 0 12px}.subtitle{font-size:20px;color:#626b69;margin:0 0 35px}.columns{display:grid;grid-template-columns:1fr 1fr;gap:65px}h2{font-size:24px;font-weight:400;color:#000;margin:14px 0 14px}p{font-size:18.5px;line-height:1.35;margin:0 0 16px}footer{position:absolute;bottom:35px;left:55px;font-size:16px;color:#626b69}
</style></head><body>'''+intro+''.join('<section>'+x.read_text(encoding='utf-8')+'</section>' for x in figures)+'</body></html>'
page=OUT/'Research_Atlas.html';page.write_text(html,encoding='utf-8')
subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless','--disable-gpu','--no-pdf-header-footer',f'--print-to-pdf={OUT/"Research_Atlas_Palatino.pdf"}',page.as_uri()],capture_output=True,check=True)
with ZipFile(OUT/'Palatino_Research_Figures.zip','w',ZIP_DEFLATED) as z:
    for path in [*sorted((OUT/'figures').glob('*')),OUT/'metrics_240.csv',OUT/'Methods_and_Results.md',OUT/'plot_data.json']:
        z.write(path,path.relative_to(OUT))
print('Packaged 12 page atlas, ten editable figures, complete CSV and methods')

