"""Create the shareable figure PDF and record font and evidence checks."""
import collections
import json
from pathlib import Path
import shutil
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree
from pypdf import PdfReader
from prepare_methodology_evidence import ROOT, sha, verify_frozen

OUT=ROOT/'reports/methodology_palatino'
figures=sorted((OUT/'figures').glob('*.svg'))
assert len(figures)==6
for p in figures:assert 'Palatino Linotype, Palatino, serif' in p.read_text(encoding='utf-8')
wrapper='''<!doctype html><html><head><meta charset="utf-8"><style>
@page{size:12.5in 9.1666667in;margin:0}html,body{margin:0;padding:0}
section{width:1200px;height:880px;break-after:page}section:last-child{break-after:auto}
svg{display:block;width:1200px;height:880px}
</style></head><body>'''+''.join('<section>'+p.read_text(encoding='utf-8')+'</section>' for p in figures)+'</body></html>'
html=OUT/'Research_Figures_Palatino.html';html.write_text(wrapper,encoding='utf-8')
pdf=OUT/'Research_Figures_Palatino.pdf'
subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless','--disable-gpu','--no-pdf-header-footer',f'--print-to-pdf={pdf}',html.as_uri()],capture_output=True,check=True)
assert len(PdfReader(pdf).pages)==6
full=OUT/'qa_final/IFC_to_CityGML_Palatino.pdf'
pages=PdfReader(full).pages
assert len(pages)==23
shutil.copyfile(full,OUT/full.name)
font_names=set()
for p in PdfReader(pdf).pages:
    for f in p['/Resources'].get('/Font',{}).values():font_names.add(str(f.get_object().get('/BaseFont')))
fonts='\n'.join(sorted(font_names))
assert 'PalatinoLinotype' in fonts,fonts
(OUT/'pdf_fonts.txt').write_text(fonts,encoding='utf-8')
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
with ZipFile(OUT/'IFC_to_CityGML_Palatino.docx') as a, ZipFile(ROOT/'reports/methodology_v0_6/IFC_to_CityGML_Methodology.docx') as b:
    x=etree.fromstring(a.read('word/document.xml'));y=etree.fromstring(b.read('word/document.xml'))
    assert collections.Counter(x.xpath('//w:t/text()',namespaces=ns))==collections.Counter(y.xpath('//w:t/text()',namespaces=ns))
    for f in x.xpath('//w:rFonts',namespaces=ns):
        assert f.get('{'+ns['w']+'}ascii')=='Palatino Linotype'
    assert len(x.xpath('//w:drawing',namespaces=ns))==6
readme='''# Palatino research figures and corrected building rendering

The six figures and the complete methodology document now use Palatino Linotype. The visual system uses restrained sage, slate and earth tones. Figure 3 has a new three column design. Figure 2 uses actual exported geometry rendered with WebGL depth testing, lighting and equal orthographic scale; this replaces the earlier polygon sorting illustration that incorrectly drew hidden triangles over the roof.

The visible roof defect was a drawing artifact. No roof faces were inserted, removed or repaired for appearance. Mesh geometry and the converter validation outcomes are unchanged. Windows and doors use their actual recorded WindowSurface and DoorSurface labels. The source surface illustration uses a uniform material colour.

Research_Figures_Palatino.pdf is the six page figure collection. Its type is vector Palatino and the building views are embedded high resolution raster renderings. The figures directory contains SVG and PNG versions. IFC_to_CityGML_Palatino.docx and its PDF are the complete Palatino methodology edition with six landscape figure pages. The matrix interpretation paragraph was moved before Appendix A to avoid a sparse continuation page; all original text is retained.

The original document and prior graphic editions remain available. Converter inputs, outputs and frozen releases were preserved. This is a presentation revision and does not change benchmark outcomes or establish geographic, semantic or flood accuracy.
'''
(OUT/'README.md').write_text(readme,encoding='utf-8')
with ZipFile(OUT/'Palatino_Figure_Pack.zip','w',ZIP_DEFLATED) as archive:
    for p in [*sorted((OUT/'figures').glob('*')),pdf,OUT/'README.md']:archive.write(p,p.relative_to(OUT))
result={'status':'passed','font':'Palatino Linotype','figure_count':6,'figure_pdf_pages':6,'full_document_pages':len(pages),
        'original_document_text_preserved':True,'building_visibility':'WebGL depth buffer, no mesh edits, equal orthographic scale',
        'frozen_releases':verify_frozen(),
        'files':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in [pdf,OUT/'IFC_to_CityGML_Palatino.docx',OUT/full.name,OUT/'Palatino_Figure_Pack.zip',*figures]]}
(OUT/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['files','frozen_releases']}))
