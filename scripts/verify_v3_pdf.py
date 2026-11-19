from pathlib import Path
import json,re,subprocess,unicodedata,xml.etree.ElementTree as ET
from pypdf import PdfReader
from PIL import Image,ImageDraw,ImageOps
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/v3';PDF=OUT/'V3_Research_and_Implementation_Palatino.pdf'
POPPLER='C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1026-487-0_26.1026.487.0_x64__3k8sg7r9htsxt/dependencies/native/poppler/Library/bin/pdftoppm.exe'
def normal(s):return re.sub(r'\s+','',unicodedata.normalize('NFKC',s))
reader=PdfReader(PDF);assert len(reader.pages)==16
texts=[normal(p.extract_text()) for p in reader.pages]
ends={0:'production qualification.',1:'frozen converter release remains separate.',2:'registration accuracy inferred.',15:'scientific qualification.'}
checks=[{'page':i+1,'end_text':s,'retained':normal(s) in texts[i]} for i,s in ends.items()]
figures=json.loads((OUT/'figure_index.json').read_text())['figures']
for i,name in enumerate(figures):
    elements=ET.parse(OUT/'figures'/(name+'.svg')).findall('.//{http://www.w3.org/2000/svg}text');tail=elements[-1].text[-70:]
    checks.append({'page':i+4,'end_text':tail,'retained':normal(tail) in texts[i+3]})
assert all(c['retained'] for c in checks),checks
subprocess.run([POPPLER,'-scale-to','1400','-png',str(PDF),str(OUT/'pdf_page')],check=True,timeout=60)
images=sorted(OUT.glob('pdf_page-*.png'));assert len(images)==16
montage=Image.new('RGB',(1800,1280),'#d8dbd6');draw=ImageDraw.Draw(montage)
for i,path in enumerate(images):
    montage.paste(ImageOps.contain(Image.open(path),(440,275)),((i%4)*450,(i//4)*320+30));draw.text(((i%4)*450+10,(i//4)*320+10),path.stem,fill='black')
montage.save(OUT/'PDF_Review_Montage.png')
fonts=sorted({str(f.get_object().get('/BaseFont')) for p in reader.pages for f in p['/Resources'].get_object().get('/Font',{}).get_object().values()})
assert any('Palatino' in f for f in fonts)
(OUT/'pdf_verification.json').write_text(json.dumps({'pages':len(reader.pages),'fonts':fonts,'all_page_renders_present':True,'required_end_text_retained':all(c['retained'] for c in checks),'page_end_checks':checks,'text_lengths':[len(p.extract_text()) for p in reader.pages]},indent=2),encoding='utf-8')
print('Verified 16 rendered pages, embedded Palatino and all required page-end text')
