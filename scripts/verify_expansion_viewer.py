"""Browser checks plus actual depth-rendered model exports."""
from pathlib import Path
import base64
import html
import json
import re
import subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/expansion_v2'
CHROME='C:/Program Files/Google/Chrome/Application/chrome.exe'
SCRIPT=r'''
const checks=[];
for(const key of ['gable_roof_b0_c0_m','hip_roof_b0_c0_m','courtyard_b0_c23_m','passage_b0_c23_m']){
 $('case').value=key;update();$('method').value='guarded';refresh();
 for(const id of ['source','target','reference']){
  const canvas=$(id),gl=canvas.getContext('webgl'),pixels=new Uint8Array(canvas.width*canvas.height*4);gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);let ink=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i]<240||pixels[i+1]<240||pixels[i+2]<240)ink++;
  checks.push({case:key,view:id,triangles:Number(canvas.dataset.triangles),rendered_pixels:ink,passed:ink>500&&Number(canvas.dataset.triangles)>0});
  const img=document.createElement('img');img.id='export_'+key+'_'+id;img.src=canvas.toDataURL();document.body.append(img);
 }
}
const before=yaw;$('reset').click();checks.push({check:'camera_reset',passed:yaw===.65});
const canvas=$('source'),r=canvas.getBoundingClientRect();pick(canvas,{clientX:r.x+r.width/2,clientY:r.y+r.height/2});checks.push({check:'source_pick',passed:$('detail').textContent.includes('source_guid')});
let result=document.createElement('pre');result.id='qa_result';result.textContent=JSON.stringify(checks);document.body.append(result);
'''

def main():
    qa=OUT/'viewer_browser_check.html';page=(OUT/'Geometry_Inspection.html').read_text(encoding='utf-8')
    qa.write_text(page.replace('</html>','<script>'+SCRIPT+'</script></html>'),encoding='utf-8')
    process=subprocess.run([CHROME,'--headless','--disable-gpu-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--window-size=1500,1100','--virtual-time-budget=5000','--dump-dom',qa.as_uri()],capture_output=True,timeout=60)
    dom=process.stdout.decode('utf-8');match=re.search(r'<pre id="qa_result">(.*?)</pre>',dom,re.S)
    if not match:raise ValueError('Viewer JS failed: '+process.stderr.decode(errors='replace')[-2000:])
    checks=json.loads(html.unescape(match.group(1)))
    for name,encoded in re.findall(r'<img id="export_([^"]+)" src="data:image/png;base64,([^"]+)"',dom):(OUT/(name+'.png')).write_bytes(base64.b64decode(encoded))
    (OUT/'viewer_verification.json').write_text(json.dumps(checks,indent=2))
    if not all(c['passed'] for c in checks):raise ValueError(checks)
    subprocess.run([CHROME,'--headless','--disable-gpu-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--window-size=1500,1100','--virtual-time-budget=3000',f'--screenshot={OUT/"Viewer_Preview.png"}',(OUT/'Geometry_Inspection.html').as_uri()],capture_output=True,timeout=45,check=True)
    print('Viewer checks passed:',len(checks))

if __name__=='__main__':main()
