"""Pinned exact native comparison; no invented per-face IFC attribution."""
from pathlib import Path
import json,subprocess,time
import numpy as np
import psutil
from lxml import etree as ET
from ifc_citygml.citygml_writer import NS,tag,child
from ifc_citygml.common import digest

def write_off(path,mesh):
    v=np.asarray(mesh['vertices']);f=np.asarray(mesh['triangles']);lines=['OFF',f'{len(v)} {len(f)} 0']
    lines.extend(' '.join(format(float(x),'.17g') for x in point) for point in v);lines.extend('3 '+' '.join(str(int(i)) for i in face) for face in f)
    Path(path).write_text('\n'.join(lines)+'\n')

def read_off(path):
    tokens=Path(path).read_text().split();assert tokens[0]=='OFF';n,m=int(tokens[1]),int(tokens[2]);offset=4+3*n
    vertices=np.asarray(tokens[4:offset],float).reshape(n,3).tolist();faces=[]
    for i in range(m):
        assert tokens[offset]=='3';faces.append([int(x) for x in tokens[offset+1:offset+4]]);offset+=4
    return {'vertices':vertices,'triangles':faces}

def components(mesh):
    faces=mesh['triangles'];byvertex={};adj=[set() for _ in faces]
    for i,f in enumerate(faces):
        for v in f:
            for j in byvertex.get(v,[]):adj[i].add(j);adj[j].add(i)
            byvertex.setdefault(v,[]).append(i)
    remaining=set(range(len(faces)));groups=[]
    while remaining:
        stack=[remaining.pop()];group=[]
        while stack:
            i=stack.pop();group.append(i)
            for j in adj[i]&remaining:remaining.remove(j);stack.append(j)
        groups.append({'vertices':mesh['vertices'],'triangles':[faces[i] for i in group]})
    return groups

def comparison_gml(mesh,srs_name):
    root=ET.Element(tag('core','CityModel'),nsmap=NS);root.set(tag('gml','id'),'exact_comparison')
    child(root,'gml','description','Exact arithmetic comparison only. Binary-double OFF serialization and CityGML validation are separate. No per-face IFC lineage claimed.')
    building=child(child(root,'core','cityObjectMember'),'bldg','Building');building.set(tag('gml','id'),'exact_building')
    multi=child(child(building,'core','lod2MultiSurface'),'gml','MultiSurface',srsName=srs_name,srsDimension='3')
    for j,component in enumerate(components(mesh)):
        surface=child(child(multi,'gml','surfaceMember'),'gml','CompositeSurface');surface.set(tag('gml','id'),'exact_c'+str(j))
        for i,f in enumerate(component['triangles']):
            polygon=child(child(surface,'gml','surfaceMember'),'gml','Polygon');polygon.set(tag('gml','id'),f'exact_c{j}_t{i}')
            ring=child(child(polygon,'gml','exterior'),'gml','LinearRing');points=np.asarray(mesh['vertices'])[[*f,f[0]]]
            child(ring,'gml','posList',' '.join(format(float(x),'.17g') for x in points.flat),srsDimension='3')
    return ET.tostring(root,pretty_print=True,xml_declaration=True,encoding='UTF-8')

def exact_union(source,folder,executable,timeout=90):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False);elements=[e for b in source['buildings'] for e in b['elements']]
    if len(source['buildings'])!=1 or not 1<len(elements)<=16:return {'status':'unsupported','reason':'Native comparator supports one building and 2–16 selected source meshes'},None
    inputs=[]
    for i,e in enumerate(elements):path=folder/f'input_{i}.off';write_off(path,e);inputs.append(path)
    output=folder/'union.off';start=time.perf_counter();peak=0
    process=subprocess.Popen([str(executable),str(output),*[str(p) for p in inputs]],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    monitor=psutil.Process(process.pid);expired=False
    while process.poll() is None:
        try:peak=max(peak,monitor.memory_info().rss)
        except psutil.NoSuchProcess:pass
        if time.perf_counter()-start>timeout:process.kill();expired=True;break
        time.sleep(.02)
    stdout,stderr=process.communicate();(folder/'process.log').write_text(stdout+'\n'+stderr,encoding='utf-8')
    record={'status':'timeout' if expired else 'completed' if process.returncode==0 else 'unsupported_or_failed','exit_code':process.returncode,'stdout':stdout,'stderr':stderr,
        'wall_seconds':time.perf_counter()-start,'sampled_peak_process_rss_bytes':peak,'memory_scope':'RSS sampled every 20 ms; sampling can miss true peak','executable_sha256':digest(Path(executable)),'per_face_attribution':False}
    data=None
    if record['status']=='completed':
        data=comparison_gml(read_off(output),source['profile']['srs_name']);(folder/'comparison.gml').write_bytes(data);record['gml_sha256']=digest(folder/'comparison.gml');record['rational_vertices_sha256']=digest(output.with_suffix('.off.rational.txt'))
    return record,data
