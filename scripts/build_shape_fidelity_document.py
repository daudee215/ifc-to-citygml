"""Build the Palatino methodology and measured results supplement."""
from pathlib import Path
import re
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.section import WD_SECTION_START,WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from build_methodology_document import add_inline

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/shape_fidelity_001'
doc=Document();section=doc.sections[0]
section.page_width=Inches(8.5);section.page_height=Inches(11)
section.left_margin=section.right_margin=Inches(.8)
section.top_margin=Inches(.7);section.bottom_margin=Inches(.65)
section.footer_distance=Inches(.24)
for style in doc.styles:
    if hasattr(style,'font'):style.font.name='Palatino Linotype'
    for border in style.element.xpath('./w:pPr/w:pBdr'):
        border.getparent().remove(border)
normal=doc.styles['Normal'];normal.font.size=Pt(11)
normal.paragraph_format.line_spacing=1.04;normal.paragraph_format.space_after=Pt(7)
for name,size in [('Title',22),('Subtitle',11),('Heading 1',14)]:
    style=doc.styles[name];style.font.size=Pt(size);style.font.color.rgb=RGBColor(0,0,0)
    style.font.bold=name=='Heading 1';style.font.underline=False
    style.paragraph_format.space_after=Pt(9);style.paragraph_format.space_before=Pt(10 if name=='Heading 1' else 0)
footer=section.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
footer.add_run('IFC to CityGML   |   Methods and results supplement   |   ')
field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
for run in footer.runs:run.font.size=Pt(9)
lines=(OUT/'Methods_and_Results.md').read_text(encoding='utf-8').splitlines();i=0;newpage=False;subtitle=False
while i<len(lines):
    text=lines[i].strip()
    if not text:i+=1;continue
    if text=='<!-- PAGE -->':newpage=True;i+=1;continue
    if text.startswith('# '):doc.add_paragraph(text[2:],style='Title');subtitle=True
    elif text.startswith('## '):
        p=doc.add_heading(text[3:],1);p.paragraph_format.page_break_before=newpage;newpage=False
    elif text.startswith('|'):
        records=[]
        while i<len(lines) and lines[i].startswith('|'):
            cells=[s.strip() for s in lines[i].strip('|').split('|')]
            if not all(re.fullmatch('[: -]+',s) for s in cells):records.append(cells)
            i+=1
        table=doc.add_table(rows=0,cols=3);table.autofit=False
        widths=[3.05,1.9,1.95]
        for col,w in zip(table.columns,widths):col.width=Inches(w)
        for j,record in enumerate(records):
            row=table.add_row()
            for k,(cell,value) in enumerate(zip(row.cells,record)):
                cell.width=Inches(widths[k]);p=cell.paragraphs[0];p.paragraph_format.space_after=Pt(4);p.paragraph_format.space_before=Pt(4)
                if k:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                r=p.add_run(value);r.font.size=Pt(10);r.bold=j==0
                if j==0:
                    shd=OxmlElement('w:shd');shd.set(qn('w:fill'),'EDF1EF');cell._tc.get_or_add_tcPr().append(shd)
            if j==0:row._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
        borders=OxmlElement('w:tblBorders')
        for side in ['top','left','bottom','right','insideH','insideV']:
            el=OxmlElement('w:'+side);el.set(qn('w:val'),'single');el.set(qn('w:sz'),'4');el.set(qn('w:color'),'D9D9D9');borders.append(el)
        table._tbl.tblPr.append(borders)
        doc.add_paragraph().paragraph_format.space_after=Pt(2)
        continue
    else:
        p=doc.add_paragraph(style='Subtitle' if subtitle else 'Normal');add_inline(p,text);subtitle=False
    i+=1
section=doc.add_section(WD_SECTION_START.NEW_PAGE);section.orientation=WD_ORIENT.LANDSCAPE
section.page_width=Inches(11);section.page_height=Inches(8.5)
section.left_margin=section.right_margin=Inches(.4);section.top_margin=Inches(.25);section.bottom_margin=Inches(.4)
section.footer_distance=Inches(.12)
for i,path in enumerate(sorted((OUT/'figures').glob('*.png'))):
    p=doc.add_paragraph();p.paragraph_format.space_before=Pt(0);p.paragraph_format.space_after=Pt(0)
    p.paragraph_format.line_spacing=1;p.paragraph_format.page_break_before=i>0
    p.add_run().add_picture(str(path),width=Inches(10.2))
    p._p.xpath('.//wp:docPr')[0].set('descr',path.stem.replace('_',' '))
for fonts in doc.styles.element.xpath('.//w:rFonts'):
    for key in list(fonts.attrib):del fonts.attrib[key]
    for name in ['ascii','hAnsi','eastAsia','cs']:fonts.set(qn('w:'+name),'Palatino Linotype')
doc.core_properties.title='Geometric Fidelity in IFC to CityGML'
doc.core_properties.author='IFC to CityGML project'
doc.save(OUT/'Methods_and_Results.docx');print(OUT/'Methods_and_Results.docx')
