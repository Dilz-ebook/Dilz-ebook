"""
Compile all ebook/*.md files into a single styled PDF.

Output: dist/ebook-pinokioarab-250-hook.pdf

Theme:
- Background: deep black (#0A0A0A)
- Headings: gold (#C9A961)
- Body: white (#F5F5F5)
- Accents: muted gold (#8C7848)

Markdown features supported:
- # / ## / ### headings
- Numbered lists "1. ..."
- Bulleted lists "- ..." or "* ..."
- Blockquotes "> ..."
- Horizontal rule "---"
- Tables "| col | col |"
- Inline **bold**, *italic*, `code`, [text](url)
- Fenced code blocks ```
"""

import os
import re
import html
from pathlib import Path

from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)

# ============================================================
# THEME
# ============================================================
BG_COLOR = HexColor("#0A0A0A")
GOLD = HexColor("#C9A961")
GOLD_DIM = HexColor("#8C7848")
TEXT = HexColor("#F0EDE6")
TEXT_DIM = HexColor("#9A958A")
DIVIDER = HexColor("#3A332A")

PAGE_W, PAGE_H = A4
MARGIN_X = 18 * mm
MARGIN_TOP = 22 * mm
MARGIN_BOTTOM = 22 * mm

# ============================================================
# STYLES
# ============================================================

STYLES = {
    "cover_title": ParagraphStyle(
        "cover_title",
        fontName="Helvetica-Bold",
        fontSize=46,
        leading=52,
        textColor=GOLD,
        alignment=TA_CENTER,
        spaceBefore=0,
        spaceAfter=14,
    ),
    "cover_sub": ParagraphStyle(
        "cover_sub",
        fontName="Helvetica",
        fontSize=14,
        leading=20,
        textColor=TEXT,
        alignment=TA_CENTER,
        spaceAfter=10,
    ),
    "cover_caption": ParagraphStyle(
        "cover_caption",
        fontName="Helvetica-Oblique",
        fontSize=11,
        leading=16,
        textColor=GOLD,
        alignment=TA_CENTER,
        spaceAfter=6,
    ),
    "h1": ParagraphStyle(
        "h1",
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=30,
        textColor=GOLD,
        spaceBefore=8,
        spaceAfter=14,
        alignment=TA_LEFT,
    ),
    "h2": ParagraphStyle(
        "h2",
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=22,
        textColor=GOLD,
        spaceBefore=14,
        spaceAfter=8,
    ),
    "h3": ParagraphStyle(
        "h3",
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=18,
        textColor=GOLD_DIM,
        spaceBefore=10,
        spaceAfter=4,
    ),
    "body": ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=10.5,
        leading=16,
        textColor=TEXT,
        spaceAfter=6,
        alignment=TA_LEFT,
    ),
    "list_item": ParagraphStyle(
        "list_item",
        fontName="Helvetica",
        fontSize=10.5,
        leading=16,
        textColor=TEXT,
        spaceAfter=4,
        leftIndent=14,
        bulletIndent=2,
    ),
    "numbered": ParagraphStyle(
        "numbered",
        fontName="Helvetica",
        fontSize=10.5,
        leading=16,
        textColor=TEXT,
        spaceAfter=8,
        leftIndent=18,
    ),
    "quote": ParagraphStyle(
        "quote",
        fontName="Helvetica-Oblique",
        fontSize=10.5,
        leading=16,
        textColor=GOLD,
        leftIndent=14,
        rightIndent=10,
        spaceBefore=6,
        spaceAfter=8,
        borderColor=GOLD_DIM,
        borderWidth=0,
    ),
    "code": ParagraphStyle(
        "code",
        fontName="Courier",
        fontSize=9,
        leading=12,
        textColor=TEXT,
        leftIndent=8,
        rightIndent=8,
        spaceBefore=4,
        spaceAfter=8,
        backColor=HexColor("#161310"),
    ),
    "footer": ParagraphStyle(
        "footer",
        fontName="Helvetica",
        fontSize=8,
        textColor=TEXT_DIM,
        alignment=TA_CENTER,
    ),
}


# ============================================================
# INLINE MARKDOWN -> REPORTLAB TAG CONVERSION
# ============================================================

def inline_md_to_rl(text: str) -> str:
    """Convert inline markdown (**bold**, *italic*, `code`, [link](url)) to ReportLab paragraph tags."""
    # Escape HTML entities first (so user text is safe)
    text = html.escape(text, quote=False)

    # Re-allow the few entities we may have introduced
    # Links: [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<link href="{m.group(2)}" color="#C9A961">{m.group(1)}</link>',
        text,
    )

    # Bold: **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    # Italic: *text* (avoid matching ** which we already replaced)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)

    # Inline code: `text`
    text = re.sub(
        r"`([^`]+)`",
        lambda m: f'<font name="Courier" color="#C9A961">{m.group(1)}</font>',
        text,
    )

    return text


def para(text: str, style_name: str = "body") -> Paragraph:
    return Paragraph(inline_md_to_rl(text), STYLES[style_name])


# ============================================================
# MARKDOWN BLOCK PARSER
# ============================================================

def parse_markdown(md_text: str):
    """Parse markdown text into a list of ReportLab flowables."""
    flowables = []
    lines = md_text.split("\n")
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Blank line
        if not stripped:
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^-{3,}$|^\*{3,}$|^_{3,}$", stripped):
            flowables.append(Spacer(1, 4))
            flowables.append(HRFlowable(
                width="100%",
                thickness=0.6,
                color=DIVIDER,
                spaceBefore=4,
                spaceAfter=8,
            ))
            i += 1
            continue

        # Fenced code block
        if stripped.startswith("```"):
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            # Render as a styled paragraph (preserve newlines via <br/>)
            code_text = "\n".join(code_lines)
            code_text_html = html.escape(code_text).replace("\n", "<br/>").replace(" ", "&nbsp;")
            flowables.append(Paragraph(code_text_html, STYLES["code"]))
            flowables.append(Spacer(1, 6))
            continue

        # Headings
        if stripped.startswith("# "):
            flowables.append(Spacer(1, 6))
            flowables.append(para(stripped[2:].strip(), "h1"))
            flowables.append(HRFlowable(
                width="40%",
                thickness=1,
                color=GOLD,
                spaceBefore=0,
                spaceAfter=10,
                hAlign="LEFT",
            ))
            i += 1
            continue

        if stripped.startswith("## "):
            flowables.append(para(stripped[3:].strip(), "h2"))
            i += 1
            continue

        if stripped.startswith("### "):
            flowables.append(para(stripped[4:].strip(), "h3"))
            i += 1
            continue

        # Blockquote — possibly multi-line
        if stripped.startswith(">"):
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip()[1:].strip())
                i += 1
            quote_text = " ".join(filter(None, quote_lines))
            if quote_text:
                flowables.append(para(quote_text, "quote"))
            continue

        # Table — collect consecutive | rows
        if stripped.startswith("|") and stripped.endswith("|"):
            table_rows = []
            while i < n and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                table_rows.append(row)
                i += 1

            # Drop separator row(s) — those that are only dashes/colons
            cleaned = []
            for row in table_rows:
                is_separator = all(re.match(r"^:?-+:?$", c.replace(" ", "")) for c in row if c)
                if not is_separator:
                    cleaned.append(row)

            if cleaned:
                # Convert each cell to Paragraph for inline markdown support
                cell_style = ParagraphStyle(
                    "cell",
                    parent=STYLES["body"],
                    fontSize=9.5,
                    leading=13,
                    textColor=TEXT,
                )
                header_style = ParagraphStyle(
                    "cell_h",
                    parent=cell_style,
                    fontName="Helvetica-Bold",
                    textColor=GOLD,
                )

                data = []
                for r_idx, row in enumerate(cleaned):
                    style = header_style if r_idx == 0 else cell_style
                    data.append([Paragraph(inline_md_to_rl(c), style) for c in row])

                # Calculate column widths evenly
                col_count = len(data[0])
                avail_w = PAGE_W - 2 * MARGIN_X
                col_w = avail_w / col_count

                tbl = Table(data, colWidths=[col_w] * col_count, repeatRows=1)
                tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1a1612")),
                    ("BACKGROUND", (0, 1), (-1, -1), HexColor("#0F0D0A")),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.8, GOLD_DIM),
                    ("GRID", (0, 0), (-1, -1), 0.3, DIVIDER),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]))
                flowables.append(Spacer(1, 4))
                flowables.append(tbl)
                flowables.append(Spacer(1, 8))
            continue

        # Numbered list item
        m_num = re.match(r"^(\d+)\.\s+(.*)", stripped)
        if m_num:
            num, content = m_num.group(1), m_num.group(2)
            # Continuation lines (indented or non-empty without new marker)
            i += 1
            while i < n:
                nxt = lines[i]
                ns = nxt.strip()
                if not ns:
                    break
                if re.match(r"^(\d+)\.\s+", ns) or ns.startswith(("#", "-", "*", ">", "|", "```")):
                    break
                content += " " + ns
                i += 1
            # Build with hanging indent: gold number, then text
            text_html = (
                f'<font color="#C9A961"><b>{num}.</b></font>&nbsp;&nbsp;'
                f'{inline_md_to_rl(content)}'
            )
            flowables.append(Paragraph(text_html, STYLES["numbered"]))
            continue

        # Bulleted list item
        if stripped.startswith(("- ", "* ", "+ ")):
            content = stripped[2:].strip()
            i += 1
            while i < n:
                nxt = lines[i]
                ns = nxt.strip()
                if not ns:
                    break
                if ns.startswith(("- ", "* ", "+ ", "#", ">", "|", "```")) or re.match(r"^\d+\.\s+", ns):
                    break
                content += " " + ns
                i += 1
            text_html = f'<font color="#C9A961">•</font>&nbsp;&nbsp;{inline_md_to_rl(content)}'
            flowables.append(Paragraph(text_html, STYLES["list_item"]))
            continue

        # Regular paragraph — collect until blank line / new block
        para_lines = [stripped]
        i += 1
        while i < n:
            nxt = lines[i]
            ns = nxt.strip()
            if not ns:
                break
            if (
                ns.startswith(("#", ">", "|", "```", "- ", "* ", "+ "))
                or re.match(r"^\d+\.\s+", ns)
                or re.match(r"^-{3,}$|^\*{3,}$", ns)
            ):
                break
            para_lines.append(ns)
            i += 1
        text = " ".join(para_lines)
        flowables.append(para(text, "body"))

    return flowables


# ============================================================
# PAGE BACKGROUND + FOOTER
# ============================================================

def draw_page_background(canvas, doc):
    canvas.saveState()
    # Fill entire page with bg color
    canvas.setFillColor(BG_COLOR)
    canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    page_num = canvas.getPageNumber()

    if page_num > 1:
        # Header line
        canvas.setStrokeColor(DIVIDER)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN_X, PAGE_H - 14 * mm, PAGE_W - MARGIN_X, PAGE_H - 14 * mm)

        # Header text — left: brand, right: book title
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(TEXT_DIM)
        canvas.drawString(MARGIN_X, PAGE_H - 11 * mm, "@pinokioarab")
        canvas.drawRightString(
            PAGE_W - MARGIN_X,
            PAGE_H - 11 * mm,
            "250+ Template Hook Utas Threads",
        )

        # Footer page number
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GOLD_DIM)
        canvas.drawCentredString(PAGE_W / 2, 12 * mm, f"— {page_num} —")

    canvas.restoreState()


def draw_cover_background(canvas, doc):
    """Special cover page background with extra accents."""
    canvas.saveState()
    canvas.setFillColor(BG_COLOR)
    canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    # Gold border frame
    canvas.setStrokeColor(GOLD_DIM)
    canvas.setLineWidth(0.6)
    canvas.rect(
        14 * mm,
        14 * mm,
        PAGE_W - 28 * mm,
        PAGE_H - 28 * mm,
        stroke=1,
        fill=0,
    )

    # Inner accent line
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.3)
    canvas.rect(
        16 * mm,
        16 * mm,
        PAGE_W - 32 * mm,
        PAGE_H - 32 * mm,
        stroke=1,
        fill=0,
    )

    canvas.restoreState()


# ============================================================
# COVER PAGE BUILDER
# ============================================================

def build_cover_flowables():
    flowables = []
    flowables.append(Spacer(1, 38 * mm))

    # Top label
    label = ParagraphStyle(
        "label",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=GOLD_DIM,
        alignment=TA_CENTER,
    )
    flowables.append(Paragraph("E B O O K &nbsp;&nbsp; T E M P L A T E", label))
    flowables.append(Spacer(1, 14 * mm))

    # Title
    big = ParagraphStyle(
        "big",
        fontName="Helvetica-Bold",
        fontSize=72,
        leading=72,
        textColor=GOLD,
        alignment=TA_CENTER,
    )
    flowables.append(Paragraph("250+", big))
    flowables.append(Spacer(1, 4))

    sub_big = ParagraphStyle(
        "sub_big",
        fontName="Helvetica-Bold",
        fontSize=32,
        leading=38,
        textColor=TEXT,
        alignment=TA_CENTER,
    )
    flowables.append(Paragraph("TEMPLATE HOOK", sub_big))
    flowables.append(Paragraph("UTAS THREADS", sub_big))
    flowables.append(Spacer(1, 8))

    siap = ParagraphStyle(
        "siap",
        fontName="Helvetica-Oblique",
        fontSize=14,
        textColor=GOLD,
        alignment=TA_CENTER,
    )
    flowables.append(Paragraph("S I A P &nbsp; P A K A I", siap))
    flowables.append(Spacer(1, 22 * mm))

    # Bonus badge
    badge = ParagraphStyle(
        "badge",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=16,
        textColor=GOLD,
        alignment=TA_CENTER,
    )
    flowables.append(HRFlowable(width="40%", thickness=0.4, color=GOLD_DIM,
                                hAlign="CENTER", spaceBefore=0, spaceAfter=8))
    flowables.append(Paragraph("BONUS 55+ HOOK RANDOM", badge))
    flowables.append(Paragraph(
        '<font color="#9A958A">untuk inspirasi tambahan setiap hari</font>',
        STYLES["cover_sub"],
    ))
    flowables.append(HRFlowable(width="40%", thickness=0.4, color=GOLD_DIM,
                                hAlign="CENTER", spaceBefore=8, spaceAfter=18))

    flowables.append(Spacer(1, 12 * mm))

    by = ParagraphStyle(
        "by",
        fontName="Helvetica-Oblique",
        fontSize=12,
        textColor=TEXT,
        alignment=TA_CENTER,
    )
    flowables.append(Paragraph("by <b>@pinokioarab</b>", by))
    flowables.append(PageBreak())

    return flowables


# ============================================================
# MAIN BUILD
# ============================================================

def build_pdf():
    base_dir = Path(__file__).parent
    ebook_dir = base_dir / "ebook"
    out_dir = base_dir / "dist"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "ebook-pinokioarab-250-hook.pdf"

    md_files = sorted(
        f for f in ebook_dir.glob("*.md")
        if f.name != "00-cover.md"  # cover handled separately
    )

    # Build document with two page templates: cover (no header/footer) + content
    doc = BaseDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title="250+ Template Hook Utas Threads",
        author="@pinokioarab",
        subject="Template hook utas Threads siap pakai",
        creator="@pinokioarab",
    )

    cover_frame = Frame(
        0, 0, PAGE_W, PAGE_H,
        leftPadding=MARGIN_X, rightPadding=MARGIN_X,
        topPadding=MARGIN_TOP, bottomPadding=MARGIN_BOTTOM,
        id="cover",
    )
    content_frame = Frame(
        MARGIN_X,
        MARGIN_BOTTOM,
        PAGE_W - 2 * MARGIN_X,
        PAGE_H - MARGIN_TOP - MARGIN_BOTTOM,
        leftPadding=0, rightPadding=0,
        topPadding=0, bottomPadding=0,
        id="content",
    )

    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=[cover_frame], onPage=draw_cover_background),
        PageTemplate(id="Content", frames=[content_frame], onPage=draw_page_background),
    ])

    story = []

    # Cover
    story.extend(build_cover_flowables())

    # Switch to content template
    from reportlab.platypus.doctemplate import NextPageTemplate
    story.append(NextPageTemplate("Content"))

    # Each markdown chapter -> new page
    for idx, md_path in enumerate(md_files):
        md_text = md_path.read_text(encoding="utf-8")
        flowables = parse_markdown(md_text)
        story.extend(flowables)
        if idx < len(md_files) - 1:
            story.append(PageBreak())

    doc.build(story)

    size_kb = out_path.stat().st_size / 1024
    print(f"OK: {out_path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    build_pdf()
