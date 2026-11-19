"""Portable, source-linked WebGL inspection of actual research meshes."""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
from ifc_citygml_lab.metrics import read_geometry
OUT=ROOT/'reports/expansion_v2';OUT.mkdir(parents=True,exist_ok=True)

def build():
    index=json.loads((ROOT/'results/expansion_v2/smoke/index.json').read_text())
    if index['status']!='completed':raise ValueError('Viewer needs a completed run')
    cases={}
    for row in index['cases']:
        if not row['case'].endswith('_m') or '_b0_' not in row['case']:continue
        report_path=ROOT/'results/expansion_v2/smoke'/row['report'];report=json.loads(report_path.read_text())
        expected=ROOT/'data/derived/expansion_v1/smoke'/(row['case']+'.expected.json')
        case=cases.setdefault(row['case'],{'family':row['family'],'methods':{},'reference':json.loads(expected.read_text())['reference_mesh'],'source':[]})
        if not case['source']:
            case['source']=[{'vertices':e['vertices'],'triangles':e['triangles'],'guid':e['ifc_global_id']} for b in report['source_evidence']['buildings'] for e in b['elements']]
        components=[]
        serialized=read_geometry((ROOT/'results/expansion_v2/smoke'/row['output_file']).read_bytes())['components'] if row.get('output_file') else []
        serial_index=0
        for b,l in zip(report.get('extraction',{}).get('buildings',[]),report.get('source_links',[])):
            contributions=l['surface_contributions'];cursor=0
            for c in b['components']:
                n=len(c['triangles']);mesh=serialized[serial_index];serial_index+=1
                if len(mesh['triangles'])!=n:raise ValueError('Serialized face correspondence changed')
                components.append({**mesh,'face_sources':[p['ifc_global_id'] for p in contributions[cursor:cursor+n]]});cursor+=n
        case['methods'][row['backend']]={'components':components,'summary':row,'report':'../../results/expansion_v2/smoke/'+row['report'].replace('\\','/'),'relations':report.get('ledger',{}).get('source_graph',{}).get('geometric_relations',[])}
    template=(ROOT/'research/inspection_viewer.html').read_text(encoding='utf-8')
    (OUT/'Geometry_Inspection.html').write_text(template.replace('__DATA__',json.dumps(cases,separators=(',',':')).replace('</','<\\/')),encoding='utf-8')
    print('Built viewer',len(cases),'cases; all geometry embedded')

if __name__=='__main__':build()
