"""Pinned source-converter applicability, without an unfair envelope ranking."""
from pathlib import Path
from datetime import datetime,timezone
import json
import subprocess
import sys
import time
from lxml import etree as ET
import ifcopenshell
from ifc_citygml.common import digest,write_json,software_versions
from ifc_citygml.validation import load_schema

COMMIT='0368abb676f3fccd6d71ceb5ea507d848c08327c'

def run_tum(root,output):
    root=Path(root);folder=Path(output)
    if folder.exists():raise FileExistsError('External comparison already exists')
    folder.mkdir(parents=True);tool=root/'tools/ifc_to_citygml3_0368/ifc2citygml.py'
    cases=[root/'data/raw/benchmarks/duplex/Duplex_A_20110907.ifc',root/'data/raw/benchmarks/clinic/Clinic_Architectural.ifc']
    write_json(folder/'PLAN.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'repository':'https://github.com/tum-gis/ifc-to-citygml3',
        'commit':COMMIT,'script_sha256':digest(tool),'licence':'MIT','licence_sha256':digest(tool.parent/'LICENSE'),'software':software_versions(),
        'cases':[{'input':str(p),'sha256':digest(p)} for p in cases],
        'scope':'Constructive/filling content comparison, not outer-envelope extraction. Geometry and source-link counts do not establish real-building semantic truth.',
        'arguments':['--no-properties','--no-storeys','--no-appearances'],'geographic_relocation':False})
    rows=[]
    for path in cases:
        target=folder/(path.parent.name+'.gml');start=time.perf_counter()
        process=subprocess.run([sys.executable,str(tool),str(path),'-o',str(target),'--no-properties','--no-storeys','--no-appearances'],capture_output=True,text=True,timeout=300)
        (folder/(path.parent.name+'.log.txt')).write_text(process.stdout+'\nSTDERR\n'+process.stderr,encoding='utf-8')
        row={'case':path.parent.name,'exit_code':process.returncode,'wall_seconds':time.perf_counter()-start,'output_written':target.exists(),'status':'failed'}
        if target.exists():
            tree=ET.parse(str(target));schema=load_schema();valid=schema.validate(tree)
            row.update(status='produced_output',sha256=digest(target),schema_valid=valid,schema_errors=[str(e) for e in schema.error_log],
                constructive_elements=len(tree.findall('.//{http://www.opengis.net/citygml/building/3.0}BuildingConstructiveElement')),
                polygons=len(tree.findall('.//{http://www.opengis.net/gml/3.2}Polygon')),
                geometry_validation='Not scored: pinned v0.6 adapter does not support the external tool volumetric feature encoding; no false envelope comparison')
        rows.append(row);write_json(folder/'index.json',{'status':'running','cases':rows});print('External baseline',row['case'],row['status'],flush=True)
    write_json(folder/'index.json',{'status':'completed','cases':rows});return rows
