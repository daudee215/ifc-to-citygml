"""Provenance-first inventory, deduplication and honest data readiness."""
from collections import defaultdict,Counter
from pathlib import Path
import json
import ifcopenshell
from ifc_citygml.common import digest

def inventory(root):
    root=Path(root);rows=[];hashes=defaultdict(list);projects=defaultdict(list)
    paths=[*list((root/'data/raw/benchmarks').rglob('*.ifc')),*list((root/'data/raw/open_corpus').rglob('*.ifc'))]
    for path in sorted(paths):
        metadata_path=next((p/'source_manifest.json' for p in [path.parent,*path.parents] if p.is_relative_to(root) and (p/'source_manifest.json').exists()),path.parent/'source_manifest.json')
        metadata=json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
        if path.stat().st_size>80_000_000:
            import re
            match=re.fullmatch(r'model_(\d+)_(?:arc|structure)',path.stem)
            group='GNI2026_team_'+match.group(1) if metadata.get('record')=='19722012' and match else 'uninspected:'+path.stem
            sha=digest(path);row={'path':path.relative_to(root).as_posix(),'sha256':sha,'bytes':path.stat().st_size,
                'project_group':group,'group_basis':'Publisher identifier; large-model SDK inspection deferred',
                'inspection_status':'deferred_over_80MB_budget','licence':metadata.get('license','unresolved'),
                'source_manifest':metadata_path.relative_to(root).as_posix(),'genuine_torino_building':False,'independent_survey_controls':False}
            rows.append(row);hashes[sha].append(row['path']);projects[group].append(row['path']);continue
        model=ifcopenshell.open(str(path));ids=sorted(p.GlobalId for p in model.by_type('IfcProject') if p.GlobalId)
        applications=[a.get_info() for a in model.by_type('IfcApplication')]
        applications=[{k:str(v) for k,v in a.items() if k in ['Version','ApplicationFullName','ApplicationIdentifier']} for a in applications]
        sha=digest(path);project_key='|'.join(ids) or 'unverified:'+path.parent.name
        if metadata.get('record')=='19722012':
            # Publisher model_N denotes one student team, including discipline exports.
            import re
            match=re.fullmatch(r'model_(\d+)_(?:arc|structure)',path.stem)
            project_key='GNI2026_team_'+match.group(1) if match else 'GNI2026_unresolved'
        elif metadata.get('record')=='6397164':
            project_key='Tafraout_collection_independence_unverified'
        row={'path':path.relative_to(root).as_posix(),'sha256':sha,'bytes':path.stat().st_size,'schema':model.schema,'ifc_project_ids':ids,
            'project_group':project_key,'group_basis':'Publisher team identifier' if metadata.get('record')=='19722012' else 'Conservative collection group' if metadata.get('record')=='6397164' else 'IFC project identifiers; not independently verified',
            'provenance_directory':path.parent.name,'authoring_metadata_self_reported':applications,
            'ifc_buildings':len(model.by_type('IfcBuilding')),'ifc_elements':len(model.by_type('IfcElement')),
            'licence':metadata.get('license',metadata.get('licence','unresolved')),'source_manifest':metadata_path.relative_to(root).as_posix() if metadata_path.exists() else None,
            'genuine_torino_building':False,'independent_survey_controls':False,'semantic_reference':'not supplied'}
        rows.append(row);hashes[sha].append(row['path']);projects[project_key].append(row['path'])
    return {'status':'inventory_completed','files':rows,'file_count':len(rows),'distinct_content_hashes':len(hashes),'project_identifier_groups':len(projects),
        'project_groups':dict(projects),'exact_duplicates':{k:v for k,v in hashes.items() if len(v)>1},
        'independence_note':'Publisher team grouping keeps GNI architectural/structural pairs together. Tafraout collection is conservatively one group. Counts are provenance groups, not independently surveyed buildings. SDK inspection is deferred for files over 80 MB.',
        'torino_readiness':{'status':'context_only','local_ifc_with_controls_found':False,'context_available':True,'conversion_accuracy_evaluation':'awaiting genuinely local IFC and independent control data'},
        'semantic_readiness':{'status':'awaiting_independent_review','annotation_guide_and_importer':'implemented separately','independently_reviewed_regions':0}}

def partition_projects(records,assignments):
    seen={};result=[]
    for record in records:
        group=record['project_group'];partition=assignments.get(group)
        if partition not in {'development','validation','test','unassigned'}:raise ValueError('Explicit project-level partition required')
        sha=record['sha256']
        if sha in seen and seen[sha]!=partition:raise ValueError('Duplicate content crosses evaluation partitions')
        seen[sha]=partition;result.append({**record,'partition':partition})
    return result

def classify_experiment_roles(rows):
    return {'analytic_controls':sum(r.get('provenance',{}).get('kind')=='project_authored_analytic_control' for r in rows),
            'independence_warning':'Unit and transform variants remain grouped; do not bootstrap triangles or variants as independent projects'}
