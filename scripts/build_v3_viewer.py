from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
from ifc_citygml_lab.metrics import read_geometry
from lxml import etree as ET
OUT=ROOT/'reports/v3';OUT.mkdir(parents=True,exist_ok=True)
REVIEW=r'''
<style>.review{max-width:1436px;margin:35px auto;padding:25px 0;border-top:1px solid #bdc9bf}.review input,.review select{font:inherit;padding:8px;border:1px solid #bdc9bf;max-width:100%;margin:8px}.review label{display:inline-block}.review button{margin:8px}.masked #metrics,.masked #status,.masked label:has(#method){visibility:hidden}.review .note{font-size:16px;color:#657874}</style>
<section class="review"><h2>Independent reference review</h2><p class="note">This form starts empty. Source-class hints are not reference labels. Supply independent evidence and reviewer identity; unknown regions can remain unscored.</p>
<label><input id="mask" type="checkbox">Mask method and measured metrics</label><br>
<label>Reviewer <input id="reviewer" autocomplete="off"></label><label>Evidence URI <input id="uri" autocomplete="off" size="40"></label>
<label>Reference host GUID (if established) <input id="host" autocomplete="off"></label>
<label>Reference label <select id="label"><option value="">Select a reference label</option><option>roof</option><option>wall</option><option>ground</option><option>outer_floor</option><option>outer_ceiling</option><option>opening</option><option>door</option><option>window</option><option>unknown</option></select></label>
<label><input type="checkbox" id="independent">Evidence is independent of converter predictions</label>
<button id="saveRegion">Record selected output triangle</button><button id="exportReview">Export my review CSV</button><div id="reviewStatus" class="note">0 reference regions recorded.</div></section>
<script>
const reviews=new Map();
function reviewCSV(){const keys=['input_sha256','output_sha256','region_id','ifc_global_id','reference_label','reference_host_guid','area_m2','reviewer_id','independent_reference','evidence_uri'];const cell=value=>{let s=String(value??'');if(/^[=+@-]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"'};return [keys.join(','),...[...reviews.values()].filter(r=>r.output_sha256===selection().summary.output_sha256).map(r=>keys.map(k=>cell(r[k])).join(','))].join('\r\n')}
$('mask').onchange=()=>document.body.classList.toggle('masked',$('mask').checked);
$('saveRegion').onclick=()=>{let picked;try{picked=JSON.parse($('detail').textContent)}catch(e){$('reviewStatus').textContent='Select an output triangle first.';return}if(picked.view!=='target'||!$('label').value||!$('reviewer').value.trim()||!$('uri').value.trim()||!$('independent').checked){$('reviewStatus').textContent='Select an output triangle and complete reviewer, evidence, label and independence fields.';return}
 let component=selection().components[picked.component],id=component.face_ids[picked.triangle],v=picked.vertices_m,a=v[1].map((x,i)=>x-v[0][i]),b=v[2].map((x,i)=>x-v[0][i]),area=Math.hypot(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])/2;
 let summary=selection().summary;reviews.set(summary.output_sha256+':'+id,{input_sha256:summary.input_sha256,output_sha256:summary.output_sha256,region_id:id,ifc_global_id:picked.source_guid,reference_label:$('label').value,reference_host_guid:$('host').value.trim(),area_m2:area,reviewer_id:$('reviewer').value.trim(),independent_reference:'true',evidence_uri:$('uri').value.trim()});$('reviewStatus').textContent=reviews.size+' regions recorded across outputs. Export saves the currently selected output only; entries remain local.'};
$('exportReview').onclick=()=>{let blob=new Blob([reviewCSV()],{type:'text/csv;charset=utf-8'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='independent_review.csv';a.click();URL.revokeObjectURL(a.href)};
</script>
'''
def main():
    folder=ROOT/'results/v3/holdout';index=json.loads((folder/'index.json').read_text());assert index['status']=='completed';cases={}
    for row in index['cases']:
        if 'report' not in row or 'output' not in row:continue
        report=json.loads((folder/row['report']).read_text());expected=json.loads(Path(report['input']).with_suffix('.expected.json').read_text())
        case=cases.setdefault(row['case'],{'family':row['family'],'mechanism':row['mechanism'],'methods':{},'reference':expected['reference_mesh'],'source':[]})
        if not case['source']:case['source']=[{'vertices':e['vertices'],'triangles':e['triangles'],'guid':e['ifc_global_id']} for b in report['source_evidence']['buildings'] for e in b['elements']]
        serialized=read_geometry((folder/row['output']).read_bytes())['components'];components=[];j=0
        for building,link in zip(report.get('extraction',{}).get('buildings',[]),report.get('source_links',[])):
            offset=0
            for c in building['components']:
                n=len(c['triangles']);faces=link['surface_contributions'][offset:offset+n];offset+=n;mesh=serialized[j];j+=1
                if len(mesh['triangles'])!=n:raise ValueError('Face lineage mismatch')
                components.append({**mesh,'face_sources':[p['ifc_global_id'] for p in faces],'face_ids':[p['polygon_id'] for p in faces]})
        summary={**row,'reference_all_guards':row['reference_passed']}
        case['methods'][row['method']]={'components':components,'summary':summary,'report':'../../results/v3/holdout/'+row['report'],'relations':report.get('relations',report.get('ledger',{}).get('source_graph',{}).get('geometric_relations',[])),
            'connection_evidence':report.get('connections',[]),'operations':report.get('operation_ledger',[])}
    workflow=ROOT/'results/v3/workflows';conversion=json.loads((workflow/'cylinder.conversion.json').read_text());selection=json.loads((workflow/'generalisation_cylinder/index.json').read_text());selected=next(r for r in selection['candidates'] if r['name']==selection['selected'])
    gml=(workflow/'generalisation_cylinder'/(selection['selected']+'.gml')).read_bytes();meshes=read_geometry(gml)['components'];tree=ET.fromstring(gml);polygons=tree.findall('.//{http://www.opengis.net/gml/3.2}Polygon');source_guid=conversion['source_evidence']['buildings'][0]['elements'][0]['ifc_global_id'];offset=0
    for mesh in meshes:
        n=len(mesh['triangles']);mesh['face_ids']=[p.get('{http://www.opengis.net/gml/3.2}id') for p in polygons[offset:offset+n]];mesh['face_sources']=[source_guid]*n;offset+=n
    cases['workflow_cylinder_generalisation']={'family':'cylinder','mechanism':'query-constrained generalisation','kind':'generalisation','source':[{'vertices':e['vertices'],'triangles':e['triangles'],'guid':e['ifc_global_id']} for b in conversion['source_evidence']['buildings'] for e in b['elements']],
        'reference':json.loads((workflow/'cylinder.expected.json').read_text())['reference_mesh'],'methods':{'query_generalisation':{'components':meshes,'summary':{'case':'workflow_cylinder_generalisation','status':'query_admissible','reference_all_guards':True,'input_sha256':conversion['input_sha256'],
            'output_sha256':__import__('hashlib').sha256(gml).hexdigest(),'geometry_valid':True,'metrics':{'component_count':selected['components'],'euler_sum':selected['euler'],'sampled_surface_distance':{'sampled_maximum_m':selected['sampled_boundary_maximum_m']},'guards':selected['guards']}},
            'report':'../../results/v3/workflows/generalisation_cylinder/index.json','relations':[]}}}
    template=(ROOT/'research/inspection_viewer.html').read_text(encoding='utf-8')
    template=template.replace('__DATA__',json.dumps(cases,separators=(',',':')).replace('</','<\\/')).replace("'guarded'","'v3_constrained'")
    template=template.replace("keys.find(k=>k.startsWith('gable_roof_b0_c0'))","keys.find(k=>k==='v3_holdout_0064_ordinary')")
    template=template.replace("o.textContent=k.replaceAll('_',' ')","o.textContent=DATA[k].family.replaceAll('_',' ')+' / '+DATA[k].mechanism.replaceAll('_',' ')+' / '+k.split('_')[2]",1)
    template=template.replace("c.methods[old]?old:'v3_constrained'","c.methods[old]?old:(c.methods.v3_constrained?'v3_constrained':Object.keys(c.methods)[0])")
    template=template.replace("['Reference checks',r.reference_all_guards", "[c.kind==='generalisation'?'Query contract checks':'Reference checks',r.reference_all_guards")
    template=template.replace('RESEARCH LABORATORY · DEVELOPMENT EVIDENCE','V3 RESEARCH LABORATORY · FROZEN MECHANISM HOLDOUT')
    template=template.replace('</main> </html>','</main></html>')
    # Keep the reviewer form inside main, with scripts after the geometry setup.
    template=template.replace('</script></html>','</script>'+REVIEW+'</html>')
    (OUT/'Geometry_and_Review.html').write_text(template,encoding='utf-8');print('Built V3 viewer with',len(cases),'cases and empty independent-review form')
if __name__=='__main__':main()
