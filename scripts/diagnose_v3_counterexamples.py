"""Retained three-stage counterexample dossiers; measurements are not causal guesses."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
from ifc_citygml_lab.metrics import read_geometry,sampled_surface_distance,mesh_statistics
from ifc_citygml.common import write_json,digest

def source_mesh(report):
    vertices=[];faces=[]
    for b in report['source_evidence']['buildings']:
        for e in b['elements']:
            shift=len(vertices);vertices.extend(e['vertices']);faces.extend([[i+shift for i in f] for f in e['triangles']])
    return {'vertices':vertices,'triangles':faces}

def main():
    folder=ROOT/'results/v3/diagnosis';folder.mkdir(parents=True,exist_ok=False)
    old=json.loads((ROOT/'reports/expansion_v2/Results_Summary.json').read_text());rows=[]
    for row in old['locked_guarded_counterexamples']:
        report_path=ROOT/'results/expansion_v2/locked'/row['report'];report=json.loads(report_path.read_text())
        expected_path=Path(report['input']).with_suffix('.expected.json');expected=json.loads(expected_path.read_text());source=source_mesh(report)
        output_path=report_path.parent/report['output_file'];output=read_geometry(output_path.read_bytes())['mesh']
        a=sampled_surface_distance(source,output,512);b=sampled_surface_distance(source,expected['reference_mesh'],512)
        dossier={'case':row['case'],'original_summary':row,'input_sha256':report['input_sha256'],'v2_report_sha256':digest(report_path),
            'source_to_serialized_sampled_distance':a,'all_source_faces_to_design_sampled_distance':b,
            'source_faces_note':'Raw constituent source includes internal interfaces; distance to design is not union-boundary fidelity for multi-element cases.',
            'serialized_mesh':mesh_statistics(output),'source_elements':len(report['source_evidence']['buildings'][0]['elements']),
            'source_relations':report['ledger']['source_graph'].get('geometric_relations',[]),
            'demonstrated':'Accepted serialized output fails retained analytical reference checks',
            'causal_status':'Source-to-output discrepancy demonstrated' if a['sampled_maximum_m']>1e-5 and len(report['source_evidence']['buildings'][0]['elements'])==1 else 'Stage attribution requires boundary/interface-specific checks; no unique cause inferred from aggregate distance'}
        write_json(folder/(row['case']+'.json'),dossier);rows.append(dossier);print(row['case'],'source/output',a['sampled_maximum_m'],'source/design',b['sampled_maximum_m'],flush=True)
    write_json(folder/'index.json',{'status':'completed','dossiers':rows,'preserved_historical_test':True})
if __name__=='__main__':main()
