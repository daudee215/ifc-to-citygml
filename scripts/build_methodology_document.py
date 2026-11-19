"""Create the research DOCX and editable Markdown using the bundled Python runtime."""
from pathlib import Path
import json
import re

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/methodology_v0_6"


def md_table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|",
                      *["| " + " | ".join(str(v).replace("|", "/") for v in row) + " |" for row in rows]])


def add_inline(paragraph, text):
    pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    end = 0
    for match in pattern.finditer(text):
        paragraph.add_run(text[end:match.start()])
        link = OxmlElement("w:hyperlink")
        link.set(qn("r:id"), paragraph.part.relate_to(match.group(2), RT.HYPERLINK, is_external=True))
        run = OxmlElement("w:r")
        properties = OxmlElement("w:rPr")
        style = OxmlElement("w:rStyle")
        style.set(qn("w:val"), "Hyperlink")
        properties.append(style)
        run.append(properties)
        content = OxmlElement("w:t")
        content.text = match.group(1)
        run.append(content)
        link.append(run)
        paragraph._p.append(link)
        end = match.end()
    paragraph.add_run(text[end:])


def configure(doc):
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.left_margin = section.right_margin = Inches(.85)
    section.top_margin, section.bottom_margin = Inches(.75), Inches(.7)
    section.header_distance = section.footer_distance = Inches(.28)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Cambria", Pt(11)
    normal.paragraph_format.line_spacing = 1.10
    normal.paragraph_format.space_after = Pt(6)
    for name, size in (("Title", 25), ("Heading 1", 15), ("Heading 2", 12)):
        style = doc.styles[name]
        style.font.name, style.font.size = "Cambria", Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.underline = False
        style.font.bold = name != "Title"
        style.paragraph_format.space_before = Pt(14 if name != "Title" else 0)
        style.paragraph_format.space_after = Pt(8)
        style.paragraph_format.keep_with_next = True
        borders = style.element.xpath("./w:pPr/w:pBdr")
        for border in borders:
            border.getparent().remove(border)
    subtitle = doc.styles["Subtitle"]
    subtitle.font.name, subtitle.font.size = "Cambria", Pt(13)
    subtitle.font.color.rgb = RGBColor(55, 55, 55)
    subtitle.paragraph_format.space_after = Pt(8)
    if "Code" not in doc.styles:
        code = doc.styles.add_style("Code", 1)
        code.font.name, code.font.size = "Consolas", Pt(9)
        code.paragraph_format.line_spacing = 1.05
        code.paragraph_format.space_before = code.paragraph_format.space_after = Pt(6)
        code.paragraph_format.keep_together = True
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("IFC to CityGML   |   Research draft   |   ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    for run in footer.runs:
        run.font.name, run.font.size = "Cambria", Pt(9)
        run.font.color.rgb = RGBColor(80, 80, 80)
    doc.core_properties.title = "IFC to CityGML Building Conversion"
    doc.core_properties.subject = "Research methodology and version 0.6 evaluation with Torino context"
    doc.core_properties.author = "IFC to CityGML project"
    doc.core_properties.keywords = "IFC CityGML Torino geometry semantics provenance methodology"


def add_table(doc, rows, dense=False):
    count = len(rows[0])
    table = doc.add_table(rows=1, cols=count)
    table.autofit = False
    if dense:
        widths = [1.02, .52, .54, .85, .95, .72, 1.40] if count == 7 else [6.8 / count] * count
    elif count == 2:
        widths = [3.8, 3.0]
    elif count == 3:
        widths = [1.7, 3.05, 2.05]
    elif count == 4:
        widths = [1.28, .66, 3.68, 1.18]
    elif count == 5:
        widths = [2.05, .78, .90, .65, 2.42]
    elif count == 6:
        widths = ([1.25, 1.15, .80, 1.12, 1.30, 1.18] if rows[0][1] == "Contributors"
                  else [1.5, 1.15, 1.05, .9, .65, 1.55])
    else:
        widths = [6.8 / count] * count
    scale = 6.8 / sum(widths)
    widths = [v * scale for v in widths]
    for col, width in zip(table.columns, widths):
        col.width = Inches(width)
    for index, values in enumerate(rows):
        cells = table.rows[0].cells if index == 0 else table.add_row().cells
        trpr = table.rows[index]._tr.get_or_add_trPr()
        cant_split = OxmlElement("w:cantSplit")
        trpr.append(cant_split)
        if index == 0:
            repeat = OxmlElement("w:tblHeader")
            trpr.append(repeat)
        for ci, (cell, text) in enumerate(zip(cells, values)):
            cell.width = Inches(widths[ci])
            tcpr = cell._tc.get_or_add_tcPr()
            margins = OxmlElement("w:tcMar")
            for edge, value in (("top", 35 if dense else 65), ("bottom", 35 if dense else 65), ("left", 85), ("right", 85)):
                node = OxmlElement("w:" + edge)
                node.set(qn("w:w"), str(value))
                node.set(qn("w:type"), "dxa")
                margins.append(node)
            tcpr.append(margins)
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.02 if dense else 1.06
            add_inline(paragraph, text)
            for run in paragraph.runs:
                run.font.name = "Cambria"
                run.font.size = Pt(9.5 if dense else 10)
                run.bold = index == 0
            if dense and ci > 0:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif ci > 0 and re.fullmatch(r"[\d. /eE+-]+", text):
                paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if index == 0:
                shade = OxmlElement("w:shd")
                shade.set(qn("w:fill"), "EEF1F3")
                tcpr.append(shade)
    after = doc.add_paragraph()
    after.paragraph_format.space_after = Pt(3)
    after.paragraph_format.line_spacing = .3
    after.add_run().font.size = Pt(3)


def main():
    evidence = json.loads((OUT / "evidence_snapshot.json").read_text())
    source = (OUT / "methodology_source.md").read_text(encoding="utf-8")
    case_names = {"controlled_ifc4": "Semantic IFC4", "controlled_ifc2x3": "Semantic IFC2x3", "fixture_m": "F m",
                  "fixture_mm": "F mm", "fixture_rotated": "F rot", "fixture_ifc2x3": "F 2x3", "duplex": "Duplex",
                  "clinic": "Clinic", "gaia_renovation": "Gaia", "digitalhub": "DigitalHub"}
    datasets = md_table(["Case", "Schema", "Provenance and status", "Licence"], [
        ["Duplex", "IFC2x3", "Community architectural sample not established as a Torino or surveyed building", "CC BY 4.0"],
        ["Clinic", "IFC2x3", "Community medical clinic sample not established as a Torino or surveyed building", "CC BY 4.0"],
        ["Gaia", "IFC4", "CHEK renovation demonstration independent as built agreement not established", "CC BY 4.0"],
        ["DigitalHub", "IFC4", "RWTH fictional teaching design not an as built building", "MIT"]])
    profiles = md_table(["CLI profile names", "Declared geometry", "Coordinate and interpretation contract"], [
        ["block and engineering-block", "Building lod1Solid", "Selected body vertices form an aggregate box engineering variant retains unapplied map metadata"],
        ["exterior and engineering-exterior", "Thematic envelope MultiSurface", "Material union with logged changes heuristic labels and separate Solid diagnostic"],
        ["source and engineering-source", "Constructive and filling MultiSurfaces", "Unmodified selected SDK tessellations in identity engineering output"],
        ["map", "Union envelope with native map operation", "Strict supported IFC4 metadata complete three axis metre CRS and placement checks"]])
    source_rows = [[case_names[r["case"]], f"{r['expected_features']} / {r['exported_features']}", f"{r['triangles_checked']:,}",
                    str(len(r["omissions"])), str(len(r["issues"])), r["status"]] for r in evidence["source_audits"]["cases"]]
    blocks = [[case_names[r["case"]], str(b["physical_contributors"]), str(b["omitted"]), str(b["annotation_only_omissions"]),
               f"{b['xml_max_corner_error_m']:.3g}", r["status"]] for r in evidence["block_audits"]["cases"] for b in r["buildings"]]
    software = evidence["clean_install"]["doctor"]["software"]
    software_rows = [["Python", "3.13.15"], *[[name, version] for name, version in software.items()], ["val3dity", "2.7.0"]]
    modes = {"block": "B", "exterior": "U", "source": "S", "map": "M", "engineering-block": "EB", "engineering-exterior": "EU", "engineering-source": "ES"}
    matrix = []
    def flag(value):
        return "P" if value == "passed" else "F" if value == "failed" else "—"
    for r in evidence["research"]["cases"]:
        block = r["mode"].endswith("block")
        matrix.append([case_names[r["case"]], modes[r["mode"]], flag(r["conversion_status"]),
                       "Solid" if block else "MS", flag(r["independent_target_status"]),
                       "N A" if block else flag(r["solid_diagnostic_status"]), f"{r['runtime_seconds']:.3f}"])
    replacements = {"DATASET_TABLE": datasets, "PROFILE_TABLE": profiles,
        "SOURCE_TABLE": md_table(["Case", "Expected and exported", "Triangles", "Omissions", "Issues", "Audit"], source_rows),
        "BLOCK_TABLE": md_table(["Case", "Contributors", "Omitted", "Annotations", "XML error m", "Audit"], blocks),
        "SOFTWARE_TABLE": md_table(["Component", "Recorded version"], software_rows),
        "ATTEMPT_TABLE": md_table(["Case", "Mode", "Export", "Target type", "Target check", "Solid extra", "Time s"], matrix)}
    for key, value in replacements.items():
        source = source.replace("{{" + key + "}}", value)
    if "{{" in source:
        raise ValueError("Unresolved document placeholder")
    markdown = OUT / "IFC_to_CityGML_Methodology.md"
    markdown.write_text(source, encoding="utf-8")
    doc = Document()
    configure(doc)
    lines = source.splitlines()
    i, in_appendix, title_seen, subtitle_seen = 0, False, False, False
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("<!--"):
            i += 1
            continue
        if line.startswith("# "):
            doc.add_paragraph(line[2:], style="Title")
            title_seen = True
        elif line.startswith("## "):
            title = line[3:]
            in_appendix = title.startswith("Appendix A")
            heading = doc.add_heading(title, level=1)
            if title.startswith("Appendix") or title.startswith("1 Research"):
                heading.paragraph_format.page_break_before = True
        elif line.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            doc.add_paragraph("\n".join(code), style="Code")
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                values = [v.strip() for v in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[:\- ]+", value) for value in values):
                    rows.append(values)
                i += 1
            add_table(doc, rows, dense=in_appendix)
            continue
        else:
            if title_seen and not subtitle_seen:
                paragraph = doc.add_paragraph(line, style="Subtitle")
                subtitle_seen = True
            else:
                paragraph = doc.add_paragraph()
                add_inline(paragraph, line)
        i += 1
    path = OUT / "IFC_to_CityGML_Methodology.docx"
    doc.save(path)
    count = len(re.findall(r"\b[\w-]+\b", source))
    print(json.dumps({"docx": str(path), "markdown": str(markdown), "word_tokens_including_tables": count, "tables": len(doc.tables)}))


if __name__ == "__main__":
    main()
