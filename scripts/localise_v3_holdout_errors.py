from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
from ifc_citygml.common import write_json
from ifc_citygml_lab.metrics import read_geometry
from ifc_citygml_v3.diagnostics import topology,contact_interface_exposure
folder=ROOT/'results/v3/holdout';rows=[]
for row in json.loads((folder/'index.json').read_text())['cases']:
    if row['method']!='v3_constrained' or row['status']!='accepted' or row['reference_passed']:continue
    report=json.loads((folder/row['report']).read_text());mesh=read_geometry((folder/row['output']).read_bytes())['mesh']
    rows.append({'case':row['case'],'failed_reference_guards':[k for k,v in row['metrics']['guards'].items() if not v],
        'topology':topology(mesh),'contact_interface_diagnostics':contact_interface_exposure(report['source_evidence'],report['extraction'],report['relations']['relations']),
        'scope':'Known holdout errors inspected after evaluation; this diagnostic is not used to claim corrected heldout performance'})
write_json(ROOT/'results/v3/holdout_error_localisation.json',{'status':'post_evaluation_diagnosis','cases':rows,'method_retuned':False});print('Localised',len(rows),'accepted reference failures')
