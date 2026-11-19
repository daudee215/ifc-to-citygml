"""Six new Palatino plates explaining the local-frame experiment and its limits."""
import json
import math
from pathlib import Path
import build_palatino_figures as p

b=p.b;ROOT=b.ROOT;EXP=ROOT/'results/experiments/local_frame_003';OUT=ROOT/'reports/local_frame_003'
OUT.mkdir(exist_ok=True);b.OUT=OUT;b.FIG=OUT/'figures';b.FIG.mkdir(exist_ok=True)
D=json.loads((EXP/'evaluation.json').read_text());F=['rectangle','l_shape','u_shape','courtyard','setback'];A=[0,15,22.5,30,45,60,67.5,75]
LABEL={'rectangle':'Rectangle','l_shape':'L shape','u_shape':'U shape','courtyard':'Courtyard','setback':'Setback'}
BASE={(r['shape_family'],r['yaw_degrees'],r['units']):r for r in D['baseline']};CAND={(r['shape_family'],r['yaw_degrees'],r['units']):r for r in D['candidate']}

def path(coords,x,y,scale,origin,fill,stroke):
    d=' '.join('M'+' L'.join(f'{x+(a-origin[0])*scale},{y-(c-origin[1])*scale}' for a,c in ring)+'Z' for ring in coords)
    b.parts.append(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="2" fill-rule="evenodd"/>')

def method():
    p.start(11,'Preserve the building frame through the Boolean union','World geometry → local building placement → snap and union → restored world geometry')
    row=CAND['u_shape',22.5,'metre'];detail=json.loads((EXP/'candidate'/row['report']).read_text())
    frame=detail['extraction']['research_frame_policy']['frames'][0]['matrix_local_to_world']
    coords=row['metrics']['footprint']['coordinates']
    local=[[( (a-frame[0][3])*frame[0][0]+(c-frame[1][3])*frame[1][0], (a-frame[0][3])*frame[0][1]+(c-frame[1][3])*frame[1][1]) for a,c in ring] for ring in coords]
    for i,(title,subtitle) in enumerate([('World frame','U shape rotated by 22.5°'),('Building frame','Snap and union before restoring'),('World output','Restore the rigid placement')]):
        x=55+i*370;b.text(x,243,title,26,b.NAVY);b.text(x,280,subtitle,18,b.MUTED)
        if i==1:path(local,x+150,468,16,(6,4),'#bdd0c8',b.TEAL)
        else:
            cx=frame[0][3]+6*frame[0][0]+4*frame[0][1];cy=frame[1][3]+6*frame[1][0]+4*frame[1][1]
            path(coords,x+150,468,16,(cx,cy),'#dde5e1' if i==0 else '#bdd0c8',b.TEAL)
        b.line(x+20,573,x+105,573,b.BLUE,2);b.line(x+20,573,x+20,518,b.BLUE,2)
        b.text(x+115,580,'x' if i!=1 else 'x local',17,b.BLUE)
        if i<2:b.arrow(x+320,445,x+352,445,b.MUTED)
    b.lines(55,665,['The 1 µm union grid and the 1 µm validator snapping tolerance remain fixed.',
                       'No post union simplification is used. The output returns to the original engineering metre frame.'],22,b.NAVY,36)
    p.save('11_local_frame_method','Source: actual U shape 22.5° candidate footprint and IFC building placement. Every plan uses the same scale.','The adapter explicitly rejects tilted or nonrigid building placements. It performs no geographic transformation.')

def edge():
    p.start(12,'A 22 nanometre edge explains a rejected U shape','Retained study 002 fine grid candidate at 45°   ·   Actual edge endpoints   ·   Local XY enlargement')
    report=json.loads((ROOT/'results/experiments/shape_fidelity_002/candidate/u_shape_yaw45_m.report.json').read_text())
    vertices=report['extraction']['buildings'][0]['components'][0]['vertices']
    a,c=vertices[0],vertices[0];shortest=float('inf')
    for comp in report['extraction']['buildings'][0]['components']:
        for face in comp['triangles']:
            for i,j in zip(face,face[1:]+face[:1]):
                v,w=comp['vertices'][i],comp['vertices'][j];length=math.dist(v,w)
                if length<shortest:shortest=length;a,c=v,w
    origin=[(a[i]+c[i])/2 for i in range(3)]
    def xy(v):return (350+(v[0]-origin[0])*1e9*9,425-(v[1]-origin[1])*1e9*9)
    for offset in [-20,-10,0,10,20]:
        b.line(350+offset*9,228,350+offset*9,621,b.LINE,1);b.line(150,425-offset*9,550,425-offset*9,b.LINE,1)
        b.text(350+offset*9,656,str(offset),17,b.MUTED,anchor='middle')
        b.text(137,431-offset*9,str(offset),17,b.MUTED,anchor='end')
    b.parts.append(f'<text x="80" y="425" transform="rotate(-90 80 425)" font-size="18" fill="{b.MUTED}" text-anchor="middle">Relative y offset in nanometres</text>')
    va,vc=xy(a),xy(c);b.line(*va,*vc,b.RUST,4)
    for k,(point,v) in enumerate([(va,a),(vc,c)]):
        b.parts.append(f'<circle cx="{point[0]}" cy="{point[1]}" r="6" fill="{b.RUST}"/>');b.text(point[0]+15,point[1]-10,'A' if k==0 else 'B',23,b.RUST)
    b.text(350,703,'Relative x offset in nanometres',20,b.MUTED,anchor='middle')
    b.lines(650,267,[f'Edge length {shortest*1e9:.2f} nm','Validator snapping 1,000 nm','Failure code 102'],25,b.NAVY,49)
    b.lines(650,455,['The endpoints are distinct in the export,','but closer than the snapping tolerance.','Simplification leaves this edge unchanged.'],21,b.MUTED,34)
    b.lines(650,610,['The local frame candidate has','one component and no sub µm edges.'],22,b.TEAL,34)
    p.save('12_short_edge_diagnostic','Source: retained rejected U shape 45° rings and the reproduced unsuccessful simplification probe.','This is a numerical geometry diagnostic. The enlarged edge is not a visible 22 nm building defect or a survey measurement.')

def outcomes():
    p.start(13,'The local frame candidate passes the angular extension','Declared MultiSurface and stronger Solid checks   ·   Validator snapping remains 1 µm')
    for i,(cohort,label,n) in enumerate([('earlier_controls','Earlier controls',60),('prospective_angles','New angle controls',20)]):
        y=281+i*187;b.text(55,y,label,25,b.NAVY)
        for j,(rows,color,label2) in enumerate([(D['baseline'],b.BLUE,'World frame'),(D['candidate'],b.TEAL,'Local frame')]):
            passed=sum(r['status']=='passed' for r in rows if r['cohort']==cohort)
            b.text(55,y+44+j*46,label2,20,b.MUTED);b.rect(320,y+22+j*46,passed/n*650,27,color)
            b.text(995,y+45+j*46,f'{passed}/{n}',25,color)
    b.lines(55,703,['Combined result: baseline 70/80, local frame 80/80. All 80 candidate cases meet the recorded guards.'],23,b.NAVY)
    p.save('13_controlled_validation','Source: 80 matched exterior inputs. New controls use 22.5° and 67.5°, five designs and two units.','The protocol records the earlier inspected prototype. New angles extend these same designs; they are not independent buildings.')

def topology():
    p.start(14,'Valid surfaces can still lose the intended topology','Baseline component count → local frame component count   ·   Cell colour tests baseline components and Euler characteristic')
    for j,a in enumerate(A):b.text(310+j*108,237,f'{a:g}°',20,b.NAVY,anchor='middle')
    for i,f in enumerate(F):
        y=271+i*77;b.text(55,y+42,LABEL[f],23,b.NAVY)
        for j,a in enumerate(A):
            old=BASE[f,a,'metre']['mesh_audit'];new=CAND[f,a,'metre']['mesh_audit']
            good=old['components']==1 and old['euler_sum']==(0 if f=='courtyard' else 2)
            x=260+j*108;b.rect(x,y,102,69,'#d3e2dc' if good else '#ead7cd',2)
            b.text(x+51,y+43,f"{old['components']} → {new['components']}",24,b.NAVY,anchor='middle')
    b.lines(55,708,['Expected topology: one connected shell; Euler characteristic 0 for the courtyard and 2 for the other forms.',
                       'Only 44/80 baseline cases match it, including 44/70 valid outputs. The candidate matches it in 80/80.'],21,b.NAVY,32)
    p.save('14_topology_correspondence','Source: extracted component meshes, including failed exports. Metre cases shown; unit counterparts agree.','Euler characteristic is a diagnostic, not a complete proof of topology. Independent Solid checks provide additional evidence.')

def minimum_edges():
    p.start(15,'Short edges disappear in the local frame controls','Minimum exported mesh edge length   ·   Five known failing configurations   ·   Metre inputs')
    pairs=[('u_shape',15),('u_shape',60),('u_shape',75),('courtyard',22.5),('courtyard',30)]
    x0=430;x1=1060
    def xx(v):return x0+(math.log10(v)+9)/10*(x1-x0)
    for power in [-9,-6,-3,0,1]:
        x=xx(10**power);b.line(x,259,x,640,b.LINE,1)
        b.parts.append(f'<text x="{x}" y="680" font-size="18" fill="{b.MUTED}" text-anchor="middle">10<tspan baseline-shift="super" font-size="12">{power}</tspan></text>')
    threshold=xx(1e-6);b.line(threshold,250,threshold,649,b.RUST,2,'5 5');b.text(threshold,228,'Validator snapping',18,b.RUST,anchor='middle')
    for i,(f,a) in enumerate(pairs):
        y=293+i*64;old=BASE[f,a,'metre']['mesh_audit']['minimum_edge_m'];new=CAND[f,a,'metre']['mesh_audit']['minimum_edge_m']
        b.text(55,y+7,f'{LABEL[f]} at {a:g}°',22,b.NAVY);b.line(xx(old),y,xx(new),y,b.MUTED,2)
        for v,color in [(old,b.RUST),(new,b.TEAL)]:b.parts.append(f'<circle cx="{xx(v)}" cy="{y}" r="5" fill="{color}"/>')
    b.text(747,725,'Edge length in metres on a logarithmic scale',20,b.MUTED,anchor='middle')
    p.save('15_minimum_edge_lengths','Source: the five baseline configurations with failure 102, each paired to its local frame candidate.','Rust marks world frame results; green marks local frame results. These selected failure cases do not describe a population distribution.')

def external():
    p.start(16,'Public benchmark files constrain the generalisation','Exploratory external check   ·   The same fixed local frame adapter   ·   Original engineering coordinate policies')
    data=json.loads((EXP/'external/index.json').read_text());assert data['status']=='completed'
    for x,label in [(55,'Benchmark'),(440,'Baseline surface'),(700,'Local frame surface'),(970,'Local frame Solid')]:b.text(x,246,label,21,b.MUTED)
    for i,row in enumerate(data['cases']):
        y=310+i*86;detail=json.loads((EXP/'external'/(row['case']+'.report.json')).read_text())
        name={'duplex':'Duplex','clinic':'Clinic','gaia_renovation':'Gaia','digitalhub':'Digital Hub'}[row['case']]
        b.text(55,y+18,name,25,b.NAVY)
        vals=[row['baseline_status'],row['status'],detail.get('validation',{}).get('independent_general_solid_validation','not reached')]
        for x,val in zip([440,700,970],vals):b.text(x,y+18,val.capitalize(),22,b.TEAL if val=='passed' else b.RUST)
        b.line(55,y+46,1145,y+46,b.LINE,1)
    b.lines(55,708,['Controlled success supports the numerical mechanism. Public benchmark outcomes remain a separate test.'],22,b.NAVY)
    p.save('16_external_applicability','Source: four exploratory re-extractions and independent validations, with all failures retained.','No independent reference envelope, semantic annotations or surveyed geographic control is available for these four files.')

if __name__=='__main__':
    for f in [method,edge,outcomes,topology,minimum_edges,external]:f();print(f.__name__,flush=True)
