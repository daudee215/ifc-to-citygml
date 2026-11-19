"""Inspectable lineage queries and an explicit experimental JSON-LD vocabulary."""
def query_guid(result,guid):
    source=result.get('source_evidence',{});graph=source.get('graph',{})
    return {'source_guid':guid,'source_records':[e for b in source.get('buildings',[]) for e in b['elements'] if e['ifc_global_id']==guid],
        'explicit_relationships':[e for e in graph.get('edges',[]) if guid in [e['source'],e['target']]],
        'connection_evidence':[e for e in result.get('connections',[]) if guid in [e['source'],e['target']]],
        'output_polygons':[p for l in result.get('source_links',[]) for p in l.get('surface_contributions',[]) if p['ifc_global_id']==guid],
        'operations':[e for e in result.get('operation_ledger',[]) if e.get('source')==guid],
        'decision':result.get('status'),'semantic_truth':'not established by lineage','geographic_truth':'not established by lineage'}

def jsonld(result):
    graph=[]
    for b in result.get('source_evidence',{}).get('buildings',[]):
        for e in b['elements']:graph.append({'@id':'urn:ifc:'+e['ifc_global_id'],'@type':'SourceElement','ifcClass':e['ifc_class'],'sourceStepId':e['step_id']})
    for link in result.get('source_links',[]):
        for p in link.get('surface_contributions',[]):graph.append({'@id':'urn:citygml:'+p['polygon_id'],'@type':'DerivedSurface','derivedFrom':{'@id':'urn:ifc:'+p['ifc_global_id']},'semanticStatus':p['semantic_status']})
    return {'@context':{'@vocab':'urn:ifc-citygml:lab:v3:'},'@graph':graph,'vocabularyStatus':'Experimental project vocabulary; not a native CityGML uncertainty module','inputSha256':result.get('input_sha256'),'decision':result.get('status')}
