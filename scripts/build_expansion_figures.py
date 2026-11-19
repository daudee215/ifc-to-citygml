"""Publication figures from retained rows; no invented outcomes or intervals."""
from pathlib import Path
from collections import Counter
import base64
import html
import json
import math
import subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/expansion_v2';FIG=OUT/'figures';FIG.mkdir(parents=True,exist_ok=True)
INK='#243b3d';TEAL='#47786a';RUST='#ad7458';GREY='#e6eae5';MUTED='#687b7a';BLUE='#7291a1'
parts=[];sources=[]
def text(x,y,value,size=24,color=INK,anchor='start'):parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}">{html.escape(str(value))}</text>')
def rect(x,y,w,h,color):parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}" rx="3"/>')
def line(x,y,X,Y,color=GREY):parts.append(f'<path d="M{x},{y} L{X},{Y}" stroke="{color}" fill="none"/>')
def start(n,title,sub):
    parts.clear();rect(0,0,1600,1000,'#fbfaf7');text(80,73,f'IFC → CITYGML   /   RESEARCH EVIDENCE {n:02}',19,TEAL);text(80,137,title,41);text(80,184,sub,23,MUTED);line(80,215,1520,215)
def save(name,foot,limit):
    line(80,897,1520,897);text(80,936,foot,20,MUTED);text(80,971,limit,19,MUTED)
    svg='<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1600" height="1000" viewBox="0 0 1600 1000"><g font-family="Palatino Linotype,Palatino,serif">'+''.join(parts)+'</g></svg>'
    path=FIG/(name+'.svg');path.write_text(svg,encoding='utf-8');sources.append(name)
def image(path,x,y,w,h):parts.append(f'<image x="{x}" y="{y}" width="{w}" height="{h}" href="data:image/png;base64,{base64.b64encode(path.read_bytes()).decode()}"/>')
def load(name):
    d=json.loads((ROOT/f'results/expansion_v2/{name}/index.json').read_text())
    if d['status']!='completed':raise ValueError(name+' is still running')
    return d['cases']
METHODS=['world_grid','building_grid','unquantised','conditioned_grid','guarded']
LABELS={'world_grid':'World grid · 1 µm','building_grid':'Building grid · 1 µm','unquantised':'Unquantised','conditioned_grid':'Conditioned grid · 10 nm','guarded':'Guarded selection'}

def coverage(rows):
    start(1,'Acceptance and reference fidelity are separate tests','Development smoke suite · 120 inputs per method · Equal inputs, units and reference budgets')
    text(490,265,'Operationally accepted',22,BLUE);text(970,265,'Accepted + all reference checks',22,TEAL)
    for i,m in enumerate(METHODS):
        r=[r for r in rows if r['backend']==m];accepted=sum(r['status']=='accepted' for r in r);good=sum(r['status']=='accepted' and r['reference_all_guards'] for r in r);y=310+i*101
        text(80,y+32,LABELS[m],25)
        for x,value,color in [(490,accepted,BLUE),(970,good,TEAL)]:
            rect(x,y,390,45,GREY);rect(x,y,390*value/120,45,color);text(x+410,y+32,f'{value}/120',23)
    save('01_acceptance_and_fidelity','Source: expansion_v2/smoke/index.json; every failed or rejected attempt remains in the denominator.','Operational rejection can reflect a strict displacement budget even when the reference geometry checks pass.')

def families(rows):
    families=sorted({r['family'] for r in rows});start(2,'The geometry challenge now spans thirteen families','Cells show accepted outputs passing every analytical reference check / tested inputs')
    for j,m in enumerate(METHODS):text(540+j*205,270,LABELS[m].split(' ·')[0],21,anchor='middle')
    for i,f in enumerate(families):
        y=292+i*43;text(80,y+29,f.replace('_',' ').capitalize(),23)
        for j,m in enumerate(METHODS):
            group=[r for r in rows if r['family']==f and r['backend']==m];good=sum(r['status']=='accepted' and r['reference_all_guards'] for r in group);frac=good/len(group);color=TEAL if frac==1 else BLUE if frac>=.5 else '#e4cdc0';rect(455+j*205,y,170,36,color);text(540+j*205,y+26,f'{good}/{len(group)}',22,'white' if frac>=.5 else INK,'middle')
    save('02_geometry_family_matrix','Source: completed smoke suite; refactored placement counterparts remain in their original family.','These are designed controls, including gable/hip roofs, openings, curved geometry, passages and genuine gaps.')

def gaps(rows):
    start(3,'Real gaps must survive numerical conditioning','48 controls · Six separations × four geometry rotations × metre/millimetre inputs')
    sizes=['0','1e-09','1e-07','5e-07','2e-06','0.001'];labels=['Contact','1 nm','100 nm','500 nm','2 µm','1 mm']
    for j,label in enumerate(labels):text(580+j*156,294,label,25,anchor='middle')
    for i,m in enumerate(METHODS):
        y=340+i*93;text(80,y+40,LABELS[m],25)
        for j,size in enumerate(sizes):
            group=[r for r in rows if r['backend']==m and r['group'].startswith('gap_'+size+'_')];good=sum(r['status']=='accepted' and r['reference_all_guards'] for r in group)
            if len(group)!=8:raise ValueError((size,len(group)))
            rect(515+j*156,y,130,58,TEAL if good==8 else '#e4cdc0');text(580+j*156,y+39,f'{good}/8',28,'white' if good==8 else INK,'middle')
    save('03_contacts_and_real_gaps','Source: expansion_v2/gaps/index.json; original analytic gap widths were registered before execution.','Separating axes and finite probes are numerical evidence, not exact arithmetic or complete proof of shape equivalence.')

def partitions(dev,locked):
    start(4,'Broader evaluation reveals the remaining failures','Frozen methods · Separate deterministic seeds · No tuning against locked outcomes')
    legend=[('Accepted + reference passed',TEAL),('Accepted + reference failed',RUST),('Rejected / review / failed',GREY)]
    for i,(label,color) in enumerate(legend):rect(80+i*480,255,18,18,color);text(108+i*480,271,label,21)
    for panel,(name,rows,x) in enumerate([('Development · 800 inputs',dev,80),('Locked · 400 inputs',locked,850)]):
        text(x,340,name,29)
        for i,m in enumerate(METHODS[2:]):
            r=[r for r in rows if r['backend']==m];n=len(r);good=sum(z['status']=='accepted' and z['reference_all_guards'] for z in r);bad=sum(z['status']=='accepted' and not z['reference_all_guards'] for z in r);y=400+i*137
            text(x,y,LABELS[m],23);cursor=x
            for value,color in [(good,TEAL),(bad,RUST),(n-good-bad,GREY)]:rect(cursor,y+22,630*value/n,42,color);cursor+=630*value/n
            text(x,y+95,f'{good} passed   /   {bad} accepted failures   /   {n-good-bad} other',21,MUTED)
    save('04_development_and_locked','Source: immutable development and locked run protocols and complete attempt indexes.','An accepted reference failure is retained as a counterexample; the candidate remains experimental.')

def scatter(rows):
    rows=[r for r in rows if r['backend']=='guarded' and 'metrics' in r];start(5,'A near-perfect footprint can conceal broken 3D topology','Locked controls · Guarded method · One point per input with an exported geometry')
    x0,y0,w,h=235,310,1140,470
    for e in [-14,-10,-6,-2,2]:
        x=x0+(e+14)/16*w;line(x,y0,x,y0+h);text(x,y0+h+40,f'10^{e}',22,MUTED,'middle')
    for e in [-14,-10,-6,-2,2]:
        y=y0+h-(e+14)/16*h;line(x0,y,x0+w,y);text(x0-24,y+8,f'10^{e}',22,MUTED,'end')
    for r in rows:
        m=r['metrics'];a=max(1e-14,m['footprints']['measurement_1nm']['boundary_discrete_hausdorff_m']);b=max(1e-14,m['sampled_surface_distance']['sampled_maximum_m']);x=x0+max(0,min(1,(math.log10(a)+14)/16))*w;y=y0+h-max(0,min(1,(math.log10(b)+14)/16))*h
        parts.append(f'<circle cx="{x}" cy="{y}" r="5" fill="{TEAL if r["reference_all_guards"] else RUST}" opacity=".72"/>')
    text(235,265,'Vertical axis: sampled 3D surface distance (m)',23,MUTED);text(800,857,'Horizontal axis: footprint boundary distance (m)',24,MUTED,'middle')
    save('05_footprint_and_3d_error','Source: locked serialized GML measurements; teal = all reference checks pass, rust = at least one fails.','Zeros are placed at 10^-14 m for log display. Distances are sampled/discrete measures; not certified Hausdorff bounds.')

def corpus():
    inventory=json.loads((ROOT/'results/expansion_v2/corpus_inventory.json').read_text());start(6,'Open IFC data broaden applicability, not geographic truth','26 distinct IFC files · 17 conservative provenance groups · Explicit licences and publisher checksums')
    groups=[('Existing public benchmarks',4,4),('GNI 2026 student projects',16,9),('BIM4EEB demonstration sites',3,3),('Tafraout architectural collection',3,1)]
    text(650,285,'Files',25,BLUE);text(1110,285,'Provenance groups',25,TEAL)
    for i,(label,files,n) in enumerate(groups):
        y=330+i*104;text(80,y+35,label,26)
        for x,value,color in [(650,files,BLUE),(1110,n,TEAL)]:rect(x,y,310*value/16,45,color);text(x+330,y+33,value,26)
    text(80,817,'Verified Torino IFC + independent survey control pairs found: 0',29,RUST)
    save('06_public_corpus_and_reference_readiness','Sources: retained Zenodo records 19722012, 6685810, 6397164; existing benchmark source manifests.','GNI discipline pairs stay together; Tafraout independence is unverified. Files over 80 MB await bounded SDK inspection.')

def context():
    manifest=json.loads((ROOT/'data/raw/torino_context/source_manifest.json').read_text());bounds=manifest['bbox'];x0,y0,w,h=80,265,850,580;s=min(w/(bounds[2]-bounds[0]),h/(bounds[3]-bounds[1]))
    start(7,'Torino provides a real urban context demonstration','Official BDTRE outline aggregates and November 2016 event polygons · EPSG:32632')
    def coord(p):return (x0+(p[0]-bounds[0])*s,y0+h-(p[1]-bounds[1])*s)
    parts.append('<defs><clipPath id="map"><rect x="80" y="265" width="850" height="580"/></clipPath></defs><g clip-path="url(#map)">')
    for name,color in [('event_2016_extent.geojson','#cddfe3'),('buildings.geojson',TEAL)]:
        collection=json.loads((ROOT/'data/raw/torino_context'/name).read_text())
        for feature in collection['features']:
            geom=feature['geometry'];polys=[geom['coordinates']] if geom['type']=='Polygon' else geom['coordinates'] if geom['type']=='MultiPolygon' else []
            for polygon in polys:
                d=' '.join('M'+' L'.join(f'{x:.2f},{y:.2f}' for x,y in map(coord,ring))+' Z' for ring in polygon)
                parts.append(f'<path d="{d}" fill="{color}" fill-rule="evenodd"/>')
    parts.append('</g>');result=json.loads((ROOT/'results/expansion_v1/torino_context_exposure.json').read_text())
    for i,(value,label) in enumerate([(result['feature_count'],'Outline aggregates'),(result['positive_area_features'],'Positive-area intersections'),(f'{result["union_exposed_area_m2"]/1e6:.3f} km²','Intersected footprint union')]):text(1040,350+i*154,value,43,TEAL);text(1040,391+i*154,label,23,MUTED)
    text(1040,817,'Context only',29,RUST)
    save('07_torino_context_map','Source: retained official service responses and hash-checked source manifest; historical event extent.','Outline aggregates are not individual building counts. This does not validate IFC placement, water depth or conversion effects.')

def roofs():
    start(8,'Roof and passage geometry now have direct visual checks','Actual depth-buffer renderings · Source, serialized conversion and independent reference · Equal scale within rows')
    for j,label in enumerate(['IFC source','Serialized CityGML','Analytical reference']):text(400+j*425,270,label,25,anchor='middle')
    for i,(case,label) in enumerate([('gable_roof_b0_c0_m','Gable roof'),('hip_roof_b0_c0_m','Hip roof'),('passage_b0_c23_m','Passage')]):
        y=295+i*185;text(80,y+90,label,22)
        for j,view in enumerate(['source','target','reference']):image(OUT/(case+'_'+view+'.png'),205+j*425,y,390,180)
    save('08_roofs_and_passage_geometry','Source: WebGL inspection viewer; guarded smoke outputs and independent closed-form control meshes.','Colours identify source elements or output components. They do not establish roof/wall semantic classification accuracy.')

def main():
    smoke=load('smoke');coverage(smoke);families(smoke);gaps(load('gaps'));partitions(load('development'),load('locked'));scatter(load('locked'));corpus();context();roofs()
    for name in sources:
        subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless','--disable-gpu','--hide-scrollbars','--force-device-scale-factor=2','--window-size=1600,1000',f'--screenshot={FIG/(name+".png")}',(FIG/(name+'.svg')).as_uri()],capture_output=True,check=True,timeout=40)
    (OUT/'figure_index.json').write_text(json.dumps({'figures':sources,'font':'Palatino Linotype','evidence':'Complete retained indexes; no invented observations'},indent=2))
    print('Created',len(sources),'SVG and PNG figures')

if __name__=='__main__':main()
