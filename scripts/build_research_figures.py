"""Create editable SVG research figures directly from preserved v0.6 evidence."""
import html
import json
import math
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/methodology_visual_revision'
FIG = OUT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)
E = json.loads((ROOT / 'reports/methodology_v0_6/evidence_snapshot.json').read_text())
page = (ROOT / 'results/v0_6/review/index.html').read_text(encoding='utf-8')
D = json.loads(re.search(r'const DATA=(.*?);\s*\nconst colours=', page, re.S).group(1))
NAVY, TEAL, AMBER, RUST, BLUE = '#183449', '#087f8c', '#c89436', '#a6533e', '#638eae'
MUTED, LINE, PALE = '#526877', '#d9e3e8', '#f2f6f7'
parts = []


def rect(x,y,w,h,fill,rx=0,stroke='none'):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}"/>')


def text(x,y,s,size=20,color=NAVY,weight=400,anchor='start'):
    parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{html.escape(str(s))}</text>')


def lines(x,y,ss,size=20,color=MUTED,gap=29):
    for i,s in enumerate(ss): text(x,y+i*gap,s,size,color)


def line(x,y,xx,yy,color=LINE,width=2,dash=''):
    parts.append(f'<path d="M{x},{y} L{xx},{yy}" stroke="{color}" stroke-width="{width}" fill="none" stroke-dasharray="{dash}"/>')


def arrow(x,y,xx,yy,color=TEAL):
    line(x,y,xx,yy,color,2.5)
    a=math.atan2(yy-y,xx-x)
    pts=[(xx,yy),(xx-10*math.cos(a-.5),yy-10*math.sin(a-.5)),(xx-10*math.cos(a+.5),yy-10*math.sin(a+.5))]
    parts.append('<polygon points="'+' '.join(f'{a},{b}' for a,b in pts)+f'" fill="{color}"/>')


def start(n,title,sub):
    parts.clear()
    rect(0,0,1200,880,'white')
    text(55,49,f'IFC TO CITYGML   /   RESEARCH FIGURE {n:02}',15,TEAL,600)
    text(55,102,title,34,NAVY,650)
    text(55,141,sub,18,MUTED)
    line(55,169,1145,169)


def save(name,source,note):
    line(55,791,1145,791)
    text(55,823,source,15,MUTED)
    text(55,850,note,15,MUTED)
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="880" viewBox="0 0 1200 880"><g font-family="Arial, sans-serif">'+''.join(parts)+'</g></svg>'
    path=FIG/(name+'.svg'); path.write_text(svg,encoding='utf-8')
    subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless','--disable-gpu','--hide-scrollbars','--force-device-scale-factor=2','--window-size=1200,880',f'--screenshot={FIG/(name+".png")}',path.as_uri()],capture_output=True,check=True)


def workflow():
    start(1,'A traceable conversion workflow','A declared representation and coordinate policy determine every downstream operation.')
    for i,(title,detail) in enumerate([('Read IFC','Schema, units, placements'),('Resolve policy','Representation and coordinates'),('Extract geometry','Selected physical bodies')]):
        x=55+i*370
        text(x,228,f'0{i+1}',17,TEAL,700); text(x,266,title,25,NAVY,600); text(x,302,detail,18)
        if i<2: arrow(x+295,260,x+345,260)
    line(55,333,1145,333)
    for i,(title,ss,c) in enumerate([('Bounding block',['Aggregate selected vertices','Six faces form a Solid'],BLUE),('Exterior surfaces',['Material union and labels','Changes and failures logged'],AMBER),('Source surfaces',['Retain SDK triangles','Preserve source identities'],TEAL)]):
        x=55+i*370
        rect(x,373,6,139,c); text(x+23,405,title,25,c,600); lines(x+23,449,ss,20)
        arrow(x+165,529,x+165,565,c)
    line(220,565,960,565,TEAL,2)
    arrow(220,565,220,599)
    text(55,629,'CityGML 3.0',29,NAVY,600)
    text(430,629,'Validation',29,NAVY,600)
    text(800,629,'Correspondence audit',29,NAVY,600)
    arrow(320,621,401,621)
    arrow(685,621,770,621)
    lines(55,670,['Geometry and semantics','Declared coordinate frame'],19)
    lines(430,670,['XSD and target geometry','Separate Solid diagnostic'],19)
    lines(800,670,['Fresh source reconstruction','Explicit omissions and links'],19)
    save('01_conversion_workflow','Source: converter v0.6 profile contracts and implementation records.','Unsupported selected geometry remains a failed attempt; coordinate rejection can be a correct policy outcome.')


def geometry():
    start(2,'Three views of the same building','Duplex benchmark geometry read from exported CityGML in a local engineering frame.')
    models=[next(m for m in D['models'] if m['label']==f'duplex · {mode}') for mode in ['block','exterior','source']]
    colors={'Block':BLUE,'WallSurface':'#78a7b0','RoofSurface':'#c89436','GroundSurface':'#b3bdc4','Door':'#a6533e','Window':'#5d8cb9'}
    def proj(p):
        x,y,z=p
        return (.78*x-.63*y, .31*x+.38*y-.87*z, .5481*x+.6786*y+.4917*z)
    projected=[proj(p) for m in models for poly in m['polygons'] for p in poly['points']]
    lo=[min(p[i] for p in projected) for i in range(2)]; hi=[max(p[i] for p in projected) for i in range(2)]
    scale=min(325/(hi[0]-lo[0]),360/(hi[1]-lo[1]))
    for i,(m,title,ss) in enumerate(zip(models,['Bounding block','Exterior surfaces','Source surfaces'],[['6 box faces','Selected body bounds'],['4,104 polygons','Material union boundary'],['9,420 triangles','137 source features']])):
        x=55+i*370
        text(x,225,title,25,[BLUE,AMBER,TEAL][i],600)
        polys=sorted(m['polygons'],key=lambda q:sum(proj(p)[2] for p in q['points'])/len(q['points']))
        for poly in polys:
            coords=[]
            for p in poly['points']:
                a,b,_=proj(p); coords.append(f'{x+12+(a-lo[0])*scale:.2f},{282+(b-lo[1])*scale:.2f}')
            c=colors.get(poly['kind'],TEAL if i==2 else BLUE)
            parts.append('<polygon points="'+' '.join(coords)+f'" fill="{c}" stroke="{NAVY}" stroke-opacity=".16" stroke-width=".28"/>')
        lines(x,702,ss,20)
    save('02_building_representations','Source: frozen v0.6 Duplex block, exterior and source CityGML outputs.','Identical camera and scale. Surface export success does not establish a valid closed building volume.')


def validation():
    start(3,'What each validation layer establishes','Schema, geometric validity and source fidelity answer different research questions.')
    ys=[235,375,515]
    for y,n,title,ss in zip(ys,['01','02','03'],['Schema and references','Declared geometry','Source correspondence'],[
        ['CityGML XSD, identifiers and links','Checks structure and references'],['Solid for a bounding block','MultiSurface for source or exterior surfaces'],['Independent inventories and fresh extraction','Checks the declared source subset and serialized output']]):
        text(55,y,n,24,TEAL,650);text(120,y,title,27,NAVY,600);lines(120,y+40,ss,20)
        line(55,y+101,1145,y+101)
    text(55,687,'Additional Solid diagnostic',24,AMBER,600)
    lines(440,681,['Reinterprets surface output as a candidate closed volume.','Not applicable as an extra test when the target is already a Solid.'],20)
    save('03_validation_layers','Source: v0.6 validation adapter, audits and val3dity 2.7.0 reports.','Passing triangle based MultiSurface checks does not establish watertightness, semantic truth or survey accuracy.')


def outcomes():
    start(4,'Conversion outcomes by experiment','All 32 paired attempts remain visible, including policy rejections and geometry failures.')
    cases=E['research']['cases']; groups=[cases[:18],cases[18:26],cases[26:]]
    vals=[]
    for g in groups:
        p=sum(r['conversion_status']=='passed' for r in g); pre=sum(r['conversion_status']!='passed' and bool(r['pre_extraction_error']) for r in g)
        vals.append([p,pre,len(g)-p-pre])
    assert vals==[[17,0,1],[0,8,0],[4,0,2]], vals
    names=['Baseline profiles','Strict IFC4 policies','Engineering IFC4 profiles']
    x0,scale=430,35
    for i,(name,v) in enumerate(zip(names,vals)):
        y=276+i*130;text(55,y+24,name,22,NAVY,600)
        left=0
        for value,c in zip(v,[TEAL,AMBER,RUST]):
            if value:
                rect(x0+left*scale,y,value*scale,48,c,3);text(x0+(left+value/2)*scale,y+31,value,23,'white',700,'middle');left+=value
        text(x0+left*scale+18,y+32,f'n = {sum(v)}',19,MUTED)
    for tick in [0,5,10,15,20]:
        x=x0+tick*scale;line(x,666,x,672,MUTED,1);text(x,701,tick,17,MUTED,anchor='middle')
    text(780,735,'Number of attempts',18,MUTED,anchor='middle')
    for x,c,s in [(55,TEAL,'21 completed'),(410,AMBER,'8 coordinate rejections'),(840,RUST,'3 geometry failures')]:
        rect(x,208,16,16,c);text(x+27,223,s,19,NAVY)
    save('04_conversion_outcomes','Source: results/v0_6/research_summary.json; counts recomputed from all 32 attempt records.','Attempts reuse inputs across profiles. This is not a sample of 32 independent buildings or a population success estimate.')


def source_audit():
    start(5,'Source preservation across four external files','Separate scales show represented elements and serialized triangles without conflating their units.')
    rows=[r for r in E['source_audits']['cases'] if r['case'] in ['duplex','clinic','gaia_renovation','digitalhub']]
    assert sum(r['triangles_checked'] for r in rows)==286316
    text(55,221,'CASE',16,MUTED,600);text(250,221,'REPRESENTED ELEMENTS',16,TEAL,600);text(720,221,'TRIANGLES',16,BLUE,600)
    for i,r in enumerate(rows):
        y=284+i*93
        text(55,y+20,{'duplex':'Duplex','clinic':'Clinic','gaia_renovation':'Gaia','digitalhub':'DigitalHub'}[r['case']],23,NAVY,600)
        for x,key,maxval,width,c in [(250,'exported_features',2200,300,TEAL),(720,'triangles_checked',160000,300,BLUE)]:
            value=r[key];rect(x,y,value/maxval*width,29,c,2);text(x+value/maxval*width+12,y+23,f'{value:,}',20,c,600)
    text(250,692,'3,838 elements',27,TEAL,650);text(720,692,'286,316 triangles',27,BLUE,650)
    text(250,735,'891 explicit omissions retained in the audit denominator',20,MUTED)
    save('05_source_preservation','Source: six source correspondence audit records; only the four external cases are plotted.','All four audits pass their declared checks. Agreement with the SDK and mapping contract is not independent semantic accuracy.')


def context():
    start(6,'Torino and Moncalieri open data context','Building aggregates and historical inundation evidence in a separate GIS reference frame.')
    bbox=D['context']['bbox']; x0,y0,w,h=55,210,720,540
    scale=min(w/(bbox[2]-bbox[0]),h/(bbox[3]-bbox[1])); ox=x0+(w-(bbox[2]-bbox[0])*scale)/2; oy=y0
    rect(ox,oy,2000*scale,2000*scale,PALE)
    parts.append(f'<defs><clipPath id="map"><rect x="{ox}" y="{oy}" width="{2000*scale}" height="{2000*scale}"/></clipPath></defs><g clip-path="url(#map)">')
    def draw_geo(collection,fill,stroke):
        for feat in collection['features']:
            g=feat['geometry']; polygons=[g['coordinates']] if g['type']=='Polygon' else g['coordinates'] if g['type']=='MultiPolygon' else []
            for poly in polygons:
                d=''
                for ring in poly:
                    coords=[(ox+(p[0]-bbox[0])*scale,oy+2000*scale-(p[1]-bbox[1])*scale) for p in ring]
                    d+='M'+' L'.join(f'{x:.2f},{y:.2f}' for x,y in coords)+'Z '
                parts.append(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width=".45" fill-rule="evenodd"/>')
    draw_geo(D['context']['flood'],'#bedde7','#76b0c4');draw_geo(D['context']['buildings'],NAVY,'white');parts.append('</g>')
    arrow(ox+505,278,ox+505,239,NAVY);text(ox+505,229,'N',17,NAVY,600,'middle')
    rect(ox+20,724,500*scale,4,NAVY);text(ox+20,710,'500 m',16,NAVY)
    text(835,263,'1,130',42,NAVY,650);lines(835,301,['Building outline aggregates','BDTRE class cs_edi'],18)
    text(835,410,'17',42,TEAL,650);lines(835,448,['Event polygons','November 2016'],18)
    text(835,557,'4 km²',36,NAVY,650);lines(835,596,['Retained sample extent','EPSG 32632'],18)
    rect(835,691,15,15,NAVY);text(860,704,'Building aggregate',16)
    rect(835,724,15,15,'#bedde7');text(860,737,'Event evidence',16)
    assert len(D['context']['buildings']['features'])==1130 and len(D['context']['flood']['features'])==17
    save('06_torino_context','Source: retained BDTRE and Arpa Piemonte WFS responses; original query extent and feature identities preserved.','Context only. These polygons are not matched to benchmark IFCs and do not establish water depth or current flood probability.')


if __name__=='__main__':
    for f in [workflow,geometry,validation,outcomes,source_audit,context]: f()
    print('Created six SVG and high resolution PNG figures in '+str(FIG))
