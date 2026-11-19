"""Controlled footprint and volume evaluation of the frozen v0.6 converter.

Reference dimensions are specified before IFC creation. No mesh repair or
converter changes are performed. Experimental outputs never replace releases.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import uuid

import ifcopenshell
import ifcopenshell.guid
from lxml import etree as ET
import numpy as np
from shapely import affinity, union_all
from shapely.geometry import Polygon, box, mapping

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ifc_citygml.benchmark import run_benchmark
from ifc_citygml.common import code_digest, digest, resource_digest, software_versions, write_json
from ifc_citygml.citygml_writer import NS
from prepare_methodology_evidence import verify_frozen

OUT=ROOT/'results/experiments/shape_fidelity_001'
INPUT=ROOT/'data/derived/shape_fidelity_001'
# x, y, z, width, depth, height in SI metres. Components touch but do not overlap.
SHAPES={
 'rectangle':{'boxes':[(0,0,0,12,8,6)],'area':96.,'volume':576.,'holes':0},
 'l_shape':{'boxes':[(0,0,0,12,3,6),(0,3,0,3,5,6)],'area':51.,'volume':306.,'holes':0},
 'u_shape':{'boxes':[(0,0,0,3,8,6),(9,0,0,3,8,6),(3,0,0,6,3,6)],'area':66.,'volume':396.,'holes':0},
 'courtyard':{'boxes':[(0,0,0,12,3,6),(0,7,0,12,3,6),(0,3,0,3,4,6),(9,3,0,3,4,6)],'area':96.,'volume':576.,'holes':1},
 'setback':{'boxes':[(0,0,0,12,8,3),(3,2,3,6,4,3)],'area':96.,'volume':360.,'holes':0}}
ID=uuid.UUID('db02988b-3d51-4cd2-9271-180bcb245d95')


def reference(name,yaw):
    spec=SHAPES[name]
    poly=union_all([box(x,y,x+w,y+d) for x,y,z,w,d,h in spec['boxes']])
    assert abs(poly.area-spec['area'])<1e-12
    assert len(poly.interiors)==spec['holes']
    # Closed-form component volumes are valid here because interiors do not overlap.
    assert sum(w*d*h for x,y,z,w,d,h in spec['boxes'])==spec['volume']
    poly=affinity.translate(affinity.rotate(poly,yaw,origin=(0,0)),100,200)
    bounds=poly.bounds
    maxz=max(z+h for x,y,z,w,d,h in spec['boxes'])
    return {'footprint':mapping(poly),'area_m2':spec['area'],'volume_m3':spec['volume'],
            'holes':spec['holes'],'z_bounds_m':[10.,10.+maxz],
            'aabb_area_m2':(bounds[2]-bounds[0])*(bounds[3]-bounds[1]),
            'aabb_volume_m3':(bounds[2]-bounds[0])*(bounds[3]-bounds[1])*maxz}


def create_ifc(path,name,yaw,mm):
    f=ifcopenshell.file(schema='IFC4');factor=1000. if mm else 1.
    def e(kind,**kw):return f.create_entity(kind,**kw)
    def point(p):return e('IfcCartesianPoint',Coordinates=tuple(float(v)*factor for v in p))
    def direction(p):return e('IfcDirection',DirectionRatios=tuple(float(v) for v in p))
    def axis(offset=(0,0,0),angle=0):
        a=math.radians(angle)
        return e('IfcAxis2Placement3D',Location=point(offset),Axis=direction((0,0,1)),RefDirection=direction((math.cos(a),math.sin(a),0)))
    def place(parent=None,offset=(0,0,0),angle=0):return e('IfcLocalPlacement',PlacementRelTo=parent,RelativePlacement=axis(offset,angle))
    def rooted(kind,key,**kw):return e(kind,GlobalId=ifcopenshell.guid.compress(uuid.uuid5(ID,path.stem+'/'+key).hex),**kw)
    context=e('IfcGeometricRepresentationContext',ContextIdentifier='Model',ContextType='Model',CoordinateSpaceDimension=3,Precision=1e-7*factor,WorldCoordinateSystem=axis())
    unit=e('IfcSIUnit',UnitType='LENGTHUNIT',Name='METRE',Prefix='MILLI' if mm else None)
    project=rooted('IfcProject','project',Name='Controlled geometric fidelity experiment',UnitsInContext=e('IfcUnitAssignment',Units=[unit]),RepresentationContexts=[context])
    building=rooted('IfcBuilding','building',Name=name,CompositionType='ELEMENT',ObjectPlacement=place(offset=(100,200,10),angle=yaw))
    rooted('IfcRelAggregates','project_building',RelatingObject=project,RelatedObjects=[building])
    members=[]
    for i,(x,y,z,w,d,h) in enumerate(SHAPES[name]['boxes']):
        profile=e('IfcRectangleProfileDef',ProfileType='AREA',Position=e('IfcAxis2Placement2D',Location=point((w/2,d/2))),XDim=w*factor,YDim=d*factor)
        solid=e('IfcExtrudedAreaSolid',SweptArea=profile,Position=axis(),ExtrudedDirection=direction((0,0,1)),Depth=h*factor)
        rep=e('IfcShapeRepresentation',ContextOfItems=context,RepresentationIdentifier='Body',RepresentationType='SweptSolid',Items=[solid])
        members.append(rooted('IfcWall',f'body_{i}',Name=f'Analytical prism {i}',ObjectPlacement=place(building.ObjectPlacement,(x,y,z)),Representation=e('IfcProductDefinitionShape',Representations=[rep])))
    rooted('IfcRelContainedInSpatialStructure','containment',RelatedElements=members,RelatingStructure=building)
    f.header.file_name.name=path.name;f.header.file_name.time_stamp='2026-11-02T00:00:00'
    f.header.file_name.author=('IFC to CityGML research project',)
    f.write(str(path))


def prepare():
    if (OUT/'PROTOCOL.json').exists():raise FileExistsError('Protocol already exists; preserve this experiment and choose a new identifier')
    OUT.mkdir(parents=True,exist_ok=True);INPUT.mkdir(parents=True,exist_ok=True)
    protocol={'experiment':'shape_fidelity_001','registered_utc':datetime.now(timezone.utc).isoformat(),
      'question':'How do representation, plan complexity, yaw and source units affect footprint fidelity and volume surrogates?',
      'design':{'shape_families':list(SHAPES),'yaw_degrees':[0,30,45],'units':['metre','millimetre'],'schema':'IFC4','profiles':['block','exterior','source'],'inputs':30,'attempts':90},
      'reference_policy':'Five project-authored idealized solid designs with closed-form area and nonoverlapping prism volume. Reference footprints come from declared dimensions and rotation, not IFC extraction.',
      'metrics':['footprint intersection over union','symmetric difference area','footprint area overestimate percent','boundary Hausdorff distance','reference courtyard preservation','block volume overestimate percent'],
      'thresholds':{'surface_footprint_iou_min':.999999,'surface_boundary_hausdorff_max_m':5e-6,'block_aabb_area_relative_error_max':1e-6,'block_volume_relative_error_max':1e-6},
      'failure_policy':'Retain all 90 attempts, including extraction and validation failures. No post hoc repair or replacement by a block.',
      'volume_policy':'A block volume is a box surrogate. Surface volume is reported only if the separate Solid diagnostic passes; source per-feature solids do not establish one building envelope.',
      'sampling_limit':'Thirty paired synthetic variants of five designs; no new independent real buildings, semantic ground truth or geographic accuracy.',
      'license':'CC0-1.0','converter_source_sha256':code_digest(),'resources_sha256':resource_digest(),'software':software_versions(),
      'generator_sha256':digest(Path(__file__)),'frozen_releases':verify_frozen()}
    # Written before fixtures and conversions, with fixed hypotheses and tolerances.
    write_json(OUT/'PROTOCOL.json',protocol)
    cases=[]
    for name in SHAPES:
        for yaw in [0,30,45]:
            for mm in [False,True]:
                case=f'{name}_yaw{yaw}_{"mm" if mm else "m"}'
                source=INPUT/(case+'.ifc');create_ifc(source,name,yaw,mm)
                expected={'case':case,'shape_family':name,'yaw_degrees':yaw,'units':'millimetre' if mm else 'metre',**reference(name,yaw)}
                write_json(source.with_suffix('.expected.json'),expected)
                cases.append({'id':case,'input':str(source.resolve()),'provenance':{'kind':'controlled_analytic_solid','license':'CC0-1.0','shape_family':name,'yaw_degrees':yaw,'units':expected['units']},'input_sha256':digest(source),'expected_sha256':digest(source.with_suffix('.expected.json'))})
    write_json(OUT/'manifest.json',{'format_version':1,'profiles':['block','exterior','source'],'cases':cases})
    print(json.dumps({'prepared_inputs':len(cases),'protocol':str(OUT/'PROTOCOL.json')}))


def execute():
    if (OUT/'conversions/index.json').exists():raise FileExistsError('Run already exists; do not overwrite recorded attempts')
    assert code_digest()==json.loads((OUT/'PROTOCOL.json').read_text())['converter_source_sha256']
    index=run_benchmark(OUT/'manifest.json',OUT/'conversions',progress=lambda r:print(json.dumps({k:r[k] for k in ('case','mode','status')}),flush=True))
    print(json.dumps({k:index[k] for k in ('attempts','completed','failed')}))


def read_footprint(path):
    tree=ET.parse(str(path),ET.XMLParser(no_network=True,resolve_entities=False))
    projected=[];rings=[]
    for poly in tree.findall('.//gml:Polygon',NS):
        pos=poly.find('./gml:exterior/gml:LinearRing/gml:posList',NS)
        ring=np.array([float(x) for x in pos.text.split()]).reshape(-1,3)
        assert np.isfinite(ring).all() and np.array_equal(ring[0],ring[-1])
        rings.append(ring)
        p=Polygon(ring[:,:2])
        if p.area>1e-12:
            if not p.is_valid:raise ValueError('Invalid projected polygon; no silent repair')
            projected.append(p)
    if not projected:raise ValueError('No nonzero projected surface')
    footprint=union_all(projected)
    if not footprint.is_valid:raise ValueError('Invalid projected union')
    return footprint,rings


def compare(footprint,expected):
    from shapely.geometry import shape
    ref=shape(expected['footprint']);intersection=footprint.intersection(ref).area
    union=footprint.union(ref).area
    return {'reference_area_m2':ref.area,'exported_area_m2':footprint.area,'intersection_over_union':intersection/union,
      'symmetric_difference_m2':footprint.symmetric_difference(ref).area,'area_overestimate_percent':100*(footprint.area/ref.area-1),
      'boundary_hausdorff_m':footprint.boundary.hausdorff_distance(ref.boundary),
      'reference_holes':expected['holes'],'exported_holes':sum(len(p.interiors) for p in ([footprint] if footprint.geom_type=='Polygon' else footprint.geoms))}


def evaluate():
    manifest=json.loads((OUT/'manifest.json').read_text());sources={c['id']:c for c in manifest['cases']}
    index=json.loads((OUT/'conversions/index.json').read_text());assert len(index['cases'])==90 and index['status']!='running'
    rows=[]
    for c in index['cases']:
        source=Path(sources[c['case']]['input']);assert digest(source)==sources[c['case']]['input_sha256']
        assert digest(source.with_suffix('.expected.json'))==sources[c['case']]['expected_sha256']
        exp=json.loads(source.with_suffix('.expected.json').read_text())
        row={k:c[k] for k in ('case','mode','status')};row.update({k:exp[k] for k in ('shape_family','yaw_degrees','units')})
        report=json.loads((OUT/'conversions'/c['report']).read_text())
        row['report']=c['report'];row['validation']=report.get('validation');row['error']=c.get('error')
        if c['status']=='passed':
            path=OUT/'conversions'/f"{c['case']}_{c['mode']}.gml";assert digest(path)==c['output_sha256']
            fp,rings=read_footprint(path);row['footprint']=compare(fp,exp);row['footprint_geojson']=mapping(fp)
            v=report['validation'];row['solid_diagnostic']=v.get('independent_general_solid_validation','not_run')
            if c['mode']=='block':
                volume=sum(g['volume_m3'] for g in v['geometry'])
                row['volume']={'surrogate_box_m3':volume,'reference_solid_m3':exp['volume_m3'],'overestimate_percent':100*(volume/exp['volume_m3']-1)}
                row['matches_analytic_aabb']=abs(fp.area/exp['aabb_area_m2']-1)<=1e-6 and abs(volume/exp['aabb_volume_m3']-1)<=1e-6
            else:
                row['surface_footprint_within_registered_tolerance']=row['footprint']['intersection_over_union']>=.999999 and row['footprint']['boundary_hausdorff_m']<=5e-6
        rows.append(row)
    summary={'experiment':'shape_fidelity_001','protocol_sha256':digest(OUT/'PROTOCOL.json'),'manifest_sha256':digest(OUT/'manifest.json'),
             'attempts':len(rows),'completed':sum(r['status']=='passed' for r in rows),'failed':sum(r['status']!='passed' for r in rows),
             'converter_source_sha256':code_digest(),'rows':rows,'frozen_releases_verified_after':verify_frozen()}
    write_json(OUT/'evaluation.json',summary)
    print(json.dumps({k:summary[k] for k in ('attempts','completed','failed')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','run','evaluate']);args=parser.parse_args()
    {'prepare':prepare,'run':execute,'evaluate':evaluate}[args.stage]()
