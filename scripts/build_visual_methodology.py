"""Preserve the research document and append six landscape figure plates."""
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.section import WD_SECTION_START, WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/methodology_visual_revision'
source=ROOT/'reports/methodology_v0_6/IFC_to_CityGML_Methodology.docx'
doc=Document(source)
section=doc.add_section(WD_SECTION_START.NEW_PAGE)
section.orientation=WD_ORIENT.LANDSCAPE
section.page_width=Inches(11)
section.page_height=Inches(8.5)
section.left_margin=section.right_margin=Inches(.4)
section.top_margin=Inches(.25)
section.bottom_margin=Inches(.4)
section.footer_distance=Inches(.12)
for i,path in enumerate(sorted((OUT/'figures').glob('*.png'))):
    p=doc.add_paragraph()
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before=Pt(0)
    p.paragraph_format.space_after=Pt(0)
    p.paragraph_format.line_spacing=1
    p.paragraph_format.page_break_before=i>0
    p.paragraph_format.keep_together=True
    p.add_run().add_picture(str(path),width=Inches(10.2))
    inline=p._p.xpath('.//wp:docPr')[0]
    inline.set('descr',path.stem.replace('_',' ')+'. Sources, units and limitations are included in the figure.')
doc.core_properties.subject='Illustrated research methodology with six revised graphics and preserved v0.6 evidence'
dest=OUT/'IFC_to_CityGML_Illustrated_Methodology.docx'
doc.save(dest)
print(dest)
