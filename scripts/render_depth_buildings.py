"""Render exported polygons with a real depth buffer, without mesh modification."""
import base64
import json
from pathlib import Path
import re
import subprocess
import build_research_figures as source

OUT=source.ROOT/'reports/methodology_palatino'
OUT.mkdir(exist_ok=True)
models=[next(m for m in source.D['models'] if m['label']==f'duplex · {mode}') for mode in ['block','exterior','source']]
data=json.dumps(models)
script=r'''
const DATA=__DATA__;
const project=p=>[.78*p[0]-.63*p[1],.31*p[0]+.38*p[1]-.87*p[2],.5481*p[0]+.6786*p[1]+.4917*p[2]];
const all=DATA.flatMap(m=>m.polygons.flatMap(q=>q.points.map(project)));
const lo=[0,1,2].map(i=>Math.min(...all.map(p=>p[i]))),hi=[0,1,2].map(i=>Math.max(...all.map(p=>p[i])));
const scale=Math.min(1.82/(hi[0]-lo[0]),1.80/(hi[1]-lo[1]));
const palette={Block:[.55,.64,.68],WallSurface:[.85,.86,.83],RoofSurface:[.55,.64,.61],GroundSurface:[.63,.67,.68],WindowSurface:[.36,.52,.59],DoorSurface:[.48,.40,.34]};
for(let index=0;index<DATA.length;index++){
 const canvas=document.createElement('canvas');canvas.width=1100;canvas.height=1000;
 const gl=canvas.getContext('webgl',{antialias:true,preserveDrawingBuffer:true,alpha:false});if(!gl)throw Error('No WebGL');
 const vs=gl.createShader(gl.VERTEX_SHADER);gl.shaderSource(vs,'attribute vec3 position;attribute vec3 colour;varying vec3 c;void main(){gl_Position=vec4(position,1.0);c=colour;}');gl.compileShader(vs);
 const fs=gl.createShader(gl.FRAGMENT_SHADER);gl.shaderSource(fs,'precision mediump float;varying vec3 c;void main(){gl_FragColor=vec4(c,1.0);}');gl.compileShader(fs);
 const prog=gl.createProgram();gl.attachShader(prog,vs);gl.attachShader(prog,fs);gl.linkProgram(prog);gl.useProgram(prog);
 const positions=[],colours=[];
 for(const polygon of DATA[index].polygons){
  const points=polygon.points;
  for(let j=1;j<points.length-1;j++){
   const tri=[points[0],points[j],points[j+1]],a=tri[1].map((v,i)=>v-tri[0][i]),b=tri[2].map((v,i)=>v-tri[0][i]);
   const n=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],length=Math.hypot(...n)||1;
   const light=.70+.30*Math.abs((n[0]*.30+n[1]*-.40+n[2]*.866)/length);
   const color=index===2?[.36,.51,.51]:(palette[polygon.kind]||[.73,.77,.77]);
   for(const p of tri){const q=project(p);positions.push((q[0]-(lo[0]+hi[0])/2)*scale*canvas.height/canvas.width,-(q[1]-(lo[1]+hi[1])/2)*scale,-.90*(2*(q[2]-lo[2])/(hi[2]-lo[2])-1));colours.push(...color.map(v=>v*light));}
  }
 }
 for(const [name,values] of [['position',positions],['colour',colours]]){let buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(values),gl.STATIC_DRAW);let at=gl.getAttribLocation(prog,name);gl.enableVertexAttribArray(at);gl.vertexAttribPointer(at,3,gl.FLOAT,false,0,0);}
 gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.clearColor(1,1,1,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.drawArrays(gl.TRIANGLES,0,positions.length/3);gl.finish();
 const img=document.createElement('img');img.id='model'+index;img.src=canvas.toDataURL('image/png');document.body.append(img);
}
document.documentElement.dataset.ready='true';
'''.replace('__DATA__',data)
path=OUT/'depth_render.html';path.write_text('<!doctype html><html><body><script>'+script+'</script></body></html>',encoding='utf-8')
result=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless','--disable-gpu-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--virtual-time-budget=12000','--dump-dom',path.as_uri()],capture_output=True,check=True)
dom=result.stdout.decode('utf-8')
assert 'data-ready="true"' in dom, result.stderr.decode('utf-8',errors='replace')[-1000:]
images=re.findall(r'<img id="model(\d)" src="data:image/png;base64,([^"]+)"',dom)
assert len(images)==3
for index,encoded in images:(OUT/f'depth_model_{index}.png').write_bytes(base64.b64decode(encoded))
print('Rendered all three models using WebGL depth testing')
