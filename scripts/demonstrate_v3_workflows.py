"""Run actual generalisation, revision, lineage and fixed-hazard examples."""
from pathlib import Path
import json,sys,time
import numpy as np
import ifcopenshell
import ifcopenshell.util.element
from shapely.geometry import box,mapping
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
from ifc_citygml.common import write_json,digest
from ifc_citygml_lab.fixtures import create_case
from ifc_citygml_lab.metrics import read_geometry
from ifc_citygml_v3.converter import convert
from ifc_citygml_v3.incremental import update
from ifc_citygml_v3.generalisation import choose,QueryContract
from ifc_citygml_v3.sensitivity import profile_sensitivity
from ifc_citygml_v3.trace import jsonld
from ifc_citygml_v3.annotations import reviewer_agreement
from ifc_citygml_v3.fixtures import gid
from ifc_citygml_lab.semantics import export_annotation_csv

def collection(geometry):return {'type':'FeatureCollection','features':[{'type':'Feature','id':'same_building','properties':{},'geometry':mapping(geometry)}]}

def main():
    folder=ROOT/'results/v3/workflows';folder.mkdir(parents=True,exist_ok=False);general=[];revision_rows=[]
    write_json(folder/'PLAN.json',{'tasks':['Measured simplification and protected courtyard','Building-level revision reuse with full rebuild comparison','Fixed hazard conversion/placement scenarios','Queryable lineage and blank review templates'],'reference_policy':'No human review or surveyed accuracy invented'})
    for family in ['courtyard','cylinder','gable_roof']:
        path=folder/(family+'.ifc');create_case(path,family);result,data=convert(path);write_json(folder/(family+'.conversion.json'),result)
        contract=QueryContract(maximum_sampled_boundary_error_m=.2 if family=='cylinder' else .1,maximum_relative_volume_error=.1,
            protected_void_probes=((106,205,13),) if family=='courtyard' else ())
        selected,outputs=choose(result,contract);target=folder/('generalisation_'+family);target.mkdir()
        for name,value in outputs.items():(target/(name+'.gml')).write_bytes(value['data'])
        write_json(target/'index.json',selected);general.append({'family':family,**selected})
        if family=='courtyard':
            accepted=read_geometry(data)['footprint'];building_bounds=box(*accepted.bounds);hazard=collection(box(105,202,108,209))
            sensitivity=profile_sensitivity({'material_union':collection(accepted),'block':collection(building_bounds)},hazard,'EPSG:32632','synthetic_truth',[(0,0),(-.1,0),(.1,0),(0,-.1),(0,.1)],'Declared +/- 0.1 m sensitivity scenarios; these are not measured Torino placement errors')
            write_json(folder/'urban_sensitivity.json',sensitivity)
        if family=='gable_roof':
            write_json(folder/'lineage.jsonld',jsonld(result));export_annotation_csv(folder/'reviewer_A_blank.csv',result);export_annotation_csv(folder/'reviewer_B_blank.csv',result)
            write_json(folder/'independent_review_status.json',reviewer_agreement([],[]))
    seed=folder/'revision_0.ifc';create_case(seed,'rectangle');model=ifcopenshell.open(str(seed));b=model.by_type('IfcBuilding')[0];wall=model.by_type('IfcWall')[0];wall.Name='Block_0';project=model.by_type('IfcProject')[0]
    for i in range(1,5):
        other=ifcopenshell.util.element.copy_deep(model,b);other.GlobalId=gid('revision/building/'+str(i));other.Name='Block '+str(i);other.ObjectPlacement.RelativePlacement.Location.Coordinates=(100.+50*i,200.,10.)
        element=ifcopenshell.util.element.copy_deep(model,wall);element.GlobalId=gid('revision/wall/'+str(i));element.Name='Block_'+str(i);element.ObjectPlacement.PlacementRelTo=other.ObjectPlacement
        model.create_entity('IfcRelAggregates',GlobalId=gid('revision/aggregate/'+str(i)),RelatingObject=project,RelatedObjects=[other])
        model.create_entity('IfcRelContainedInSpatialStructure',GlobalId=gid('revision/contain/'+str(i)),RelatingStructure=other,RelatedElements=[element])
    cache=folder/'incremental_cache.json'
    for i in range(5):
        if i==1:next(w for w in model.by_type('IfcWall') if w.Name=='Block_2').Representation.Representations[0].Items[0].Depth=8.
        if i==2:next(x for x in model.by_type('IfcBuilding') if x.Name=='Block 3').ObjectPlacement.RelativePlacement.Location.Coordinates=(251.5,200.,10.)
        if i==4:next(w for w in model.by_type('IfcWall') if w.Name=='Block_1').Name='Changed semantic name'
        path=folder/f'revision_{i}.ifc';model.write(str(path));r,data=update(path,cache,verify_rebuild=True)
        if data:(folder/f'revision_{i}.{r["status"]}.gml').write_bytes(data)
        write_json(folder/f'revision_{i}.report.json',r);revision_rows.append({'revision':i,**r['incremental']});print('Revision',i,'reused',len(r['incremental']['reused_buildings']),flush=True)
    write_json(folder/'index.json',{'status':'completed','generalisation':general,'revisions':revision_rows,'semantic_review':'awaiting independent reviewers','urban_scope':'Synthetic fixed-hazard sensitivity, not Torino accuracy'})
if __name__=='__main__':main()
