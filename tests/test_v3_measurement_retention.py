from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from ifc_citygml_v3 import safe_benchmark
from ifc_citygml_v3.policy import Policy
from ifc_citygml_lab.fixtures import create_case
def test_measurement_exception_preserves_geometry_and_ledger(tmp_path,monkeypatch):
    path=tmp_path/'r.ifc';case=create_case(path,'rectangle');case['mechanism']='test';output=tmp_path/'output';output.mkdir()
    def fail(*args):raise RuntimeError('Injected measurement failure')
    monkeypatch.setattr(safe_benchmark,'compare_export',fail);policies={k:Policy().to_dict() for k in ['v3_no_repair','v3_constrained']}
    rows=safe_benchmark.worker((case,str(output),policies))
    assert len(rows)==3
    for row in rows:
        assert row['status']=='execution_failed' and row['failed_stage']=='reference_measurement' and row['conversion_status']=='accepted'
        assert (output/row['output']).is_file()
        report=json.loads((output/row['report']).read_text());assert report['source_evidence'] and report.get('source_links')
