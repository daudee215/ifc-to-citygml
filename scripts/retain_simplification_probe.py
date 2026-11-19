"""Reproduce and retain the unsuccessful exploratory simplification probe."""
import json
from pathlib import Path
import shape_fidelity_experiment as first
from union_simplification_research import simplify_extraction
from ifc_citygml.common import load_profile,write_json,digest
from ifc_citygml.exterior_writer import create_exterior_document
from ifc_citygml.validation import validate_document

root=first.ROOT;folder=root/'results/experiments/local_frame_003/exploratory_probe'
if folder.exists():raise FileExistsError('Do not overwrite the probe')
folder.mkdir(parents=True)
source=root/'results/experiments/shape_fidelity_002/candidate/u_shape_yaw45_m.report.json'
detail=json.loads(source.read_text());extraction=simplify_extraction(detail['extraction'])
data,links=create_exterior_document(extraction,load_profile('exterior'))
path=folder/'u_shape_yaw45_m.rejected_probe.gml';path.write_bytes(data)
write_json(folder/'report.json',{'stage':'Post hoc reproduction of the exploratory probe disclosed in study 003 protocol',
    'source_report':str(source.relative_to(root)),'source_report_sha256':digest(source),'output_sha256':digest(path),
    'extraction':extraction,'validation':validate_document(data,1e-6),'source_links':links,
    'conclusion':'The simplifier retains the short edge; this approach was not selected for the prospective experiment.'})
print('Retained unsuccessful simplification probe')
