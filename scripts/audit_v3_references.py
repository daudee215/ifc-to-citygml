"""Re-audit historical cases without modifying their IFCs, references or outputs."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
from ifc_citygml_v3.references import corrected_expected
from ifc_citygml_lab.metrics import compare_export,mesh_statistics
from ifc_citygml.common import write_json,digest
def main():
    folder=ROOT/'results/v3/reference_audit';folder.mkdir(parents=True,exist_ok=False);rows=[]
    for row in json.loads((ROOT/'reports/expansion_v2/Results_Summary.json').read_text())['locked_guarded_counterexamples']:
        report_path=ROOT/'results/expansion_v2/locked'/row['report'];report=json.loads(report_path.read_text());oldpath=Path(report['input']).with_suffix('.expected.json');old=json.loads(oldpath.read_text());new=corrected_expected(old)
        write_json(folder/(row['case']+'.corrected_reference.json'),new)
        metrics=compare_export((report_path.parent/report['output_file']).read_bytes(),new,512)
        record={'case':row['case'],'original_reference_sha256':digest(oldpath),'corrected_reference_sha256':digest(folder/(row['case']+'.corrected_reference.json')),
            'old_reference_stats':mesh_statistics(old['reference_mesh']),'new_reference_stats':mesh_statistics(new['reference_mesh']),
            'original_reference_all_guards':row['reference_all_guards'],'corrected_metrics':metrics,
            'interpretation':'Historical reference-induced failure' if metrics['all_guards_passed'] else 'Failure persists under corrected analytical reference',
            'evaluation_role':'Historical diagnosis, not fresh validation'}
        rows.append(record);print(row['case'],record['interpretation'],flush=True)
    write_json(folder/'index.json',{'status':'completed','cases':rows,'references_corrected_not_original_artifacts':True})
if __name__=='__main__':main()
