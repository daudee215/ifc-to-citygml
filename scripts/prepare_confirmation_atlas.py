"""Build inspectable plotting data and depth-tested images from retained exports."""
import base64
import json
from pathlib import Path
import re
import subprocess
import shape_fidelity_experiment as first

ROOT=first.ROOT
OUT=ROOT/'reports/shape_fidelity_002'
OUT.mkdir(parents=True,exist_ok=True)
study=json.loads((ROOT/'results/experiments/shape_fidelity_002/evaluation.json').read_text())
families=list(first.SHAPES)
models=[]
references={}
for family in families:
    for angle in [0,15,30,45,60,75]:
        references[f'{family}_{angle}']=first.reference(family,angle)
    for mode in ['block','exterior','source']:
        row=next(r for r in study['baseline_rows'] if r['shape_family']==family and r['yaw_degrees']==0 and r['units']=='metre' and r['mode']==mode)
        gml=ROOT/row['report'].replace('.report.json','.gml')
        _,rings=first.read_footprint(gml)
        models.append({'family':family,'mode':mode,'source':str(gml.relative_to(ROOT)),
            'polygons':[{'kind':'Block' if mode=='block' else 'RoofSurface' if max(p[2] for p in ring)-min(p[2] for p in ring)<1e-7 else 'WallSurface','points':ring.tolist()} for ring in rings]})
payload={'baseline':study['baseline_rows'],'candidate':study['candidate_rows'],'references':references,
         'families':families,'angles':[0,15,30,45,60,75], 'models':[{k:v for k,v in m.items() if k!='polygons'} for m in models]}
(OUT/'plot_data.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
original=(ROOT/'scripts/render_depth_buildings.py').read_text()
shader=original.split("script=r'''",1)[1].split("'''.replace",1)[0]
shader=shader.replace('__DATA__',json.dumps(models)).replace('index===2','index%3===2')
html=OUT/'geometry_render.html'
html.write_text('<!doctype html><html><body><script>'+shader+'</script></body></html>',encoding='utf-8')
result=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless','--disable-gpu-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--virtual-time-budget=12000','--dump-dom',html.as_uri()],capture_output=True,check=True)
dom=result.stdout.decode('utf-8')
assert 'data-ready="true"' in dom
images=re.findall(r'<img id="model(\d+)" src="data:image/png;base64,([^"]+)"',dom)
assert len(images)==15
for index,encoded in images:(OUT/f'model_{index}.png').write_bytes(base64.b64decode(encoded))
print('Prepared 240 attempts, 30 references and 15 depth-tested exported models')
