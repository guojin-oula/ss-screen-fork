"""Build the formal SS-Screen Chinese user manual from its Markdown source."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

MANUAL_TITLE = "固溶体可调带隙材料筛选软件用户使用手册"
MANUAL_SUBTITLE = "SS-Screen 完整功能版 V1.4"
SOURCE_BASELINE = "当前实现基线：ss-screen 0.1.0"
AUTHOR = "SS-Screen Project"

# compact_reference_guide with named A4/CJK overrides from the approved design.
PAGE_WIDTH_CM = 21.0
PAGE_HEIGHT_CM = 29.7
MARGIN_TOP_CM = 2.54
MARGIN_BOTTOM_CM = 2.54
MARGIN_LEFT_CM = 2.60
MARGIN_RIGHT_CM = 2.60
CONTENT_WIDTH_DXA = 8957  # 158 mm, derived from A4 width minus side margins.
TABLE_INDENT_DXA = 120
CELL_MARGIN_TOP_DXA = 90
CELL_MARGIN_BOTTOM_DXA = 90
CELL_MARGIN_SIDE_DXA = 120

FONT_CJK = "Microsoft YaHei"
FONT_LATIN = "Calibri"
FONT_CODE = "Consolas"

NAVY = "183B56"
BLUE = "2E74B5"
DARK_BLUE = "1F4D78"
INK = "263238"
MUTED = "66737E"
LIGHT_BLUE = "E8F1F8"
LIGHT_GRAY = "F3F5F7"
MID_GRAY = "D5DDE3"
ORANGE_FILL = "FFF1DE"
ORANGE_TEXT = "8A4B08"
GREEN_FILL = "E9F5EE"
GREEN_TEXT = "276749"
RED = "9B1C1C"
WHITE = "FFFFFF"

REQUIRED_HEADINGS = (
    "第一部分 软件概述",
    "第二部分 安装与配置",
    "第三部分 完整科研工作流",
    "第四部分 结果解释与科研决策",
    "第五部分 CLI与文件契约参考",
    "第六部分 完整示例与附录",
)
FORBIDDEN_PLACEHOLDERS = ("TO" + "DO", "TB" + "D", "待补充", "以后填写")


@dataclass(frozen=True)
class Block:
    kind: str
    text: str = ""
    level: int = 0
    language: str = ""
    rows: tuple[tuple[str, ...], ...] = ()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Markdown source")
    parser.add_argument("--output", type=Path, required=True, help="Output DOCX")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run source and DOCX structural checks after building",
    )
    return parser.parse_args()


def validate_source(text: str) -> None:
    missing = [heading for heading in REQUIRED_HEADINGS if f"# {heading}" not in text]
    if missing:
        raise ValueError(f"missing required manual headings: {missing}")
    for token in FORBIDDEN_PLACEHOLDERS:
        if token in text:
            raise ValueError(f"forbidden placeholder found: {token}")
    if "[当前可用]" not in text:
        raise ValueError("manual lacks current-availability markers")
    if "完整版本预期接口" not in text:
        raise ValueError("manual lacks future-interface markers")
    if "不能直接用来证明当前版本已经具有所有规划功能" not in text:
        raise ValueError("manual lacks the planned-versus-current disclaimer")


def is_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def parse_table_row(line: str) -> tuple[str, ...]:
    return tuple(cell.strip() for cell in line.strip().strip("|").split("|"))


def parse_markdown(text: str) -> list[Block]:
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.strip() == "## 文档状态图例"),
        0,
    )
    lines = lines[start:]
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("```"):
            language = stripped[3:].strip()
            i += 1
            code_lines: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            blocks.append(Block("code", "\n".join(code_lines), language=language))
            continue
        image_match = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if image_match:
            blocks.append(
                Block(
                    "image",
                    image_match.group(1).strip(),
                    language=image_match.group(2).strip(),
                )
            )
            i += 1
            continue
        heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading_match:
            blocks.append(
                Block(
                    "heading",
                    heading_match.group(2).strip(),
                    level=len(heading_match.group(1)),
                )
            )
            i += 1
            continue
        if stripped == "---":
            blocks.append(Block("rule"))
            i += 1
            continue
        if stripped.startswith(">"):
            quote_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip()[1:].strip())
                i += 1
            blocks.append(Block("callout", " ".join(quote_lines)))
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines: list[str] = []
            while i < len(lines):
                candidate = lines[i].strip()
                if not (candidate.startswith("|") and candidate.endswith("|")):
                    break
                table_lines.append(candidate)
                i += 1
            rows = tuple(
                parse_table_row(line) for line in table_lines if not is_table_separator(line)
            )
            if rows:
                blocks.append(Block("table", rows=rows))
            continue
        list_match = re.match(r"^[-*]\s+(.+)$", stripped)
        number_match = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if list_match or number_match:
            kind = "bullet" if list_match else "number"
            match = list_match or number_match
            assert match is not None
            blocks.append(Block(kind, match.group(1).strip()))
            i += 1
            continue
        paragraph_lines = [stripped]
        i += 1
        while i < len(lines):
            candidate = lines[i].strip()
            if not candidate:
                break
            if (
                candidate.startswith("```")
                or candidate.startswith("![")
                or candidate.startswith("#")
                or candidate.startswith(">")
                or candidate == "---"
                or (candidate.startswith("|") and candidate.endswith("|"))
                or re.match(r"^[-*]\s+", candidate)
                or re.match(r"^\d+[.)]\s+", candidate)
            ):
                break
            paragraph_lines.append(candidate)
            i += 1
        blocks.append(Block("paragraph", " ".join(paragraph_lines)))
    return blocks


def set_run_font(
    run,
    *,
    latin: str = FONT_LATIN,
    east_asia: str = FONT_CJK,
    size: float | None = None,
    color: str | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
) -> None:
    run.font.name = latin
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.rFonts
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)
    rfonts.set(qn("w:eastAsia"), east_asia)
    if size is not None:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for edge, value in (
        ("top", CELL_MARGIN_TOP_DXA),
        ("bottom", CELL_MARGIN_BOTTOM_DXA),
        ("start", CELL_MARGIN_SIDE_DXA),
        ("end", CELL_MARGIN_SIDE_DXA),
    ):
        tag = tc_mar.find(qn(f"w:{edge}"))
        if tag is None:
            tag = OxmlElement(f"w:{edge}")
            tc_mar.append(tag)
        tag.set(qn("w:w"), str(value))
        tag.set(qn("w:type"), "dxa")


def set_table_borders(table, color: str = MID_GRAY, size: str = "4") -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def visual_length(text: str) -> int:
    return sum(2 if ord(char) > 127 else 1 for char in text)


def compute_column_widths(rows: Sequence[Sequence[str]]) -> list[int]:
    count = len(rows[0])
    maxima = []
    for column in range(count):
        maximum = max(visual_length(row[column]) for row in rows if column < len(row))
        maxima.append(max(6.0, min(42.0, maximum**0.65 * 4.0)))
    if count == 2 and max(visual_length(row[0]) for row in rows) <= 20:
        maxima[0] *= 0.72
        maxima[1] *= 1.15
    total = sum(maxima)
    widths = [int(CONTENT_WIDTH_DXA * weight / total) for weight in maxima]
    widths[-1] += CONTENT_WIDTH_DXA - sum(widths)
    return widths


def set_table_geometry(table, widths: Sequence[int], *, indent: int = TABLE_INDENT_DXA) -> None:
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(indent))
    tbl_ind.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        grid_col = OxmlElement("w:gridCol")
        grid_col.set(qn("w:w"), str(width))
        grid.append(grid_col)
    for row in table.rows:
        for index, cell in enumerate(row.cells):
            width = widths[min(index, len(widths) - 1)]
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(width))
            tc_w.set(qn("w:type"), "dxa")
            cell.width = Cm(width / 1440 * 2.54)


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    tr_pr.append(header)


def set_paragraph_border(paragraph, color: str = MID_GRAY, size: str = "6") -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = p_pr.find(qn("w:pBdr"))
    if p_bdr is None:
        p_bdr = OxmlElement("w:pBdr")
        p_pr.append(p_bdr)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), color)
    p_bdr.append(bottom)


def set_callout_paragraph_style(paragraph, *, fill: str, border: str) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    p_pr.append(shading)
    p_bdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), "16")
    left.set(qn("w:space"), "8")
    left.set(qn("w:color"), border)
    p_bdr.append(left)
    p_pr.append(p_bdr)


def configure_styles(doc: Document) -> None:
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = FONT_LATIN
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor.from_string(INK)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_CJK)
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.35
    normal.paragraph_format.widow_control = True

    heading_tokens = {
        "Heading 1": (18, NAVY, 18, 10),
        "Heading 2": (14, BLUE, 14, 7),
        "Heading 3": (12, DARK_BLUE, 10, 5),
    }
    for name, (size, color, before, after) in heading_tokens.items():
        style = styles[name]
        style.font.name = FONT_LATIN
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_CJK)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.widow_control = True

    for name in ("List Bullet", "List Number"):
        style = styles[name]
        style.font.name = FONT_LATIN
        style.font.size = Pt(10.5)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_CJK)
        style.paragraph_format.left_indent = Cm(0.95)
        style.paragraph_format.first_line_indent = Cm(-0.48)
        style.paragraph_format.space_after = Pt(4)
        style.paragraph_format.line_spacing = 1.25

    if "Code Block" not in styles:
        code = styles.add_style("Code Block", WD_STYLE_TYPE.PARAGRAPH)
    else:
        code = styles["Code Block"]
    code.font.name = FONT_CODE
    code.font.size = Pt(8.5)
    code._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_CJK)
    code.paragraph_format.left_indent = Cm(0.35)
    code.paragraph_format.right_indent = Cm(0.20)
    code.paragraph_format.space_before = Pt(2)
    code.paragraph_format.space_after = Pt(2)
    code.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE


def configure_section(doc: Document) -> None:
    doc.settings.odd_and_even_pages_header_footer = False
    section = doc.sections[0]
    section.page_width = Cm(PAGE_WIDTH_CM)
    section.page_height = Cm(PAGE_HEIGHT_CM)
    section.top_margin = Cm(MARGIN_TOP_CM)
    section.bottom_margin = Cm(MARGIN_BOTTOM_CM)
    section.left_margin = Cm(MARGIN_LEFT_CM)
    section.right_margin = Cm(MARGIN_RIGHT_CM)
    section.header_distance = Cm(1.25)
    section.footer_distance = Cm(1.25)
    section.different_first_page_header_footer = True


def add_page_field(paragraph) -> None:
    paragraph.add_run("第 ")
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend((begin, instruction, separate, text, end))
    paragraph.add_run(" 页")


def add_header_footer(doc: Document) -> None:
    section = doc.sections[0]
    header = section.header
    paragraph = header.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("SS-Screen · 完整功能版用户使用手册")
    set_run_font(run, size=8.5, color=MUTED)
    set_paragraph_border(paragraph, color=MID_GRAY, size="4")

    footer = section.footer
    paragraph = footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_page_field(paragraph)
    for run in paragraph.runs:
        set_run_font(run, size=8.5, color=MUTED)


def add_cover(doc: Document) -> None:
    for _ in range(5):
        doc.add_paragraph()
    kicker = doc.add_paragraph()
    kicker.alignment = WD_ALIGN_PARAGRAPH.CENTER
    kicker.paragraph_format.space_after = Pt(20)
    run = kicker.add_run("科研软件 · 用户使用手册")
    set_run_font(run, size=11, color=BLUE, bold=True)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(12)
    run = title.add_run(MANUAL_TITLE)
    set_run_font(run, size=28, color=NAVY, bold=True)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(34)
    run = subtitle.add_run(MANUAL_SUBTITLE)
    set_run_font(run, size=16, color=DARK_BLUE)

    rule = doc.add_paragraph()
    set_paragraph_border(rule, color=BLUE, size="10")
    rule.paragraph_format.space_after = Pt(26)

    metadata = (
        ("适用对象", "材料科学、计算材料学和电子结构计算科研用户"),
        ("文档性质", "未来完整产品使用说明与目标接口基线"),
        ("实现基线", "ss-screen 0.1.0"),
        ("编制日期", "2026年7月22日"),
    )
    for label, value in metadata:
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.left_indent = Cm(3.3)
        paragraph.paragraph_format.right_indent = Cm(1.2)
        paragraph.paragraph_format.space_after = Pt(4)
        label_run = paragraph.add_run(f"{label}　")
        set_run_font(label_run, size=10, color=MUTED, bold=True)
        value_run = paragraph.add_run(value)
        set_run_font(value_run, size=10, color=INK)

    doc.add_paragraph()
    add_callout(
        doc,
        "本手册描述未来完整功能。标为“完整版本预期接口”的命令当前尚未实现；"
        "当前可运行能力以 ss-screen 0.1.0 的真实 CLI 和测试为准。",
        kind="future",
    )
    doc.add_page_break()


def add_static_toc(doc: Document, blocks: Sequence[Block]) -> None:
    heading = doc.add_paragraph("目录")
    heading.style = doc.styles["Heading 1"]
    heading.paragraph_format.page_break_before = False
    used_lines = 2
    page_line_budget = 16
    for block in blocks:
        if block.kind != "heading" or block.level > 2:
            continue
        line_cost = 2 if block.level == 1 else 1
        if used_lines + line_cost > page_line_budget:
            doc.add_page_break()
            used_lines = 0
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.left_indent = Cm(0 if block.level == 1 else 0.8)
        paragraph.paragraph_format.space_after = Pt(3)
        paragraph.paragraph_format.keep_together = True
        paragraph.paragraph_format.keep_with_next = block.level == 1
        run = paragraph.add_run(block.text)
        set_run_font(
            run,
            size=10.5 if block.level == 1 else 9.5,
            color=NAVY if block.level == 1 else INK,
            bold=block.level == 1,
        )
        used_lines += line_cost
    note = doc.add_paragraph("说明：目录按章节层级列出；页码以 Word/PDF 渲染结果为准。")
    note.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for run in note.runs:
        set_run_font(run, size=8.5, color=MUTED, italic=True)
    doc.add_page_break()


def add_inline_runs(paragraph, text: str, *, color: str = INK, size: float = 10.5) -> None:
    pattern = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")
    cursor = 0
    for match in pattern.finditer(text):
        if match.start() > cursor:
            run = paragraph.add_run(text[cursor : match.start()])
            set_run_font(run, size=size, color=color)
        token = match.group(0)
        if token.startswith("**"):
            run = paragraph.add_run(token[2:-2])
            set_run_font(run, size=size, color=color, bold=True)
        elif token.startswith("`"):
            run = paragraph.add_run(token[1:-1])
            set_run_font(
                run,
                latin=FONT_CODE,
                east_asia=FONT_CJK,
                size=max(8.5, size - 1),
                color=DARK_BLUE,
            )
            shading = OxmlElement("w:shd")
            shading.set(qn("w:fill"), LIGHT_GRAY)
            run._element.get_or_add_rPr().append(shading)
        else:
            label = token[1 : token.index("]")]
            run = paragraph.add_run(label)
            set_run_font(run, size=size, color=BLUE)
            run.underline = True
        cursor = match.end()
    if cursor < len(text):
        run = paragraph.add_run(text[cursor:])
        set_run_font(run, size=size, color=color)


def add_callout(doc: Document, text: str, *, kind: str | None = None) -> None:
    detected = kind
    if detected is None:
        detected = "future" if "完整版本预期接口" in text else "note"
        if "科研边界" in text or "解释注意" in text:
            detected = "warning"
    fill, color = {
        "future": (ORANGE_FILL, ORANGE_TEXT),
        "warning": ("FDECEC", RED),
        "current": (GREEN_FILL, GREEN_TEXT),
        "note": (LIGHT_BLUE, DARK_BLUE),
    }[detected]
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.left_indent = Cm(0.35)
    paragraph.paragraph_format.right_indent = Cm(0.20)
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(7)
    paragraph.paragraph_format.line_spacing = 1.2
    set_callout_paragraph_style(paragraph, fill=fill, border=color)
    add_inline_runs(paragraph, text, color=color, size=9.5)


def add_markdown_table(doc: Document, rows: Sequence[Sequence[str]]) -> None:
    column_count = max(len(row) for row in rows)
    normalized = [tuple(row) + ("",) * (column_count - len(row)) for row in rows]
    table = doc.add_table(rows=len(normalized), cols=column_count)
    widths = compute_column_widths(normalized)
    set_table_geometry(table, widths)
    set_table_borders(table)
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
    set_repeat_table_header(table.rows[0])
    for row_index, (word_row, values) in enumerate(zip(table.rows, normalized, strict=True)):
        for cell, value in zip(word_row.cells, values, strict=True):
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if row_index == 0:
                set_cell_shading(cell, LIGHT_BLUE)
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_before = Pt(0)
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.15
            if column_count > 2 and visual_length(value) <= 18:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_inline_runs(
                paragraph,
                value,
                color=NAVY if row_index == 0 else INK,
                size=9 if row_index == 0 else 8.8,
            )
            if row_index == 0:
                for run in paragraph.runs:
                    run.bold = True
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(2)


def add_code_block(doc: Document, text: str, language: str) -> None:
    label = language or "text"
    header = doc.add_paragraph()
    header.paragraph_format.space_before = Pt(7)
    header.paragraph_format.space_after = Pt(1)
    header.paragraph_format.keep_with_next = True
    run = header.add_run(label.upper())
    set_run_font(run, latin=FONT_CODE, east_asia=FONT_CJK, size=7.5, color=MUTED, bold=True)
    for line in text.splitlines() or [""]:
        paragraph = doc.add_paragraph(style="Code Block")
        paragraph.paragraph_format.keep_together = False
        p_pr = paragraph._p.get_or_add_pPr()
        shading = OxmlElement("w:shd")
        shading.set(qn("w:fill"), LIGHT_GRAY)
        p_pr.append(shading)
        run = paragraph.add_run(line if line else " ")
        set_run_font(
            run,
            latin=FONT_CODE,
            east_asia=FONT_CJK,
            size=8.2,
            color=INK,
        )
    doc.add_paragraph().paragraph_format.space_after = Pt(1)


def create_list_numbering(doc: Document, *, ordered: bool) -> int:
    """Create an independent real Word list so each Markdown list restarts."""
    numbering = doc.part.numbering_part.element
    abstract_ids = [
        int(element.get(qn("w:abstractNumId")))
        for element in numbering.findall(qn("w:abstractNum"))
    ]
    num_ids = [int(element.get(qn("w:numId"))) for element in numbering.findall(qn("w:num"))]
    abstract_id = max(abstract_ids, default=-1) + 1
    num_id = max(num_ids, default=0) + 1

    abstract = OxmlElement("w:abstractNum")
    abstract.set(qn("w:abstractNumId"), str(abstract_id))
    multi_level = OxmlElement("w:multiLevelType")
    multi_level.set(qn("w:val"), "singleLevel")
    abstract.append(multi_level)

    level = OxmlElement("w:lvl")
    level.set(qn("w:ilvl"), "0")
    start = OxmlElement("w:start")
    start.set(qn("w:val"), "1")
    level.append(start)
    num_format = OxmlElement("w:numFmt")
    num_format.set(qn("w:val"), "decimal" if ordered else "bullet")
    level.append(num_format)
    level_text = OxmlElement("w:lvlText")
    level_text.set(qn("w:val"), "%1." if ordered else "•")
    level.append(level_text)
    justification = OxmlElement("w:lvlJc")
    justification.set(qn("w:val"), "left")
    level.append(justification)
    p_pr = OxmlElement("w:pPr")
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "num")
    tab.set(qn("w:pos"), "540")
    tabs.append(tab)
    p_pr.append(tabs)
    indent = OxmlElement("w:ind")
    indent.set(qn("w:left"), "540")
    indent.set(qn("w:hanging"), "270")
    p_pr.append(indent)
    level.append(p_pr)
    abstract.append(level)
    first_num_index = next(
        (index for index, element in enumerate(numbering) if element.tag == qn("w:num")),
        len(numbering),
    )
    numbering.insert(first_num_index, abstract)

    num = OxmlElement("w:num")
    num.set(qn("w:numId"), str(num_id))
    abstract_ref = OxmlElement("w:abstractNumId")
    abstract_ref.set(qn("w:val"), str(abstract_id))
    num.append(abstract_ref)
    numbering.append(num)
    return num_id


def apply_list_numbering(paragraph, num_id: int) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    num_pr = p_pr.find(qn("w:numPr"))
    if num_pr is None:
        num_pr = OxmlElement("w:numPr")
        p_pr.append(num_pr)
    level = OxmlElement("w:ilvl")
    level.set(qn("w:val"), "0")
    number = OxmlElement("w:numId")
    number.set(qn("w:val"), str(num_id))
    num_pr.append(level)
    num_pr.append(number)


def add_body(
    doc: Document,
    blocks: Sequence[Block],
    *,
    asset_base: Path | None = None,
) -> None:
    active_list_kind: str | None = None
    active_num_id: int | None = None
    for index, block in enumerate(blocks):
        if block.kind not in {"bullet", "number"}:
            active_list_kind = None
            active_num_id = None
        if block.kind == "rule":
            continue
        if block.kind == "heading":
            paragraph = doc.add_paragraph(style=f"Heading {block.level}")
            if block.level == 1:
                paragraph.paragraph_format.page_break_before = True
            add_inline_runs(
                paragraph,
                block.text,
                color={1: NAVY, 2: BLUE, 3: DARK_BLUE}[block.level],
                size={1: 18, 2: 14, 3: 12}[block.level],
            )
            for run in paragraph.runs:
                run.bold = True
            continue
        if block.kind == "paragraph":
            paragraph = doc.add_paragraph()
            add_inline_runs(paragraph, block.text)
            continue
        if block.kind in {"bullet", "number"}:
            if active_list_kind != block.kind or active_num_id is None:
                active_list_kind = block.kind
                active_num_id = create_list_numbering(
                    doc,
                    ordered=block.kind == "number",
                )
            style = "List Bullet" if block.kind == "bullet" else "List Number"
            paragraph = doc.add_paragraph(style=style)
            apply_list_numbering(paragraph, active_num_id)
            next_is_same_list = index + 1 < len(blocks) and blocks[index + 1].kind == block.kind
            paragraph.paragraph_format.keep_with_next = next_is_same_list
            add_inline_runs(paragraph, block.text)
            continue
        if block.kind == "callout":
            add_callout(doc, block.text)
            continue
        if block.kind == "table":
            add_markdown_table(doc, block.rows)
            continue
        if block.kind == "code":
            add_code_block(doc, block.text, block.language)
            continue
        if block.kind == "image":
            if asset_base is None:
                raise ValueError(f"image block has no asset base: {block.language}")
            image_path = (asset_base / block.language).resolve()
            if not image_path.is_file():
                raise FileNotFoundError(f"manual image not found: {image_path}")
            picture = doc.add_paragraph()
            picture.alignment = WD_ALIGN_PARAGRAPH.CENTER
            picture.paragraph_format.keep_with_next = bool(block.text)
            picture.add_run().add_picture(str(image_path), width=Cm(15.4))
            if block.text:
                caption = doc.add_paragraph()
                caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                caption.paragraph_format.keep_together = True
                caption.paragraph_format.space_after = Pt(7)
                run = caption.add_run(block.text)
                set_run_font(run, size=8.5, color=MUTED, bold=True)
            continue
        raise ValueError(f"unsupported block type: {block.kind}")


def set_document_properties(doc: Document) -> None:
    properties = doc.core_properties
    properties.title = MANUAL_TITLE
    properties.subject = "SS-Screen未来完整功能的中文科研用户手册"
    properties.author = AUTHOR
    properties.last_modified_by = AUTHOR
    properties.keywords = "SS-Screen, 固溶体, 带隙, 材料筛选, SQS, 用户手册"
    properties.comments = "Generated deterministically from the repository Markdown source."


def build_document(source: str, output: Path) -> None:
    blocks = parse_markdown(source)
    doc = Document()
    configure_section(doc)
    configure_styles(doc)
    set_document_properties(doc)
    add_header_footer(doc)
    add_cover(doc)
    add_static_toc(doc, blocks)
    add_body(doc, blocks, asset_base=output.parent)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)


def count_blocks(blocks: Iterable[Block], kind: str) -> int:
    return sum(1 for block in blocks if block.kind == kind)


def check_docx(source: str, output: Path) -> dict[str, int]:
    if not output.exists() or output.stat().st_size < 10_000:
        raise ValueError(f"DOCX missing or unexpectedly small: {output}")
    doc = Document(output)
    visible_text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    for heading in REQUIRED_HEADINGS:
        if heading not in visible_text:
            raise ValueError(f"DOCX missing heading text: {heading}")
    if AUTHOR != doc.core_properties.author:
        raise ValueError("DOCX author metadata is not scrubbed to project identity")
    blocks = parse_markdown(source)
    stats = {
        "headings": count_blocks(blocks, "heading"),
        "tables": count_blocks(blocks, "table"),
        "code_blocks": count_blocks(blocks, "code"),
        "callouts": count_blocks(blocks, "callout"),
        "docx_paragraphs": len(doc.paragraphs),
        "docx_tables": len(doc.tables),
        "current_labels": source.count("[当前可用]"),
        "future_labels": source.count("完整版本预期接口"),
    }
    if stats["headings"] < 60:
        raise ValueError("unexpectedly few headings")
    if stats["tables"] < 15:
        raise ValueError("unexpectedly few Markdown tables")
    if stats["code_blocks"] < 30:
        raise ValueError("unexpectedly few command/code blocks")
    return stats


def format_stats(stats: dict[str, int]) -> str:
    return "\n".join(f"{key}: {value}" for key, value in stats.items())


def main() -> int:
    args = parse_args()
    source = args.input.read_text(encoding="utf-8")
    validate_source(source)
    build_document(source, args.output)
    stats = check_docx(source, args.output)
    print(f"built: {args.output}")
    print(f"size_bytes: {args.output.stat().st_size}")
    if args.check:
        print(format_stats(stats))
        print("manual structural checks: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure boundary
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
