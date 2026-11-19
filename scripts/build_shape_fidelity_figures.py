"""Palatino figures for the new measured geometric fidelity experiment."""
import json
from pathlib import Path
import build_palatino_figures as p

b=p.b
ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'results/experiments/shape_fidelity_001'
b.OUT=ROOT/'reports/shape_fidelity_001';b.FIG=b.OUT/'figures';b.FIG.mkdir(parents=True,exist_ok=True)
rows=json.loads((RESULT/'evaluation.json').read_text())['rows']
labels={'rectangle':'Rectangle','l_shape':'L shape','u_shape':'U shape','courtyard':'Courtyard','setback':'Setback'}
lookup={(r['shape_family'],r['yaw_degrees'],r['mode'],r['units']):r for r in rows}


def heatmap():
    p.start(7,'How much does a bounding block add','Footprint area above the analytical reference   ·   Same five designs at three rotations')
    for j,angle in enumerate([0,30,45]):b.text(507+j*245,235,f'{angle}° rotation',22,b.NAVY,anchor='middle')
    for i,family in enumerate(labels):
        y=267+i*86;b.text(55,y+43,labels[family],23,b.NAVY)
        for j,angle in enumerate([0,30,45]):
            r=lookup[(family,angle,'block','metre')];v=r['footprint']['area_overestimate_percent'];alpha=min(v/210,1)
            rgb=[round(244*(1-alpha)+a*alpha) for a in (76,114,113)];color='#'+''.join(f'{a:02x}' for a in rgb)
            x=385+j*245;b.rect(x,y,238,73,color,3)
            b.text(x+119,y+47,f'+{max(0,v):.1f}%',27,'white' if v>175 else b.NAVY,anchor='middle')
    b.text(55,743,'The box matches its declared bounds in all 30 controls, while shape fidelity varies strongly.',20,b.MUTED)
    p.save('07_block_footprint_bias','Source: shape_fidelity_001 primary evaluation. Metre inputs shown; millimetre counterparts are identical.','Percentages describe geometric overestimation in controlled designs, not errors measured on real Torino buildings.')


def footprint():
    p.start(8,'What the block removes from the plan','Unrotated controls   ·   Reference footprint within the actual exported bounding footprint')
    for i,family in enumerate(labels):
        x=55+i*220
        b.text(x,247,labels[family],23,b.NAVY)
        expected=json.loads((ROOT/f'data/derived/shape_fidelity_001/{family}_yaw0_m.expected.json').read_text())
        ref=expected['footprint'];block=lookup[(family,0,'block','metre')]['footprint_geojson']
        scale=14.;ox=x+7;oy=330
        def path(poly,fill,stroke):
            data=''
            for ring in poly['coordinates']:
                coords=[(ox+(a-100)*scale,oy+(10-(c-200))*scale) for a,c in ring]
                data+='M'+' L'.join(f'{a},{c}' for a,c in coords)+'Z '
            b.parts.append(f'<path d="{data}" fill="{fill}" stroke="{stroke}" stroke-width="1.7" fill-rule="evenodd"/>')
        path(block,'#efe8dd','#bba482');path(ref,'#b4c9c4',b.TEAL)
        row=lookup[(family,0,'block','metre')]
        b.lines(x,568,[f"Area +{max(0,row['footprint']['area_overestimate_percent']):.1f}%",f"Volume +{max(0,row['volume']['overestimate_percent']):.1f}%"],21,b.MUTED,34)
    b.rect(55,694,18,18,'#b4c9c4');b.text(85,710,'Analytical reference',20,b.NAVY)
    b.rect(445,694,18,18,'#efe8dd');b.text(475,710,'Additional area inside the block',20,b.NAVY)
    p.save('08_plan_shape_loss','Source: declared reference dimensions and exported block GML. Equal plan scale across all five designs.','The setback has the same footprint as its block, but the box overestimates volume by 60%. Plan agreement alone is insufficient.')


def sensitivity():
    p.start(9,'Separating the two numerical tolerances','Post hoc courtyard diagnostic   ·   Union grid and validator snapping varied independently')
    grids=[1e-6,1e-7,1e-8,1e-9];snaps=[1e-6,1e-9]
    results=json.loads((RESULT/'diagnostics/courtyard_grid_sensitivity.json').read_text())['rows']
    for j,label in enumerate(['1 micrometre','0.1 micrometre','0.01 micrometre','0.001 micrometre']):b.text(437+j*198,261,label,18,b.NAVY,anchor='middle')
    b.text(55,209,'Union grid',21,b.NAVY)
    for i,snap in enumerate(snaps):
        y=307+i*133
        b.lines(55,y+34,['Validator snapping','1 micrometre' if i==0 else '0.001 micrometre'],20,b.MUTED)
        for j,grid in enumerate(grids):
            matches=[r for r in results if r['union_grid_m']==grid and r['validator_snap_m']==snap]
            assert len(matches)==2 and matches[0]['target_surface_status']==matches[1]['target_surface_status']
            passed=matches[0]['target_surface_status']=='passed';x=340+j*198
            b.rect(x,y,187,103,'#d9e6e1' if passed else '#ecded4',3)
            b.text(x+93,y+43,'Passed' if passed else 'Failed',24,b.TEAL if passed else b.RUST,anchor='middle')
            b.text(x+93,y+76,'Both units' if passed else 'Error 102',18,b.MUTED,anchor='middle')
    b.lines(55,652,['The original candidate contains two edges about 0.094 micrometres long.','Fourteen of 16 checks pass. The two registered primary failures remain failed.'],22,b.NAVY,37)
    p.save('09_courtyard_numerical_sensitivity','Source: retained diagnostic candidates and all 16 independent validator reports. Metre and millimetre results agree.','These are exploratory settings, not an adopted converter policy or a new estimate of real building accuracy.')


if __name__=='__main__':
    for f in [heatmap,footprint,sensitivity]:f()
    print(b.FIG)
