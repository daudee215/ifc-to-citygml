"""Actual component-coloured geometry for a larger, curated figure edition."""
import base64
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/publication_figures_004';OUT.mkdir(exist_ok=True)
paths=[ROOT/'results/experiments/shape_fidelity_001/conversions/courtyard_yaw45_m_exterior.report.json',
       ROOT/'results/experiments/local_frame_003/candidate/courtyard_yaw45_m.report.json',
       ROOT/'results/experiments/frame_alignment_004/building_frame/courtyard_inner7_outer37_m.report.json']
models=[]
for path in paths:
    detail=json.loads(path.read_text());extraction=detail['extraction'];polygons=[]
    for building in extraction['buildings']:
        for i,component in enumerate(building['components']):
            for tri in component['triangles']:
                polygons.append({'kind':'C'+str(i),'points':[component['vertices'][v] for v in tri]})
    models.append({'report':str(path.relative_to(ROOT)),'polygons':polygons})
original=(ROOT/'scripts/render_depth_buildings.py').read_text()
shader=original.split("script=r'''",1)[1].split("'''.replace",1)[0]
shader=shader.replace('__DATA__',json.dumps(models))
shader=shader.replace('const palette={','const palette={C0:[.29,.47,.46],C1:[.67,.43,.33],C2:[.54,.58,.68],C3:[.69,.60,.40],')
shader=shader.replace('index===2?[.36,.51,.51]:(palette[polygon.kind]||[.73,.77,.77])','(palette[polygon.kind]||[.73,.77,.77])')
page=OUT/'component_render.html';page.write_text('<!doctype html><html><body><script>'+shader+'</script></body></html>',encoding='utf-8')
r=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless','--disable-gpu-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--virtual-time-budget=12000','--dump-dom',page.as_uri()],capture_output=True,check=True)
dom=r.stdout.decode();assert 'data-ready="true"' in dom
images=re.findall(r'<img id="model(\d+)" src="data:image/png;base64,([^"]+)"',dom);assert len(images)==3
for i,data in images:(OUT/f'courtyard_components_{i}.png').write_bytes(base64.b64decode(data))
(OUT/'geometry_sources.json').write_text(json.dumps([{'report':m['report']} for m in models],indent=2),encoding='utf-8')
print('Rendered three actual courtyard meshes with per-component colours')
