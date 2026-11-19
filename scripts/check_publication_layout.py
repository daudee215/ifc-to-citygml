"""Check SVG text bounds with the same browser/font used for the exports."""
import html
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/publication_figures_004'
figures=sorted((OUT/'figures').glob('*.svg'))
page=OUT/'layout_check.html'
script='''const errors=[];for(const svg of document.querySelectorAll('svg')){for(const t of svg.querySelectorAll('text')){const r=t.getBBox(),m=t.getCTM();const ps=[[r.x,r.y],[r.x+r.width,r.y],[r.x,r.y+r.height],[r.x+r.width,r.y+r.height]].map(([x,y])=>new DOMPoint(x,y).matrixTransform(m));if(Math.min(...ps.map(p=>p.x))<58||Math.max(...ps.map(p=>p.x))>1542||Math.min(...ps.map(p=>p.y))<0||Math.max(...ps.map(p=>p.y))>995)errors.push({figure:svg.dataset.name,text:t.textContent,bounds:ps.map(p=>[p.x,p.y])});}}document.getElementById('result').textContent=JSON.stringify(errors);'''
page.write_text('<!doctype html><meta charset="utf-8">'+''.join(f'<div>{p.read_text(encoding="utf-8").replace("<svg ","<svg data-name="+chr(34)+p.stem+chr(34)+" ",1)}</div>' for p in figures)+'<pre id="result"></pre><script>'+script+'</script>',encoding='utf-8')
r=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless','--disable-gpu','--dump-dom',page.as_uri()],capture_output=True,check=True)
result=json.loads(html.unescape(re.search(r'<pre id="result">(.*?)</pre>',r.stdout.decode(),re.S).group(1)))
(OUT/'layout_bounds.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if result:raise SystemExit(1)
