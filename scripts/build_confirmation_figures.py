"""Ten research plates from measured data, exported geometry and retained failures."""
import base64
import json
import math
from pathlib import Path
import build_palatino_figures as p

b=p.b;ROOT=b.ROOT
OUT=ROOT/'reports/shape_fidelity_002';b.OUT=OUT;b.FIG=OUT/'figures';b.FIG.mkdir(exist_ok=True)
D=json.loads((OUT/'plot_data.json').read_text());F=D['families'];A=D['angles']
L={'rectangle':'Rectangle','l_shape':'L shape','u_shape':'U shape','courtyard':'Courtyard','setback':'Setback'}
BASE={(r['shape_family'],r['yaw_degrees'],r['units'],r['mode']):r for r in D['baseline']}
CAND={(r['shape_family'],r['yaw_degrees'],r['units']):r for r in D['candidate']}

def dot(x,y,color,r=4):b.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>')

def polygon(geom,x,y,scale,cx,cy,fill,stroke):
    polys=geom['coordinates'] if geom['type']=='MultiPolygon' else [geom['coordinates']]
    for poly in polys:
        path=' '.join('M'+' L'.join(f'{x+(a-cx)*scale:.3f},{y-(c-cy)*scale:.3f}' for a,c in ring)+'Z' for ring in poly)
        b.parts.append(f'<path d="{path}" fill="{fill}" stroke="{stroke}" stroke-width="1.1" fill-rule="evenodd"/>')

def save(name,source,note):p.save(name,source,note)

def design():
    p.start(1,'A controlled test of conversion fidelity','Five analytical forms   ·   Six orientations   ·   Two source units   ·   Three exported representations')
    for i,f in enumerate(F):
        x=125+i*225;ref=D['references'][f+'_0']['footprint']
        polygon(ref,x,295,9,106,205,'#c3d4ce',b.TEAL);b.text(x,387,L[f],23,b.NAVY,anchor='middle')
    b.line(55,409,1145,409,b.LINE,1)
    for x,num,title,detail in [(55,'60','Controlled IFC inputs','5 forms × 6 angles × 2 units'),(425,'180','Baseline conversions','Block, exterior and source'),(795,'60','Candidate conversions','Exterior with a finer union grid')]:
        b.text(x,486,num,55,b.TEAL);b.text(x,532,title,24,b.NAVY);b.text(x,568,detail,19,b.MUTED)
    b.lines(55,655,['Initial angles 0°, 30°, 45° were extended with 15°, 60°, 75° under a recorded protocol.',
                       'Every attempt is retained. These are related controls, not 60 independently sampled buildings.'],22,b.NAVY,35)
    save('01_experiment_design','Source: study 001 and study 002 protocols, manifests and all 240 conversion records.','The candidate changes the union grid from 1 µm to 0.1 µm; validator snapping remains 1 µm.')

def gallery():
    p.start(2,'The exported geometry across five building forms','Actual CityGML polygons   ·   Unrotated metre inputs   ·   One camera and one scale for all 15 views')
    for j,title in enumerate(['Bounding block','Exterior surfaces','Source surfaces']):b.text(385+j*295,218,title,23,b.NAVY,anchor='middle')
    for i,f in enumerate(F):
        y=242+i*100;b.text(55,y+53,L[f],22,b.NAVY)
        for j in range(3):
            data=base64.b64encode((OUT/f'model_{i*3+j}.png').read_bytes()).decode()
            b.parts.append(f'<image x="{330+j*295}" y="{y}" width="110" height="100" xlink:href="data:image/png;base64,{data}"/>')
    save('02_exported_geometry_gallery','Source: 15 passed baseline GML outputs. A depth buffer determines visibility; the meshes are unchanged.','These idealised massing controls test geometry. Their IFC element labels are not independent semantic ground truth.')

def plans():
    p.start(3,'Rotation changes the area lost to a bounding block','Exported block footprint overlaid with the analytical building footprint   ·   Equal plan scale in every panel')
    for j,a in enumerate(A):b.text(310+j*150,221,f'{a}°',22,b.NAVY,anchor='middle')
    for i,f in enumerate(F):
        b.text(55,290+i*88,L[f],21,b.NAVY)
        for j,a in enumerate(A):
            ref=D['references'][f+'_'+str(a)]['footprint'];r=BASE[f,a,'metre','block']
            cx=100+6*math.cos(math.radians(a))-5*math.sin(math.radians(a));cy=200+6*math.sin(math.radians(a))+5*math.cos(math.radians(a))
            polygon(r['metrics']['footprint'],310+j*150,289+i*88,4.3,cx,cy,'#efe8dd','#bba482')
            polygon(ref,310+j*150,289+i*88,4.3,cx,cy,'#adc7be',b.TEAL)
    b.rect(55,726,17,17,'#adc7be');b.text(85,742,'Reference',20,b.NAVY)
    b.rect(340,726,17,17,'#efe8dd');b.text(370,742,'Additional block area',20,b.NAVY)
    b.line(865,732,908,732,b.NAVY,2);b.text(925,740,'10 m',18,b.MUTED)
    save('03_rotation_footprints','Source: all 30 metre block exports and declared reference dimensions. Panels are centred without rescaling.','Rotation is an experimental factor. The drawings are local engineering geometry, not a map of Torino.')

def heat(volume=False):
    n=5 if volume else 4
    p.start(n,'Volume inflation reveals losses hidden in the plan' if volume else 'Footprint inflation grows with rotation and concavity',
            'Percent above the analytical building volume' if volume else 'Percent above the analytical building footprint area')
    for j,a in enumerate(A):b.text(330+j*146,233,f'{a}°',22,b.NAVY,anchor='middle')
    maxv=240 if volume else 210
    for i,f in enumerate(F):
        y=265+i*79;b.text(55,y+43,L[f],23,b.NAVY)
        for j,a in enumerate(A):
            r=BASE[f,a,'metre','block']['metrics'];v=100*r['volume']['relative_error'] if volume else r['raw']['area_overestimate_percent']
            t=max(0,min(v/maxv,1));rgb=[round(245*(1-t)+c*t) for c in (76,114,113)]
            b.rect(260+j*146,y,142,74,'#'+''.join(f'{c:02x}' for c in rgb))
            b.text(331+j*146,y+46,f'+{max(0,v):.1f}%',24,'white' if t>.65 else b.NAVY,anchor='middle')
    for k in range(100):
        t=k/99;rgb=[round(245*(1-t)+c*t) for c in (76,114,113)];b.rect(260+k*3,696,3.1,12,'#'+''.join(f'{c:02x}' for c in rgb))
    b.text(260,734,'0%',17,b.MUTED);b.text(560,734,f'+{maxv}%',17,b.MUTED,anchor='end')
    b.text(635,720,'Setback at 0°: area +0%, volume +60%.' if volume else 'Largest footprint increase: U shape at 45°.',21,b.NAVY)
    save(f'0{n}_block_'+('volume' if volume else 'area'),'Source: 60 passed block exports. Metre results shown; millimetre counterparts use the same metre geometry.',
         'Volume is integrated from oriented exported faces and compared with the sum of nonoverlapping reference prism volumes.' if volume else 'The block can match its declared bounding box exactly while substantially changing the building footprint.')

def matrix():
    p.start(6,'A finer union grid moves the validation failures','Paired exterior results   ·   Each half of a cell is one source unit   ·   Fixed validator snapping at 1 µm')
    for panel,title,x,lookup in [(0,'Baseline union grid 1 µm',225,BASE),(1,'Candidate union grid 0.1 µm',735,CAND)]:
        b.text(x+205,231,title,23,b.NAVY,anchor='middle')
        for j,a in enumerate(A):b.text(x+j*67+29,275,f'{a}°',18,b.MUTED,anchor='middle')
        for i,f in enumerate(F):
            if panel==0:b.text(55,324+i*70,L[f],21,b.NAVY)
            for j,a in enumerate(A):
                for k,unit in enumerate(['metre','millimetre']):
                    r=lookup[(f,a,unit,'exterior')] if panel==0 else lookup[(f,a,unit)]
                    passed=r['status']=='passed';xx=x+j*67+k*30;yy=293+i*70
                    b.rect(xx,yy,28,49,'#d3e2dc' if passed else '#ead7cd',2)
                    b.text(xx+14,yy+32,'✓' if passed else '×',20,b.TEAL if passed else b.RUST,anchor='middle')
    b.rect(55,688,18,18,'#d3e2dc');b.text(85,705,'Passed',20,b.NAVY)
    b.rect(255,688,18,18,'#ead7cd');b.text(285,705,'Failed',20,b.NAVY)
    b.text(495,705,'Left half: metres    Right half: millimetres',20,b.MUTED)
    save('06_paired_validation_matrix','Source: 60 baseline and 60 experimental exterior validations. All failures record val3dity error 102.','Error 102 means consecutive points coincide under validator snapping. Unit counterparts agree in every cell.')

def paired():
    p.start(7,'Two more passes conceal two new regressions','The candidate reaches 54 of 60, compared with 52 of 60 for the baseline exterior profile')
    counts={('passed','passed'):0,('failed','passed'):0,('passed','failed'):0,('failed','failed'):0}
    for r in D['candidate']:
        old=BASE[r['shape_family'],r['yaw_degrees'],r['units'],'exterior'];counts[old['status'],r['status']]+=1
    for i,(key,title,color) in enumerate([(('passed','passed'),'Pass retained',b.TEAL),(('failed','passed'),'Failure resolved',b.BLUE),(('passed','failed'),'New failure',b.RUST),(('failed','failed'),'Failure retained',b.AMBER)]):
        x=55+i*285;b.text(x,279,counts[key],62,color);b.text(x,325,title,23,b.NAVY)
    b.line(55,367,1145,367,b.LINE,1)
    b.text(55,421,'Successful exterior conversions by family',24,b.NAVY)
    for i,f in enumerate(F):
        y=465+i*47;b.text(55,y+16,L[f],20,b.NAVY)
        for j,(rows,color) in enumerate([(D['baseline'],b.BLUE),(D['candidate'],b.TEAL)]):
            n=sum(r['status']=='passed' for r in rows if r['shape_family']==f and r['mode']=='exterior')
            b.rect(275,y+j*16,n*43,11,color);b.text(295+n*43,y+j*16+10,f'{n}/12',17,color)
    b.rect(885,483,20,11,b.BLUE);b.text(920,495,'Baseline',20,b.NAVY)
    b.rect(885,526,20,11,b.TEAL);b.text(920,538,'Candidate',20,b.NAVY)
    b.lines(885,602,['Decision','Keep the default','and investigate','short edges.'],20,b.NAVY,28)
    save('07_candidate_transitions','Source: matched case identifiers across all 60 baseline and candidate exterior attempts.','The six candidate failures remain in the evidence. A higher aggregate pass count does not establish a safe replacement.')

def precision():
    p.start(8,'Footprint measurement has its own numerical behaviour','Maximum discrete boundary Hausdorff distance   ·   Only successfully exported baseline surfaces')
    x0=285;x1=1085;y0=300
    def xx(v):return x0+(math.log10(max(v,1e-12))+12)/13*(x1-x0)
    for power in [-12,-9,-6,-3,0,1]:
        x=xx(10**power);b.line(x,255,x,493,b.LINE,1)
        b.parts.append(f'<text x="{x}" y="532" font-size="18" fill="{b.MUTED}" text-anchor="middle">10<tspan baseline-shift="super" font-size="12">{power}</tspan></text>')
    for i,mode in enumerate(['exterior','source']):
        y=y0+i*145;b.text(55,y+9,mode.capitalize(),24,b.NAVY)
        rows=[r for r in D['baseline'] if r['mode']==mode and 'metrics'in r]
        raw=max(r['metrics']['raw']['boundary_hausdorff_m'] for r in rows)
        snapped=max(r['metrics']['measurement_1nm']['boundary_hausdorff_m'] for r in rows)
        b.line(xx(raw),y,xx(snapped),y,b.MUTED,2);dot(xx(raw),y,b.RUST,7);dot(xx(snapped),y,b.TEAL,5)
        b.text(xx(raw),y-22,f'Raw {raw:.3g} m',19,b.RUST,anchor='middle')
        b.text(xx(snapped),y+36,f'1 nm grid {snapped:.3g} m',19,b.TEAL,anchor='middle')
    b.text(680,577,'Distance in metres on a logarithmic scale',20,b.MUTED,anchor='middle')
    b.lines(55,646,['The source maximum is 2 m despite negligible footprint area disagreement.',
                       'Derived planar unions can develop tiny cracks. Both raw and rounded measurements are retained.'],22,b.NAVY,35)
    save('08_measurement_precision','Source: 52 exterior and 60 source exports. The 1 nm grid is applied to derived footprints and references only.','Distances of zero appear at the 10^-12 plotting floor. No IFC or CityGML coordinates are changed by this measurement step.')

def sensitivity():
    p.start(9,'The original courtyard failure depends on both tolerances','Exploratory study 001 diagnostic   ·   Sixteen retained checks   ·   Both source units tested at each setting')
    rows=json.loads((ROOT/'results/experiments/shape_fidelity_001/diagnostics/courtyard_grid_sensitivity.json').read_text())['rows']
    grids=[1e-6,1e-7,1e-8,1e-9]
    for j,label in enumerate(['1 µm','0.1 µm','0.01 µm','0.001 µm']):b.text(455+j*195,266,label,23,b.NAVY,anchor='middle')
    b.text(55,216,'Union grid',21,b.NAVY)
    for i,snap in enumerate([1e-6,1e-9]):
        y=309+i*137;b.lines(55,y+35,['Validator snapping','1 µm' if i==0 else '0.001 µm'],21,b.MUTED)
        for j,grid in enumerate(grids):
            rr=[r for r in rows if r['union_grid_m']==grid and r['validator_snap_m']==snap]
            n=sum(r['target_surface_status']=='passed' for r in rr);x=360+j*195
            b.rect(x,y,185,101,'#d3e2dc' if n==2 else '#ead7cd',2);b.text(x+92,y+45,f'{n}/2 passed',23,b.NAVY,anchor='middle')
            b.text(x+92,y+77,'Both units',18,b.MUTED,anchor='middle')
    b.lines(55,652,['The failing courtyard contains edges about 0.094 µm long, below 1 µm validator snapping.',
                       'Study 002 tests the finer grid on more rotations and reveals new U shape regressions.'],22,b.NAVY,36)
    save('09_tolerance_sensitivity','Source: all 16 diagnostic reports and retained candidate rings from study 001. Fourteen checks pass.','This exploratory matrix motivated the candidate comparison; it is not independent confirmation of a production tolerance.')

def external():
    p.start(10,'External IFC files test a different part of the method','Fresh extraction audits of four public benchmark files   ·   Frozen v0.6 source surface exports')
    cases=b.E['source_audits']['cases'][2:]
    # Values are read from audited per-case records rather than conversion timings.
    values=[]
    for name,case in zip(['Duplex','Clinic','Gaia','Digital Hub'],cases):
        omissions=case['omissions']
        count=len(omissions) if isinstance(omissions,list) else sum(omissions.values()) if isinstance(omissions,dict) else omissions
        values.append((name,case['exported_features'],case['triangles_checked'],count))
    assert [v[3] for v in values]==[81,513,88,209],values
    b.text(55,231,'Benchmark',21,b.MUTED);b.text(385,231,'Represented features',21,b.MUTED);b.text(755,231,'Retained source triangles',21,b.MUTED)
    for i,(name,features,triangles,omits) in enumerate(values):
        y=283+i*92;b.text(55,y+30,name,24,b.NAVY);b.text(55,y+60,f'{omits:,} omissions recorded',17,b.MUTED)
        b.rect(385,y+9,features/2200*240,25,b.BLUE);b.text(398+features/2200*240,y+29,f'{features:,}',20,b.NAVY)
        b.rect(755,y+9,triangles/160000*245,25,b.TEAL);b.text(1015,y+29,f'{triangles:,}',20,b.NAVY)
    b.lines(55,705,['3,838 represented features   ·   286,316 source triangles   ·   891 explicit omissions'],24,b.NAVY)
    save('10_external_source_evidence','Source: independent source preservation audits for Duplex, Clinic, Gaia and Digital Hub. Bar baselines are zero.','Feature and triangle counts describe retained content. They do not imply correct semantics, watertight envelopes or Torino accuracy.')

if __name__=='__main__':
    for f in [design,gallery,plans,lambda:heat(False),lambda:heat(True),matrix,paired,precision,sensitivity,external]:
        f();print(f.__name__,flush=True)
