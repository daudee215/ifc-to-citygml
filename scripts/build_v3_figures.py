"""Twelve Palatino research plates from completed V3 experiments."""
from pathlib import Path
from collections import Counter
import json,math,subprocess
import build_expansion_figures as b
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/v3';FIG=OUT/'figures';FIG.mkdir(parents=True,exist_ok=True);b.OUT=OUT;b.FIG=FIG
T=b.text;R=b.rect;L=b.line;S=b.start;SAVE=b.save
INK,TEAL,RUST,GREY,MUTED,BLUE=b.INK,b.TEAL,b.RUST,b.GREY,b.MUTED,b.BLUE
def load(name):return json.loads((ROOT/'results/v3'/name).read_text())
H=load('holdout/index.json')['cases'];W=load('workflows/index.json');METHODS=['v2_guarded','v3_no_repair','v3_constrained'];LABELS={'v2_guarded':'V2 source-only baseline','v3_no_repair':'V3 · repair disabled','v3_constrained':'V3 · constrained repair'}
def counts(rows):return [sum(r['status']=='accepted' and r['reference_passed'] for r in rows),sum(r['status']=='accepted' and not r['reference_passed'] for r in rows),sum(r['status']=='needs_review' for r in rows),sum(r['status']=='rejected' for r in rows),sum(r['status']=='execution_failed' for r in rows)]

def architecture():
    S(1,'A conversion now carries its decision record','Implemented software layers · Building material targets in engineering metres · Experimental qualification')
    cards=[('01 / Extract',['Selected IFC Body','Units and placements','Explicit omissions']),('02 / Interpret',['Logical connections','Geometric planes','Ambiguous contacts']),('03 / Construct',['Unquantised union','Conditioned union','Bounded plane edit']),('04 / Serialize',['17-digit coordinates','Roundtrip identity','Stable source links']),('05 / Verify',['Schema and solids','Source matches','Reference comparison']),('06 / Decide',['Accepted','Review required','Reject / unsupported'])]
    for i,(title,lines) in enumerate(cards):
        x=80+i*242;R(x,320,220,250,'#e8ede7');T(x+18,367,title,25,TEAL)
        for j,line in enumerate(lines):T(x+18,428+j*44,line,19)
        if i<5:L(x+223,445,x+238,445,TEAL)
    T(80,666,'Parallel research track',28);T(80,714,'Exact CGAL comparisons distinguish arithmetic robustness from the interpretation of source contacts.',25,MUTED)
    T(80,786,'Acceptance remains conditional: the fresh holdout still contains four accepted reference failures.',27,RUST)
    SAVE('01_implemented_architecture','Source: V3 policy, extraction adapter, connections, converter, checks and retained experiment protocols.','The ledger explains implemented decisions; it does not turn finite diagnostic checks into a formal fidelity certificate.')

def reference_audit():
    rows=load('reference_audit/index.json')['cases'];S(2,'Reference auditing changes the historical diagnosis','Eight previously reported accepted failures · Corrected cell arrangement built before scaling')
    T(80,278,'Historical case',23,MUTED);T(700,278,'Old sampled 3D error',23,MUTED);T(1050,278,'Corrected 3D error',23,MUTED);T(1360,278,'Result',23,MUTED)
    for i,r in enumerate(rows):
        y=335+i*61;old=next(x for x in load('diagnosis/index.json')['dossiers'] if x['case']==r['case'])['original_summary']['metrics']['sampled_surface_distance']['sampled_maximum_m'];new=r['corrected_metrics']['sampled_surface_distance']['sampled_maximum_m'];passed=r['corrected_metrics']['all_guards_passed']
        T(80,y,r['case'].replace('locked_',''),24);T(700,y,f'{old:.3f} m',25,RUST);T(1050,y,f'{new:.2e} m',25,TEAL if passed else RUST);T(1360,y,'Pass' if passed else 'Still fails',23,TEAL if passed else RUST);L(80,y+16,1520,y+16)
    T(80,858,'Five failures arose from the analytical reference; three persist and V3 routes those cases to review.',24,TEAL)
    SAVE('02_historical_reference_audit','Source: preserved V2 outputs, corrected reference audit and V3 historical recheck; 512 surface samples per direction.','This is retrospective diagnosis, not fresh validation. Original references, outputs and reports remain unchanged.')

def holdout():
    S(3,'The fresh holdout exposes both capability and limits','160 inputs × three methods · Eight registered mechanisms · All attempts retained')
    states=['Accepted + reference passed','Accepted + reference failed','Review','Rejected','Execution failed'];colors=[TEAL,RUST,BLUE,GREY,'#4b5052']
    for i,(label,c) in enumerate(zip(states,colors)):R(80+i*292,257,16,16,c);T(104+i*292,272,label,18)
    for i,m in enumerate(METHODS):
        rows=[r for r in H if r['method']==m];c=counts(rows);y=350+i*154;T(80,y,LABELS[m],29);x=80
        for value,color in zip(c,colors):R(x,y+25,1380*value/160,50,color);x+=1380*value/160
        T(80,y+111,f'{c[0]} accepted + passed   /   {c[1]} accepted failures   /   {c[2]} review   /   {c[3]} rejected   /   {c[4]} execution failure',23,MUTED)
    SAVE('03_fresh_holdout_accounting','Source: frozen V3 holdout/index.json; same analytical inputs and registered evaluation for all methods.','V2 does not implement declared connection-plane repairs. These aggregate challenge counts are not a matched-task superiority ranking.')

def mechanisms():
    S(4,'Performance depends on the source mechanism','Accepted outputs passing every registered reference guard / 20 inputs in each mechanism')
    for j,m in enumerate(METHODS):T(650+j*340,278,LABELS[m],22,anchor='middle')
    names=['ordinary','tilted','faceted_encoding','logical_connection','geometric_connection','conflicting_connection','protected_gap','party_wall']
    for i,name in enumerate(names):
        y=318+i*64;T(80,y+34,name.replace('_',' ').capitalize(),25)
        for j,m in enumerate(METHODS):
            r=[r for r in H if r['method']==m and r['mechanism']==name];good=counts(r)[0];R(510+j*340,y,280,47,TEAL if good==20 else '#e6eae5');label='Target unsupported' if m=='v2_guarded' and name=='geometric_connection' else f'{good}/20';T(650+j*340,y+33,label,24,'white' if good==20 else INK,'middle')
    SAVE('04_mechanism_results','Source: fresh holdout mechanism labels; tilted cases include new 3D orientations and source encodings.','Logical-only connections do not mandate joining. Conflicting geometry may justify rejection even when material-only geometry resembles its source.')

def repairs():
    S(5,'Connection geometry supports bounded, selective repair','Declared interface planes must agree and meet opposed source supports within the edit budget')
    for i,m in enumerate(METHODS[1:]):
        r=[r for r in H if r['method']==m and r['mechanism']=='geometric_connection'];c=counts(r);y=340+i*165;T(80,y,LABELS[m],30);x=80
        for value,col in zip(c,[TEAL,RUST,BLUE,GREY,'#4b5052']):R(x,y+27,780*value/20,52,col);x+=780*value/20
        T(80,y+118,f'{c[0]}/20 accepted + reference passed',28,TEAL)
    changes=[]
    for row in H:
        if row['method']=='v3_constrained' and row['status']=='accepted':
            d=json.loads((ROOT/'results/v3/holdout'/row['report']).read_text());changes.extend(e['maximum_vertex_change_from_original_m'] for e in d.get('operation_ledger',[]))
    T(1040,367,'100 nm',49,TEAL);T(1040,408,'Maximum allowed edit',24,MUTED)
    T(1040,522,f'{max(changes)*1e9:.2f} nm' if changes else 'No accepted edits',42,TEAL);T(1040,562,'Largest accepted plane projection',22,MUTED)
    T(80,807,'Logical-only and conflicting connection evidence do not authorize an automatic geometric join.',25,RUST)
    SAVE('05_connection_repair_ablation','Source: repair-enabled/disabled holdout outcomes and actual accepted vertex-operation ledgers.','Repair eligibility is source-derived. Reference meshes are consulted only after conversion, never during candidate selection.')

def generalisation():
    selected=next(r for r in W['generalisation'] if r['family']=='cylinder');rows=[r for r in selected['candidates'] if r['status']=='admissible'];S(6,'Query constraints select a simpler curved representation','Cylinder example · 0.2 m sampled boundary limit · 10% volume limit · Components and Euler preserved')
    T(300,281,'792 source triangles',26,anchor='middle');T(735,281,'56 selected triangles',26,TEAL,anchor='middle')
    b.image(OUT/'workflow_cylinder_generalisation_source.png',80,310,420,370);b.image(OUT/'workflow_cylinder_generalisation_target.png',510,310,420,370)
    x0,y0,w,h=1060,340,400,330
    for n in [0,200,400,600,800]:y=y0+h-n/800*h;L(x0,y,x0+w,y);T(x0-15,y+6,n,18,MUTED,'end')
    for r in rows:
        x=x0+min(.2,r['sampled_boundary_maximum_m'])/.2*w;y=y0+h-r['triangles']/800*h;b.parts.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{TEAL}"/>');T(x+12,y-9,r['triangles'],21)
    T(1060,318,'Output triangles',20,MUTED)
    for value in [0,.1,.2]:T(x0+value/.2*w,705,f'{value:g} m',18,MUTED,'middle')
    T(1260,753,'Sampled boundary error →',20,MUTED,'middle');T(80,798,'A courtyard block is rejected: fewer faces do not justify closing its protected void.',28,RUST)
    SAVE('06_query_constrained_generalisation','Source: retained cylinder simplification candidates and courtyard query guards; depth-rendered actual GML.','Errors are finite sampled measurements, not certified global bounds. Generalised output carries a different contract from strict material conversion.')

def incremental():
    rows=W['revisions'];S(7,'Revision reuse agrees with complete rebuilding','Five buildings · Five revision states · Canonical geometry, source lineage and decisions checked')
    T(390,278,'Building reuse',25,anchor='middle');T(1100,278,'Observed computation time',25,anchor='middle')
    for i,r in enumerate(rows):
        y=325+i*101;reused=len(r['reused_buildings']);recomputed=len(r['recomputed_buildings']);T(80,y+32,f'Revision {i}',25);R(255,y,450*reused/5,40,TEAL);R(255+450*reused/5,y,450*recomputed/5,40,GREY);T(730,y+29,f'{reused} reused',23)
        a=r['incremental_wall_seconds_before_rebuild_check'];z=r['full_rebuild_wall_seconds'];scale=480/7;R(950,y,scale*a,17,TEAL);R(950,y+24,scale*z,17,BLUE);T(1450,y+16,f'{a:.2f}s',19,TEAL);T(1450,y+42,f'{z:.2f}s',19,BLUE)
    T(80,854,'All five rebuild checks pass. Incremental overhead is slower for some small edits; no-change reuse is faster.',23,MUTED)
    SAVE('07_incremental_rebuild_agreement','Source: actual building-level cache/rebuild demonstrations; teal = incremental stage, blue = separate full rebuild.','Times were observed under background load. These small examples do not establish production throughput or general speedup.')

def indexing():
    rows=load('index_scaling.json')['cases'];S(8,'Spatial indexing removes provably irrelevant pairs','Synthetic AABB strip · Only neighbouring bounds can interact within the declared edit budget')
    x0,y0,w,h=200,325,1000,470
    def xy(n,p):return x0+(math.log10(n)-2)/(math.log10(5000)-2)*w,y0+h-(math.log10(p)-1)/7*h
    for e in [2,3,4,5,6,7]:y=y0+h-(e-1)/7*h;L(x0,y,x0+w,y);T(170,y+7,f'10^{e}',20,MUTED,'end')
    for field,color in [('all_possible_pairs',BLUE),('indexed_pairs',TEAL)]:
        points=[xy(r['elements'],r[field]) for r in rows];b.parts.append('<path d="M'+' L'.join(f'{x},{y}' for x,y in points)+f'" fill="none" stroke="{color}" stroke-width="3"/>')
        for (x,y),r in zip(points,rows):b.parts.append(f'<circle cx="{x}" cy="{y}" r="6" fill="{color}"/>');T(x,y-15,f'{r[field]:,}',19,color,'middle')
    for r in rows:x,_=xy(r['elements'],100);T(x,834,f'{r["elements"]:,}',21,MUTED,'middle')
    T(1250,390,'All pairs',24,BLUE);T(1250,640,'Indexed pairs',24,TEAL);T(80,270,'Pair count · log scale',22,MUTED);T(710,873,'Elements · log scale',22,MUTED,'middle')
    SAVE('08_interaction_index_scaling','Source: measured index-only benchmark; all four known strip adjacency sets matched exactly.','This is broad-phase indexing, not full IFC conversion. A pair is pruned only by the declared distance/influence rule.')

def exact():
    rows=load('exact_comparison/index.json')['cases'];S(9,'Exact arithmetic preserves input geometry, not intent','Locally compiled CGAL 6.2.1 · Rational constructions on represented binary-double source coordinates')
    T(80,276,'Case',23,MUTED);T(520,276,'Observed runtime · 0–90 s',23,MUTED);T(1140,276,'Comparison outcome',23,MUTED)
    for i,r in enumerate(rows):
        y=320+i*71;seconds=r.get('wall_seconds',0);ok=r['status']=='completed';T(80,y+27,r['case'].replace('locked_',''),23);R(520,y,530*min(seconds,90)/90,33,TEAL if ok else GREY);T(1070,y+25,f'{seconds:.2f}s',20,MUTED)
        outcome='Design checks pass' if ok and r.get('reference_metrics',{}).get('all_guards_passed') else 'Source/design differ' if ok else 'Timed out';T(1190,y+26,outcome,21,TEAL if outcome=='Design checks pass' else RUST)
    T(80,862,'Six unions complete; one exceeds 90 s. Exact logging is checked separately on replayed controls.',24,MUTED)
    SAVE('09_exact_geometry_comparison','Source: pinned native build/logs and serialized GML checks. Exact-limb logging is audited separately.','The native comparison has no qualified per-face IFC attribution and is not promoted as the production conversion backend.')

def external():
    initial=load('external/index.json')['cases'];adapt=load('schema_adapter/index.json')['cases'];bounded=load('bounded_adapter/index.json')['cases'];names=['Anoeta','Donor','Jolastokieta','Longyearbyen','Target'];S(10,'External applicability remains a clear qualification gap','Five new SUM4Re IFCs and matching-by-name HL2 scans · CC BY 4.0 · No independent registration established')
    for x,label in [(640,'Initial strict profile'),(990,'IFC4X3 development'),(1340,'Resource-bounded follow-up')]:T(x,278,label,21,anchor='middle')
    def find(rows,name):return next(r for r in rows if r.get('case',Path(r.get('input','')).stem)==name)
    for i,name in enumerate(names):
        y=335+i*91;T(80,y+35,name,29)
        for j,rows in enumerate([initial,adapt,bounded]):
            r=find(rows,name);status=r['status'];label='Time out' if status.startswith('timeout') else 'Rejected' if status=='rejected' else 'Memory failure' if 'MemoryError' in str(r.get('error')) else 'Unsupported';R(490+j*350,y,300,48,GREY);T(640+j*350,y+33,label,23,RUST,'middle')
    T(80,848,'No strict material-union output from this new external collection is qualified by these trials.',26,RUST)
    SAVE('10_external_applicability','Source: initial fresh applicability trial and separately labelled development follow-ups; every timeout retained.','The bounded adapter refuses excessive source complexity without truncation. Scan pairing does not establish survey accuracy or semantic truth.')

def sensitivity():
    d=load('workflows/urban_sensitivity.json');S(11,'Representation changes the same fixed-hazard query','Synthetic courtyard · Identical hazard geometry, feature identity and declared coordinate frame')
    x0,y0,scale=100,320,43
    def ring(points):return 'M'+' L'.join(f'{x0+(x-100)*scale},{y0+(210-y)*scale}' for x,y in points)+' Z'
    source=[[(100,200),(112,200),(112,210),(100,210),(100,200)],[(103,203),(103,207),(109,207),(109,203),(103,203)]]
    b.parts.append('<path d="'+' '.join(ring(r) for r in source)+f'" fill="{TEAL}" fill-rule="evenodd"/>')
    b.parts.append('<path d="'+ring([(105,202),(108,202),(108,209),(105,209),(105,202)])+f'" fill="{BLUE}" fill-opacity=".6" stroke="{INK}"/>')
    for i,(name,label) in enumerate([('material_union','Material union'),('block','Bounding block')]):
        value=d['baseline_profiles'][name]['union_exposed_area_m2'];y=360+i*185;T(850,y,label,31);R(850,y+28,520*value/21,45,TEAL if i==0 else RUST);T(1410,y+60,f'{value:g} m²',30)
    T(850,763,'Difference: +12 m²',34,RUST);T(850,814,'The selected ±0.1 m scenarios leave both values unchanged.',20,MUTED)
    SAVE('11_fixed_hazard_query_effect','Source: workflow/urban_sensitivity.json; raw hazard identity is fixed across all profiles and scenarios.','This is a controlled conversion-sensitivity example, not a Torino building, water-depth estimate, probability interval or damage prediction.')

def geometry():
    S(12,'The figures are linked to actual converted geometry','Depth-buffer rendering · Shared camera and physical scale within each source/output/reference row')
    for j,label in enumerate(['IFC source','Serialized output','Analytical reference']):T(400+j*425,269,label,26,anchor='middle')
    for i,(key,label) in enumerate([('v3_holdout_0064_ordinary','Gable roof'),('v3_holdout_0017_tilted','Tilted U shape'),('workflow_cylinder_generalisation','Simplified cylinder')]):
        y=294+i*185;T(80,y+92,label,22)
        for j,view in enumerate(['source','target','reference']):b.image(OUT/(key+'_'+view+'.png'),225+j*425,y,375,181)
    SAVE('12_actual_geometry_comparisons','Source: source-linked V3 viewer and actual GML; the cylinder is selected under its separate measured query contract.','Colours identify source elements or components. No independently reviewed semantic classification accuracy is implied.')

def main():
    for fn in [architecture,reference_audit,holdout,mechanisms,repairs,generalisation,incremental,indexing,exact,external,sensitivity,geometry]:fn()
    for name in b.sources:
        subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless','--disable-gpu','--hide-scrollbars','--force-device-scale-factor=2','--window-size=1600,1000',f'--screenshot={FIG/(name+".png")}',(FIG/(name+'.svg')).as_uri()],capture_output=True,timeout=40,check=True)
    (OUT/'figure_index.json').write_text(json.dumps({'figures':b.sources,'font':'Palatino Linotype','formats':['SVG','3200x2000 PNG'],'planned_results_included':False},indent=2));print('Created',len(b.sources),'research figures')
if __name__=='__main__':main()
