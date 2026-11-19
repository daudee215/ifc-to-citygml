"""Curated larger Palatino figures with explicit evidence and consistent scales."""
import base64
from collections import Counter
import html
import json
import math
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/publication_figures_004';FIG=OUT/'figures';FIG.mkdir(exist_ok=True)
OLD=json.loads((ROOT/'results/experiments/shape_fidelity_002/evaluation.json').read_text())
LOCAL=json.loads((ROOT/'results/experiments/local_frame_003/evaluation.json').read_text())
STRESS=json.loads((ROOT/'results/experiments/frame_alignment_004/index.json').read_text());assert STRESS['status']=='completed'
INK='#1d3034';TEAL='#426e68';BLUE='#718d9b';RUST='#a16c53';MUTED='#65716f';LINE='#dce2df';SAGE='#dce8e2';SAND='#f0e2d7'
parts=[]
def text(x,y,s,size=23,color=INK,anchor='start',weight=400):parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}">{html.escape(str(s))}</text>')
def rect(x,y,w,h,fill,rx=0):parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"/>')
def line(x,y,xx,yy,color=LINE,width=1,dash=''):parts.append(f'<path d="M{x},{y}L{xx},{yy}" fill="none" stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}"/>')
def circle(x,y,r,color):parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>')
def picture(path,x,y,w,h):
    encoded=base64.b64encode(path.read_bytes()).decode();parts.append(f'<image x="{x}" y="{y}" width="{w}" height="{h}" href="data:image/png;base64,{encoded}"/>')
def start(n,title,subtitle):
    parts.clear();rect(0,0,1600,1000,'white');text(80,55,f'IFC to CityGML   /   Figure {n:02}',20,MUTED)
    text(80,122,title,44,'#101e21');text(80,167,subtitle,23,MUTED);line(80,197,1520,197)
def save(name,source,note):
    line(80,898,1520,898);text(80,935,source,19,MUTED);text(80,969,note,19,MUTED)
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000" viewBox="0 0 1600 1000"><g font-family="Palatino Linotype, Palatino, serif">'+''.join(parts)+'</g></svg>'
    path=FIG/(name+'.svg');path.write_text(svg,encoding='utf-8')
    subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless','--disable-gpu','--hide-scrollbars','--force-device-scale-factor=2','--window-size=1600,1000',f'--screenshot={FIG/(name+".png")}',path.as_uri()],capture_output=True,check=True)

def duplex():
    start(1,'One IFC building in three representations','Duplex public benchmark   ·   Actual exported polygons   ·   Identical camera and physical scale')
    for i,(title,num,desc) in enumerate([('Bounding block','6 faces','Selected physical bounds'),('Exterior surfaces','4,104 polygons','Source attributed union'),('Source surfaces','9,420 triangles','137 represented features')]):
        x=80+i*495;text(x,257,chr(97+i).upper(),19,TEAL);text(x+33,257,title,30)
        picture(ROOT/f'reports/methodology_palatino/depth_model_{i}.png',x-5,285,485,441)
        line(x,753,x+445,753);text(x,797,num,32,TEAL);text(x,840,desc,23,MUTED)
    save('01_duplex_representations','Source: frozen v0.6 Duplex CityGML exports and independent source audit. Visibility uses a depth buffer.',
         'The roof geometry is unchanged. These representations have different purposes; surface validity does not establish a watertight volume.')

def forms():
    start(2,'Bounding blocks remove courtyards and setbacks','Four analytical designs   ·   Unrotated metre inputs   ·   Same camera and scale within every comparison')
    labels=[('l_shape',1,'L shape'),('u_shape',2,'U shape'),('courtyard',3,'Courtyard'),('setback',4,'Setback')]
    for k,(f,i,label) in enumerate(labels):
        x=80+(k%2)*760;y=245+(k//2)*315;text(x,y,label,30)
        text(x+160,y+35,'Exterior',19,TEAL,anchor='middle');text(x+405,y+35,'Block',19,BLUE,anchor='middle')
        picture(ROOT/f'reports/shape_fidelity_002/model_{i*3+1}.png',x+40,y+35,245,223)
        picture(ROOT/f'reports/shape_fidelity_002/model_{i*3}.png',x+285,y+35,245,223)
        r=next(r for r in OLD['baseline_rows'] if r['shape_family']==f and r['yaw_degrees']==0 and r['units']=='metre' and r['mode']=='block')['metrics']
        text(x+560,y+111,'Added area',19,MUTED);text(x+560,y+147,f"+{max(0,r['raw']['area_overestimate_percent']):.1f}%",30,RUST)
        text(x+560,y+193,'Added volume',19,MUTED);text(x+560,y+229,f"+{max(0,100*r['volume']['relative_error']):.1f}%",30,RUST)
    save('02_structural_shape_loss','Source: actual baseline GML outputs and independently declared prism dimensions. Each pair retains equal model scale.',
         'These idealised massing designs test geometry; their IFC element labels are not independent semantic ground truth.')

def components():
    start(3,'A valid courtyard can have the wrong connectivity','Component colours expose topology that is invisible in a footprint area comparison')
    cases=[('World frame','Aligned source at 45°',2,4),('Building frame','Aligned source at 45°',1,0),('Building frame','Oblique source at 44°',2,4)]
    for i,(title,sub,count,euler) in enumerate(cases):
        x=80+i*495;text(x,257,title,30);text(x,299,sub,22,MUTED)
        picture(OUT/f'courtyard_components_{i}.png',x-5,327,485,441)
        text(x,802,f'{count} component'+('s' if count!=1 else '')+f'   ·   Euler {euler}',27,TEAL if count==1 else RUST)
        text(x,847,'Expected topology' if count==1 else 'Topology differs from the design',21,MUTED)
    save('03_courtyard_component_geometry','Source: retained study 001, 003 and 004 exterior meshes. One colour per connected union component; equal camera and scale.',
         'Gaps between components can be too small to see at this scale. Colours identify components, not different materials or semantic classes.')

def paired_errors():
    start(4,'Area and volume quantify different representation losses','Bounding block increase above the analytical reference   ·   One shared colour scale for both matrices')
    families=['rectangle','l_shape','u_shape','courtyard','setback'];labels=['Rectangle','L shape','U shape','Courtyard','Setback'];angles=[0,15,30,45,60,75]
    for panel,(heading,x,volume) in enumerate([('Footprint area',275,False),('Building volume',925,True)]):
        text(x+270,262,heading,31,anchor='middle')
        for j,a in enumerate(angles):text(x+j*89+42,312,f'{a}°',21,MUTED,anchor='middle')
        for i,(f,label) in enumerate(zip(families,labels)):
            y=343+i*82
            if panel==0:text(80,y+47,label,25)
            for j,a in enumerate(angles):
                m=next(r for r in OLD['baseline_rows'] if r['shape_family']==f and r['yaw_degrees']==a and r['units']=='metre' and r['mode']=='block')['metrics']
                value=max(0,100*m['volume']['relative_error'] if volume else m['raw']['area_overestimate_percent']);t=min(value/240,1)
                rgb=[round(247*(1-t)+v*t) for v in (66,110,104)];colour='#'+''.join(f'{v:02x}' for v in rgb)
                rect(x+j*89,y,85,76,colour);text(x+j*89+42,y+47,f'{value:.0f}%',23,'white' if t>.63 else INK,anchor='middle')
    for k in range(240):
        t=k/239;rgb=[round(247*(1-t)+v*t) for v in (66,110,104)];rect(485+k*2,806,2.1,14,'#'+''.join(f'{v:02x}' for v in rgb))
    text(485,857,'0% increase',20,MUTED);text(965,857,'240% increase',20,MUTED,anchor='end')
    text(1070,835,'Setback at 0°: area 0%, volume 60%.',22)
    save('04_area_volume_comparison','Source: all 60 passed baseline block exports. Metre values shown; unit counterparts agree. Labels are rounded to whole percentages.',
         'Each percentage uses its own reference area or volume denominator. Colour limits stay fixed at 0–240% across both matrices.')

def validity():
    start(5,'Geometry validation is only one acceptance criterion','Eighty matched aligned exterior controls   ·   Expected topology uses component count and Euler characteristic')
    for i,(title,rows,x) in enumerate([('World frame baseline',LOCAL['baseline'],270),('Building frame candidate',LOCAL['candidate'],955)]):
        text(x+195,256,title,30,anchor='middle')
        text(x+95,312,'Expected topology',20,MUTED,anchor='middle');text(x+310,312,'Topology mismatch',20,MUTED,anchor='middle')
        for a,status in enumerate(['passed','failed']):
            if i==0:text(80,421+a*195,'Valid geometry' if a==0 else 'Invalid geometry',24)
            for j,good in enumerate([True,False]):
                n=sum(r['status']==status and ((r['mesh_audit']['components']==1 and r['mesh_audit']['euler_sum']==(0 if r['shape_family']=='courtyard' else 2))==good) for r in rows)
                xx=x+j*215;yy=349+a*195;rect(xx,yy,200,175,SAGE if good and status=='passed' else SAND if n else '#f4f5f3',3)
                text(xx+100,yy+110,n,61,TEAL if good and status=='passed' else RUST if n else MUTED,anchor='middle')
    text(80,825,'Twenty six valid baseline outputs fail the intended topology diagnostics. The aligned candidate satisfies both in all 80.',28)
    save('05_validity_and_topology','Source: study 003 paired exterior records. All attempt denominators are retained; failed cases use their retained extraction meshes.',
         'Euler characteristic is a diagnostic, not a complete topology proof. These fixtures have independently known intended construction.')

def stress():
    start(6,'Oblique source geometry exposes the method limit','New study 004   ·   Every cell contains two unit counterparts   ·   Validity and all acceptance guards are reported separately')
    combinations=[(7,0),(7,37),(23,0),(23,37)]
    for panel,(arm,title,x) in enumerate([('world_frame','World frame baseline',270),('building_frame','Building frame candidate',925)]):
        text(x+280,253,title,30,anchor='middle')
        for j,(inner,outer) in enumerate(combinations):
            text(x+j*145+65,302,f'{inner}° / {outer}°',22,MUTED,anchor='middle')
        for i,(f,label) in enumerate([('l_shape','L shape'),('u_shape','U shape'),('courtyard','Courtyard'),('setback','Setback')]):
            y=332+i*116
            if panel==0:text(80,y+63,label,25)
            for j,(inner,outer) in enumerate(combinations):
                rows=[r for r in STRESS['cases'] if r['arm']==arm and r['shape_family']==f and r['contents_yaw_degrees']==inner and r['building_yaw_degrees']==outer]
                assert len(rows)==2;valid=sum(r['status']=='passed' for r in rows);allok=sum(r['all_guards_passed'] for r in rows)
                xx=x+j*145;rect(xx,y,136,106,SAGE if allok==2 else '#eee9dc' if valid==2 else SAND,2)
                text(xx+68,y+43,f'Valid {valid}/2',22,anchor='middle');text(xx+68,y+79,f'All guards {allok}/2',20,TEAL if allok==2 else RUST,anchor='middle')
    text(80,853,'Column labels: contents rotation / building placement rotation. The fixed candidate validates 32/32, but meets all guards in 16/32.',25)
    save('06_alignment_stress','Source: prospectively recorded 32 new IFC4 controls, 64 conversion attempts. Settings fixed at union grid 1 µm and validator snapping 1 µm.',
         'The aligned 80/80 result does not generalise to these oblique controls. No tolerance was tuned after observing the outcomes.')

def precision():
    start(7,'Measurement precision can change the planar boundary result','Sixty source preserving outputs   ·   Same points and axes in both panels   ·   Marker size counts coincident observations')
    source=[r for r in OLD['baseline_rows'] if r['mode']=='source'];assert len(source)==60
    for panel,(key,title,x0) in enumerate([('raw','Raw derived footprint',200),('measurement_1nm','Derived footprint on a 1 nm grid',940)]):
        text(x0+220,257,title,29,anchor='middle');y0=720;w=450;h=370
        def xx(v):return x0+(math.log10(max(v,1e-15))+15)/7*w
        def yy(v):return y0-(math.log10(max(v,1e-15))+15)/16*h
        for power in [-15,-12,-9,-8]:
            x=xx(10**power);line(x,y0-h,x,y0);text(x,y0+50,'0 floor' if power==-15 else f'1e{power}',19,MUTED,anchor='middle')
        for power in [-15,-10,-5,0]:
            y=yy(10**power);line(x0,y,x0+w,y);text(x0-40,y+6,'0 floor' if power==-15 else f'1e{power}',19,MUTED,anchor='end')
        threshold=yy(5e-6);line(x0,threshold,x0+w,threshold,RUST,1.4,'5 5')
        grouped=Counter((round(xx(r['metrics'][key]['symmetric_difference_m2']),1),round(yy(r['metrics'][key]['boundary_hausdorff_m']),1)) for r in source)
        for (x,y),n in grouped.items():
            radius=5+2.2*math.sqrt(n);circle(x,y,radius,BLUE if panel==0 else TEAL)
            if n>=3:text(x,y+6,n,17,'white',anchor='middle')
        text(x0+w/2,819,'Footprint symmetric difference in m²',22,MUTED,anchor='middle')
    parts.append(f'<text x="82" y="545" transform="rotate(-90 82 545)" font-size="23" fill="{MUTED}" text-anchor="middle">Discrete boundary distance in metres</text>')
    text(80,867,'The dashed line is the 5 µm comparison threshold. Zero is shown at the plotting floor; both axes are logarithmic.',23)
    save('07_measurement_precision','Source: all 60 source exports in study 002. Precision is applied only to derived footprints and references, never to IFC or GML vertices.',
         'A large raw boundary metric alongside negligible area disagreement can result from planar union cracks. It is not a measured building displacement.')

def external():
    start(8,'External files fail at different conversion stages','Four public IFC files   ·   Fresh fixed policy local frame extractions   ·   Explicit failures remain visible')
    folder=ROOT/'results/experiments/local_frame_003/external'
    headings=[(80,'Benchmark'),(425,'Invalid source solids'),(785,'Zero area union triangles'),(1140,'Surface / Solid')]
    for x,title in headings:text(x,271,title,25,MUTED)
    for i,(case,label) in enumerate([('duplex','Duplex'),('clinic','Clinic'),('gaia_renovation','Gaia'),('digitalhub','Digital Hub')]):
        row=json.loads((folder/(case+'.report.json')).read_text());failures=row['extraction'].get('failures',[])
        source=sum('Unsupported source topology' in r['reason'] for r in failures);degenerate=sum('zero-area/non-finite triangle' in r['reason'] for r in failures)
        y=344+i*105;text(80,y,label,31);text(520,y,source,32,RUST if source else TEAL,anchor='middle');text(900,y,degenerate,32,RUST if degenerate else TEAL,anchor='middle')
        text(1140,y,'Pass / Fail' if row['status']=='passed' else 'Not reached',25,RUST);line(80,y+45,1520,y+45)
    text(80,807,'The frame change addresses a numerical contact problem.',27)
    text(80,851,'Unsupported source topology and degenerate union triangles require separate treatment.',25,MUTED)
    save('08_external_failure_stages','Source: retained study 003 element failures and validation reports. Counts identify rejected source solids and flagged union triangles.',
         'Duplex passes the declared surface check but fails the stronger Solid diagnostic. No failed extraction is published as a successful conversion.')

def torino():
    import build_research_figures as evidence
    context=evidence.D['context'];bbox=context['bbox'];assert bbox==[394000,4981000,396000,4983000]
    start(9,'Torino and Moncalieri provide the urban context','Retained open geodata in projected metres   ·   EPSG 32632   ·   Benchmark IFCs are not placed on this map')
    x0,y0,size=190,240,620;scale=size/2000
    rect(x0,y0,size,size,'#f6f7f3')
    parts.append(f'<defs><clipPath id="map"><rect x="{x0}" y="{y0}" width="{size}" height="{size}"/></clipPath></defs><g clip-path="url(#map)">')
    for key,fill,stroke,width in [('flood','#d3e4dc','#9bb9aa',.8),('buildings','#546c71','white',.45)]:
        for feature in context[key]['features']:
            geom=feature['geometry'];polys=[geom['coordinates']] if geom['type']=='Polygon' else geom['coordinates']
            for poly in polys:
                d=' '.join('M'+'L'.join(f'{x0+(v[0]-bbox[0])*scale:.2f},{y0+size-(v[1]-bbox[1])*scale:.2f}' for v in ring)+'Z' for ring in poly)
                parts.append(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" fill-rule="evenodd"/>')
    parts.append('</g>')
    rect(718,245,88,100,'white',2)
    for k in range(3):
        x=x0+k*310;y=y0+size-k*310;line(x,y0+size,x,y0+size+8,MUTED);text(x,889,f'{394000+k*1000:,}',19,MUTED,anchor='middle')
        line(x0-8,y,x0,y,MUTED);text(x0-18,y+7,f'{4981000+k*1000:,}',19,MUTED,anchor='end')
    # Grid north, rather than an inferred true-north convergence correction.
    line(762,328,762,283,INK,2);parts.append(f'<path d="M756,294L762,279L768,294Z" fill="{INK}"/>');text(762,267,'Grid N',17,INK,anchor='middle')
    rect(225,814,155,5,INK);text(225,802,'500 m',18,INK)
    for y,value,label,detail in [(296,'1,130','Building outline aggregates','BDTRE class cs_edi'),(464,'17','Historical event polygons','November 2016 inundation evidence'),(632,'4 km²','Retained query extent','Two kilometres by two kilometres')]:
        text(990,y,value,53,TEAL);text(990,y+44,label,26);text(990,y+80,detail,21,MUTED)
    rect(990,793,22,18,'#546c71');text(1028,810,'Building aggregate',22)
    rect(990,837,22,18,'#d3e4dc');text(1028,854,'Historical inundation polygon',22)
    assert len(context['buildings']['features'])==1130 and len(context['flood']['features'])==17
    save('09_torino_open_data_context','Sources: Regione Piemonte and CSI Piemonte BDTRE; Arpa Piemonte historical event WFS. Retained query geometry and IDs are unchanged.',
         'Seventeen polygons are not seventeen flood events. This context does not establish flood depth, present probability or IFC geographic accuracy.')

if __name__=='__main__':
    for function in [duplex,forms,components,paired_errors,validity,stress,precision,external,torino]:function();print(function.__name__,flush=True)
