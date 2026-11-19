from pathlib import Path
import subprocess,re,json,html,base64
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/v3';CHROME='C:/Program Files/Google/Chrome/Application/chrome.exe'
SCRIPT=r'''
const checks=[];
for(const key of ['v3_holdout_0064_ordinary','v3_holdout_0017_tilted','v3_holdout_0004_geometric_connection','workflow_cylinder_generalisation']){
 $('case').value=key;update();if(DATA[key].methods.v3_constrained){$('method').value='v3_constrained';refresh()}
 for(const id of ['source','target','reference']){const canvas=$(id),gl=canvas.getContext('webgl'),pixels=new Uint8Array(canvas.width*canvas.height*4);gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);let ink=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i]<240||pixels[i+1]<240||pixels[i+2]<240)ink++;
 checks.push({case:key,view:id,triangles:Number(canvas.dataset.triangles),rendered_pixels:ink,passed:ink>500&&Number(canvas.dataset.triangles)>0});let img=document.createElement('img');img.id='export_'+key+'_'+id;img.src=canvas.toDataURL();document.body.append(img);}
}
$('mask').checked=true;$('mask').onchange();checks.push({check:'method_metric_mask',passed:document.body.classList.contains('masked')});$('mask').checked=false;$('mask').onchange();
checks.push({check:'empty_review_not_scored',passed:reviews.size===0&&reviewCSV().split('\r\n').length===1});$('saveRegion').click();checks.push({check:'incomplete_review_blocked',passed:reviews.size===0});
$('case').value='v3_holdout_0064_ordinary';update();let canvas=$('target'),r=canvas.getBoundingClientRect();pick(canvas,{clientX:r.x+r.width/2,clientY:r.y+r.height/2});checks.push({check:'target_source_pick',passed:$('detail').textContent.includes('source_guid')});
const result=document.createElement('pre');result.id='qa_result';result.textContent=JSON.stringify(checks);document.body.append(result);
'''
def main():
    path=OUT/'viewer_browser_check.html';page=(OUT/'Geometry_and_Review.html').read_text(encoding='utf-8')
    guard="<script>window.addEventListener('error',e=>{let p=document.createElement('pre');p.id='qa_error';p.textContent=e.message+' '+(e.error?.stack||'');document.body.append(p)})</script>"
    page=page.replace('<script>',guard+'<script>',1)
    path.write_text(page.replace('</html>','<script>'+SCRIPT+'</script></html>'),encoding='utf-8')
    args=[CHROME,'--headless','--disable-gpu-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--window-size=1500,1100','--virtual-time-budget=5000']
    result=subprocess.run([*args,'--dump-dom',path.as_uri()],capture_output=True,timeout=60);dom=result.stdout.decode('utf-8');match=re.search(r'<pre id="qa_result">(.*?)</pre>',dom,re.S)
    if not match:
        errors=re.findall(r'<pre id="qa_error">(.*?)</pre>',dom,re.S)
        raise ValueError('Viewer JS failed: '+html.unescape(str(errors))+' '+result.stderr.decode(errors='replace')[-500:])
    checks=json.loads(html.unescape(match.group(1)));(OUT/'viewer_verification.json').write_text(json.dumps(checks,indent=2))
    for name,encoded in re.findall(r'<img id="export_([^"]+)" src="data:image/png;base64,([^"]+)"',dom):(OUT/(name+'.png')).write_bytes(base64.b64decode(encoded))
    assert all(r['passed'] for r in checks),checks
    subprocess.run([*args,f'--screenshot={OUT/"Viewer_Preview.png"}',(OUT/'Geometry_and_Review.html').as_uri()],capture_output=True,timeout=60,check=True)
    print('Passed',len(checks),'viewer/review browser checks')
if __name__=='__main__':main()
