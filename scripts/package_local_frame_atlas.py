"""Package the sixteen figure research atlas without changing prior artifacts."""
import csv
import json
from pathlib import Path
import shutil
import subprocess
from zipfile import ZipFile,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/local_frame_003';EXP=ROOT/'results/experiments/local_frame_003'
data=json.loads((EXP/'evaluation.json').read_text())
for path in (ROOT/'reports/shape_fidelity_002/figures').glob('*'):shutil.copyfile(path,OUT/'figures'/path.name)

def flatten(row,arm):
    d={k:row[k] for k in ['case','shape_family','yaw_degrees','units','status','cohort']};d.update(arm=arm,mode='exterior',report=row['report'])
    if arm=='local_frame':d['report']=str((EXP/'candidate'/row['report']).relative_to(ROOT))
    for key,value in row['mesh_audit'].items():d['mesh_'+key]=value
    for precision in ['raw','measurement_1nm','measurement_1um']:
        for key,value in (row.get('metrics') or {}).get(precision,{}).items():d[precision+'_'+key]=value
    for key,value in (row.get('metrics') or {}).get('volume',{}).items():d['volume_'+key]=value
    return d

paired=[flatten(r,arm) for arm,key in [('baseline','baseline'),('local_frame','candidate')] for r in data[key]]
combined=list(csv.DictReader((ROOT/'reports/shape_fidelity_002/metrics_240.csv').open(encoding='utf-8')))
for r in combined:
    if r['arm']=='candidate':r['report']='results/experiments/shape_fidelity_002/candidate/'+r['report']
combined.extend(r for r in paired if r['arm']=='local_frame' or r['cohort']=='prospective_angles')
assert len(paired)==160 and len(combined)==340
for name,rows in [('matched_exterior_160.csv',paired),('combined_controlled_340.csv',combined)]:
    with (OUT/name).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));writer.writeheader();writer.writerows(rows)

intro='''<section class="intro"><div class="kicker">Research update / 3 November 2026</div>
<h1>Local building frames in IFC to CityGML</h1><p class="subtitle">Expanded methodology and results with sixteen Palatino figures</p>
<div class="columns"><article><h2>A numerical mechanism with a tested remedy</h2>
<p>Snapping rotated geometry in a world coordinate grid can separate intended contacts and create very short union edges. A finer grid alone moved the failures between cases. A simplification probe left the known 22 nm edge unchanged.</p>
<p>The new candidate transforms input vertices into the IFC building placement frame before snapping and Boolean union, then restores world coordinates. The union grid and validator snapping both remain at 1 µm.</p>
<h2>What improved in the controls</h2><p>The candidate passes all 80 exterior controls, including 20 prospective angular controls. It also preserves the expected component and Euler diagnostics in all 80. The world frame baseline passes 70 of 80, but only 44 of 80 match the intended topology diagnostics.</p>
<p>This distinction matters: 26 valid baseline outputs do not match the intended component count or Euler characteristic.</p>
</article><article><h2>External files retain important limits</h2>
<p>Four existing public IFC files were tested with the fixed adapter. Duplex passes the surface check but still fails the stronger Solid diagnostic. Clinic, Gaia and Digital Hub retain source extraction failures.</p>
<p>The numerical improvement is supported for these controlled shapes. It does not establish a general solution to unsupported source solids, real building semantics or geographic accuracy. The installed converter remains unchanged.</p>
<h2>How to read this atlas</h2><p>Figures 1–10 retain the earlier studies and their 240 attempts. Figures 11–16 present the local frame method, failure mechanism, new comparisons and external check. The combined studies contain 340 controlled attempts on 80 related inputs, plus four external checks.</p>
<p>Detailed methods, complete CSV rows, source hashes and failed reports accompany the atlas. All 125 tests pass.</p></article></div>
<footer>Research adapter only · Original releases preserved · Torino and flood accuracy remain outside these controlled results</footer></section>
<section class="intro"><div class="kicker">Research methodology / Local frame experiment 003</div>
<h1>Prospective comparison and acceptance criteria</h1><p class="subtitle">The protocol discloses the known case prototype before the angular extension</p>
<div class="columns"><article><h2>Design and reference construction</h2>
<p>The experiment reuses 60 controls and adds 20 at 22.5° and 67.5°, spanning the same five forms and two source units. Eighty local frame conversions are paired with 80 world frame exterior cases. The new experiment adds 100 attempts; earlier attempts are not counted twice.</p>
<p>The five massing designs have independently declared footprint dimensions and nonoverlapping reference prism volumes. They are related analytical controls, not 80 independently sampled buildings.</p>
<h2>Numerical and validation policy</h2><p>Both grid spacing and validator snapping stay at 1 µm. The adapter requires a gravity aligned proper rigid building placement, uses the original attributed union routine, and restores the original engineering metre coordinates.</p>
<p>It performs no mesh simplification or geographic transformation. The ordinary CityGML writer and independent validators remain in use.</p></article>
<article><h2>Acceptance beyond a valid export</h2>
<p>Each candidate must pass the declared surface and stronger Solid checks, footprint IoU ≥ 0.999999, discrete boundary distance ≤ 5 µm and absolute relative volume error ≤ 10⁻⁶.</p>
<p>Topology diagnostics require one component, Euler characteristic 0 for the courtyard and 2 for the other forms, plus no edges shorter than 1 µm. Euler characteristic is a limited diagnostic rather than a complete topology proof.</p>
<h2>Measured outcome and scope</h2><p>All 80 candidates meet these guards. On derived 1 nm footprints, IoU is 1 and boundary distance is zero. Maximum absolute relative volume error is about 1.12 × 10⁻¹³. These are arithmetic comparisons with ideal controls, not surveyed physical accuracy.</p>
<p>External checks are exploratory and reported separately. Further work must address nonaligned local geometry, unreliable placements and unsupported source topology.</p></article></div>
<footer>Raw metrics remain available · Failed attempts stay in the denominators · No source or release files are overwritten</footer></section>'''
old=(ROOT/'reports/shape_fidelity_002/Research_Atlas.html').read_text(encoding='utf-8')
style=old.split('<style>',1)[1].split('</style>',1)[0]
figures=sorted((OUT/'figures').glob('*.svg'));assert len(figures)==16
html='<!doctype html><html><head><meta charset="utf-8"><title>Local building frames in IFC to CityGML</title><style>'+style+'</style></head><body>'+intro+''.join('<section>'+p.read_text(encoding='utf-8')+'</section>' for p in figures)+'</body></html>'
page=OUT/'Research_Atlas.html';page.write_text(html,encoding='utf-8')
subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless','--disable-gpu','--no-pdf-header-footer',f'--print-to-pdf={OUT/"Research_Atlas_Palatino.pdf"}',page.as_uri()],capture_output=True,check=True)
with ZipFile(OUT/'Palatino_Figures_and_Results.zip','w',ZIP_DEFLATED) as z:
    for path in [*sorted((OUT/'figures').glob('*')),OUT/'Methods_and_Results.md',OUT/'matched_exterior_160.csv',OUT/'combined_controlled_340.csv']:
        z.write(path,path.relative_to(OUT))
print('Created 18 page atlas and 16 figure pack with complete 340 row controlled evidence')
