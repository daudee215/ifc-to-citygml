from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src'),str(ROOT/'scripts')]
from evaluate_v3_external import scan_audit
from ifc_citygml.common import write_json,digest
rows=[]
for path in sorted((ROOT/'data/raw/v3_sum4re').glob('*.ifc')):
    scan=path.with_name(path.stem+'_HL2.laz');row={'ifc':path.relative_to(ROOT).as_posix(),'ifc_sha256':digest(path),'publisher_filename_pair_found':scan.exists(),'independent_registration_and_reference_status':'not established'}
    if scan.exists():row['scan']=scan_audit(scan)
    rows.append(row)
write_json(ROOT/'results/v3/scan_reference_audit.json',{'status':'metadata_audit_completed','pairs':rows,'no_accuracy_or_semantic_truth_claim':True});print('Audited',len(rows),'filename pairings; registration remains unverified')
