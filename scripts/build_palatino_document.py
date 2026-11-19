"""Apply Palatino consistently and add the corrected research figures."""
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.section import WD_SECTION_START, WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/methodology_palatino'
doc=Document(ROOT/'reports/methodology_v0_6/IFC_to_CityGML_Methodology.docx')
# Keep the matrix interpretation with the preceding study discussion instead
# of leaving one paragraph on a separate page after the dense matrix.
matrix_summary=next(p for p in doc.paragraphs if p.text.startswith('Declared type validation is separate'))
matrix_heading=next(p for p in doc.paragraphs if p.text.startswith('Appendix A'))
matrix_heading._p.addprevious(matrix_summary._p)
for style in doc.styles:
    if hasattr(style,'font'):
        style.font.name='Palatino Linotype'
        if style.name in ('Title','Subtitle','Heading 1','Heading 2'):
            style.font.color.rgb=RGBColor(0,0,0)
for part in [doc.part,*[s.footer.part for s in doc.sections]]:
    for fonts in part.element.xpath('.//w:rFonts'):
        for key in list(fonts.attrib):del fonts.attrib[key]
        for name in ('ascii','hAnsi','eastAsia','cs'):fonts.set(qn('w:'+name),'Palatino Linotype')
for fonts in doc.styles.element.xpath('.//w:rFonts'):
    for key in list(fonts.attrib):del fonts.attrib[key]
    for name in ('ascii','hAnsi','eastAsia','cs'):fonts.set(qn('w:'+name),'Palatino Linotype')
section=doc.add_section(WD_SECTION_START.NEW_PAGE)
section.orientation=WD_ORIENT.LANDSCAPE
section.page_width=Inches(11);section.page_height=Inches(8.5)
section.left_margin=section.right_margin=Inches(.4)
section.top_margin=Inches(.25);section.bottom_margin=Inches(.4);section.footer_distance=Inches(.12)
for i,path in enumerate(sorted((OUT/'figures').glob('*.png'))):
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before=Pt(0);p.paragraph_format.space_after=Pt(0)
    p.paragraph_format.line_spacing=1;p.paragraph_format.page_break_before=i>0
    p.paragraph_format.keep_together=True
    p.add_run().add_picture(str(path),width=Inches(10.2))
    p._p.xpath('.//wp:docPr')[0].set('descr',path.stem.replace('_',' '))
doc.core_properties.subject='Palatino edition with corrected depth-tested building renderings and six research figures'
dest=OUT/'IFC_to_CityGML_Palatino.docx';doc.save(dest);print(dest)
