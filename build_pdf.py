"""
Compile all ebook/*.md files into a single styled PDF.

Output: dist/ebook-pinokioarab-250-hook.pdf

Theme:
- Background: deep black (#0A0A0A)
- Headings: gold (#C9A961), Playfair Display (serif)
- Body: light cream (#F0EDE6), Inter (sans-serif)
- Code: JetBrains Mono
- Accents: muted gold (#8C7848)

Markdown features supported:
- # / ## / ### headings
- Numbered lists "1. ..."
- Bulleted lists "- ..." / "* ..."
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

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.platypus.doctemplate import NextPageTemplate

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

BASE_DIR = Path(__file__).parent
FONT_DIR = BASE_DIR / "fonts"

# ============================================================
# FONT REGISTRATION
# ============================================================

def register_fonts():
    """Register premium fonts. Falls back to Helvetica if files missing.

    Note: Inter variable fonts caused rendering issues, so we use Helvetica
    (built-in Type 1) for body text. Headings use Playfair Display for the
    "premium" serif look.
    """
    fonts = {
        # Body uses Helvetica (built-in) — skip Inter to avoid variable-font issues
        "DisplayFont":    FONT_DIR / "PlayfairDisplay-Bold.ttf",
        "DisplayItalic":  FONT_DIR / "PlayfairDisplay-Italic.ttf",
        "MonoFont":       FONT_DIR / "JetBrainsMono-Regular.ttf",
    }
    registered = {}
    for name, path in fonts.items():
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont(name, str(path)))
                registered[name] = True
            except Exception as e:
                print(f"WARN failed to register {name}: {e}")
                registered[name] = False
        else:
            print(f"WARN font missing: {path}")
            registered[name] = False

    # Map family for bold/italic resolution
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    if registered.get("BodyFont"):
        registerFontFamily(
            "BodyFont",
            normal="BodyFont",
            bold="BodyFont-Bold" if registered.get("BodyFont-Bold") else "BodyFont",
            italic="BodyFont-Italic" if registered.get("BodyFont-Italic") else "BodyFont",
            boldItalic="BodyFont-Italic" if registered.get("BodyFont-Italic") else "BodyFont",
        )
    if registered.get("DisplayFont"):
        registerFontFamily(
            "DisplayFont",
            normal="DisplayFont",
            bold="DisplayFont",
            italic="DisplayItalic" if registered.get("DisplayItalic") else "DisplayFont",
            boldItalic="DisplayItalic" if registered.get("DisplayItalic") else "DisplayFont",
        )
    return registered


FONT_OK = register_fonts()

# Resolve actual font names with fallback
F_BODY    = "BodyFont"        if FONT_OK.get("BodyFont")        else "Helvetica"
F_BOLD    = "BodyFont-Bold"   if FONT_OK.get("BodyFont-Bold")   else "Helvetica-Bold"
F_ITALIC  = "BodyFont-Italic" if FONT_OK.get("BodyFont-Italic") else "Helvetica-Oblique"
F_DISPLAY = "DisplayFont"     if FONT_OK.get("DisplayFont")     else "Helvetica-Bold"
F_DISP_I  = "DisplayItalic"   if FONT_OK.get("DisplayItalic")   else "Helvetica-Oblique"
F_MONO    = "MonoFont"        if FONT_OK.get("MonoFont")        else "Courier"

# ============================================================
# STYLES
# ============================================================

STYLES = {
    "h1": ParagraphStyle(
        "h1",
        fontName=F_DISPLAY,
        fontSize=28,
        leading=34,
        textColor=GOLD,
        spaceBefore=4,
        spaceAfter=12,
        alignment=TA_LEFT,
    ),
    "h2": ParagraphStyle(
        "h2",
        fontName=F_DISPLAY,
        fontSize=17,
        leading=24,
        textColor=GOLD,
        spaceBefore=14,
        spaceAfter=8,
    ),
    "h3": ParagraphStyle(
        "h3",
        fontName=F_BOLD,
        fontSize=11.5,
        leading=17,
        textColor=GOLD_DIM,
        spaceBefore=10,
        spaceAfter=4,
    ),
    "body": ParagraphStyle(
        "body",
        fontName=F_BODY,
        fontSize=10.5,
        leading=16,
        textColor=TEXT,
        spaceAfter=6,
        alignment=TA_LEFT,
    ),
    "list_item": ParagraphStyle(
        "list_item",
        fontName=F_BODY,
        fontSize=10.5,
        leading=16,
        textColor=TEXT,
        spaceAfter=4,
        leftIndent=14,
        bulletIndent=2,
    ),
    "numbered": ParagraphStyle(
        "numbered",
        fontName=F_BODY,
        fontSize=10.5,
        leading=16,
        textColor=TEXT,
        spaceAfter=8,
        leftIndent=20,
    ),
    "quote": ParagraphStyle(
        "quote",
        fontName=F_DISP_I,
        fontSize=11,
        leading=17,
        textColor=GOLD,
        leftIndent=16,
        rightIndent=10,
        spaceBefore=6,
        spaceAfter=10,
    ),
    "code": ParagraphStyle(
        "code",
        fontName=F_MONO,
        fontSize=8.5,
        leading=12,
        textColor=TEXT,
        leftIndent=10,
        rightIndent=10,
        spaceBefore=4,
        spaceAfter=8,
        backColor=HexColor("#161310"),
        borderColor=DIVIDER,
        borderWidth=0.4,
        borderPadding=6,
    ),
}


# ============================================================
# INLINE MARKDOWN -> REPORTLAB TAG CONVERSION
# ============================================================

def inline_md_to_rl(text: str) -> str:
    """Convert inline markdown to ReportLab paragraph tags."""
    text = html.escape(text, quote=False)

    # Links: [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<link href="{m.group(2)}" color="#C9A961">{m.group(1)}</link>',
        text,
    )

    # Bold: **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    # Italic: *text*
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)

    # Inline code: `text`
    text = re.sub(
        r"`([^`]+)`",
        lambda m: f'<font name="{F_MONO}" color="#C9A961">{m.group(1)}</font>',
        text,
    )

    return text


def para(text: str, style_name: str = "body") -> Paragraph:
    return Paragraph(inline_md_to_rl(text), STYLES[style_name])


# ============================================================
# MARKDOWN BLOCK PARSER
# ============================================================

def parse_markdown(md_text: str):
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
                thickness=0.5,
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
            i += 1
            code_text = "\n".join(code_lines)
            code_html = (
                html.escape(code_text)
                .replace("\n", "<br/>")
                .replace(" ", "&nbsp;")
            )
            flowables.append(Paragraph(code_html, STYLES["code"]))
            flowables.append(Spacer(1, 6))
            continue

        # H1
        if stripped.startswith("# "):
            flowables.append(Spacer(1, 4))
            flowables.append(para(stripped[2:].strip(), "h1"))
            flowables.append(HRFlowable(
                width="35%",
                thickness=1,
                color=GOLD,
                spaceBefore=0,
                spaceAfter=12,
                hAlign="LEFT",
            ))
            i += 1
            continue

        # H2
        if stripped.startswith("## "):
            flowables.append(para(stripped[3:].strip(), "h2"))
            i += 1
            continue

        # H3
        if stripped.startswith("### "):
            flowables.append(para(stripped[4:].strip(), "h3"))
            i += 1
            continue

        # Blockquote
        if stripped.startswith(">"):
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip()[1:].strip())
                i += 1
            quote_text = " ".join(filter(None, quote_lines))
            if quote_text:
                flowables.append(para(quote_text, "quote"))
            continue

        # Table
        if stripped.startswith("|") and stripped.endswith("|"):
            table_rows = []
            while i < n and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                table_rows.append(row)
                i += 1

            cleaned = []
            for row in table_rows:
                is_separator = all(
                    re.match(r"^:?-+:?$", c.replace(" ", "")) for c in row if c
                )
                if not is_separator:
                    cleaned.append(row)

            if cleaned:
                cell_style = ParagraphStyle(
                    "cell",
                    parent=STYLES["body"],
                    fontSize=9.2,
                    leading=13,
                    textColor=TEXT,
                )
                header_style = ParagraphStyle(
                    "cell_h",
                    parent=cell_style,
                    fontName=F_BOLD,
                    textColor=GOLD,
                )

                data = []
                for r_idx, row in enumerate(cleaned):
                    style = header_style if r_idx == 0 else cell_style
                    data.append([Paragraph(inline_md_to_rl(c), style) for c in row])

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

        # Numbered list
        m_num = re.match(r"^(\d+)\.\s+(.*)", stripped)
        if m_num:
            num, content = m_num.group(1), m_num.group(2)
            i += 1
            while i < n:
                ns = lines[i].strip()
                if not ns:
                    break
                if re.match(r"^(\d+)\.\s+", ns) or ns.startswith(("#", "-", "*", ">", "|", "```")):
                    break
                content += " " + ns
                i += 1
            text_html = (
                f'<font color="#C9A961" name="{F_DISPLAY}"><b>{num}.</b></font>&nbsp;&nbsp;'
                f'{inline_md_to_rl(content)}'
            )
            flowables.append(Paragraph(text_html, STYLES["numbered"]))
            continue

        # Bulleted list
        if stripped.startswith(("- ", "* ", "+ ")):
            content = stripped[2:].strip()
            i += 1
            while i < n:
                ns = lines[i].strip()
                if not ns:
                    break
                if ns.startswith(("- ", "* ", "+ ", "#", ">", "|", "```")) or re.match(r"^\d+\.\s+", ns):
                    break
                content += " " + ns
                i += 1
            text_html = f'<font color="#C9A961">&#9670;</font>&nbsp;&nbsp;{inline_md_to_rl(content)}'
            flowables.append(Paragraph(text_html, STYLES["list_item"]))
            continue

        # Paragraph
        para_lines = [stripped]
        i += 1
        while i < n:
            ns = lines[i].strip()
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
# PAGE BACKGROUND + HEADER + FOOTER
# ============================================================

def draw_page_background(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BG_COLOR)
    canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    page_num = canvas.getPageNumber()

    if page_num > 1:
        # Header decorative line
        canvas.setStrokeColor(DIVIDER)
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN_X, PAGE_H - 13 * mm, PAGE_W - MARGIN_X, PAGE_H - 13 * mm)

        # Tiny gold dot accent on header
        canvas.setFillColor(GOLD)
        canvas.circle(PAGE_W / 2, PAGE_H - 13 * mm, 0.8, stroke=0, fill=1)

        # Header text
        canvas.setFont(F_DISP_I if F_DISP_I in pdfmetrics.getRegisteredFontNames() else "Helvetica-Oblique", 8)
        canvas.setFillColor(TEXT_DIM)
        canvas.drawString(MARGIN_X, PAGE_H - 10 * mm, "@pinokioarab")
        canvas.drawRightString(
            PAGE_W - MARGIN_X,
            PAGE_H - 10 * mm,
            "250+ Template Hook Utas Threads",
        )

        # Footer page number
        canvas.setFont(F_DISPLAY if F_DISPLAY in pdfmetrics.getRegisteredFontNames() else "Helvetica", 8)
        canvas.setFillColor(GOLD_DIM)
        canvas.drawCentredString(PAGE_W / 2, 12 * mm, f"{page_num:02d}")

        # Footer thin line
        canvas.setStrokeColor(DIVIDER)
        canvas.setLineWidth(0.3)
        canvas.line(PAGE_W / 2 - 10 * mm, 14 * mm, PAGE_W / 2 - 4 * mm, 14 * mm)
        canvas.line(PAGE_W / 2 + 4 * mm, 14 * mm, PAGE_W / 2 + 10 * mm, 14 * mm)

    canvas.restoreState()


def draw_cover_background(canvas, doc):
    canvas.saveState()

    # Solid black
    canvas.setFillColor(BG_COLOR)
    canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    # Outer frame
    canvas.setStrokeColor(GOLD_DIM)
    canvas.setLineWidth(0.5)
    canvas.rect(
        12 * mm, 12 * mm,
        PAGE_W - 24 * mm, PAGE_H - 24 * mm,
        stroke=1, fill=0,
    )

    # Inner accent
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.3)
    canvas.rect(
        15 * mm, 15 * mm,
        PAGE_W - 30 * mm, PAGE_H - 30 * mm,
        stroke=1, fill=0,
    )

    # Top corner ornaments
    for x_off, y_off in [(15, PAGE_H/mm - 15), (PAGE_W/mm - 15, PAGE_H/mm - 15),
                         (15, 15), (PAGE_W/mm - 15, 15)]:
        canvas.setFillColor(GOLD)
        canvas.circle(x_off * mm, y_off * mm, 1.2, stroke=0, fill=1)

    canvas.restoreState()


# ============================================================
# COVER PAGE BUILDER
# ============================================================

def build_cover_flowables():
    flowables = []
    flowables.append(Spacer(1, 32 * mm))

    # Top label with letter-spacing effect
    label = ParagraphStyle(
        "label",
        fontName=F_BOLD,
        fontSize=10,
        leading=14,
        textColor=GOLD_DIM,
        alignment=TA_CENTER,
    )
    flowables.append(Paragraph("E B O O K &nbsp; &middot; &nbsp; T E M P L A T E", label))
    flowables.append(Spacer(1, 6 * mm))

    # Decorative divider
    flowables.append(HRFlowable(
        width="20%", thickness=0.6, color=GOLD,
        hAlign="CENTER", spaceBefore=0, spaceAfter=14,
    ))

    # 250+ huge number — Playfair Display
    big = ParagraphStyle(
        "big",
        fontName=F_DISPLAY,
        fontSize=96,
        leading=96,
        textColor=GOLD,
        alignment=TA_CENTER,
    )
    flowables.append(Paragraph("250+", big))
    flowables.append(Spacer(1, 4))

    # Subtitle — Playfair Display
    sub_big = ParagraphStyle(
        "sub_big",
        fontName=F_DISPLAY,
        fontSize=30,
        leading=38,
        textColor=TEXT,
        alignment=TA_CENTER,
    )
    flowables.append(Paragraph("TEMPLATE HOOK", sub_big))
    flowables.append(Paragraph("UTAS THREADS", sub_big))
    flowables.append(Spacer(1, 10))

    # "Siap Pakai" italic
    siap = ParagraphStyle(
        "siap",
        fontName=F_DISP_I,
        fontSize=15,
        textColor=GOLD,
        alignment=TA_CENTER,
    )
    flowables.append(Paragraph("Siap Pakai", siap))
    flowables.append(Spacer(1, 24 * mm))

    # Bonus badge with frame
    flowables.append(HRFlowable(
        width="30%", thickness=0.4, color=GOLD_DIM,
        hAlign="CENTER", spaceBefore=0, spaceAfter=10,
    ))

    badge = ParagraphStyle(
        "badge",
        fontName=F_BOLD,
        fontSize=11,
        leading=16,
        textColor=GOLD,
        alignment=TA_CENTER,
    )
    flowables.append(Paragraph("BONUS &nbsp; 55+ &nbsp; HOOK &nbsp; RANDOM", badge))

    sub_caption = ParagraphStyle(
        "sub_caption",
        fontName=F_BODY,
        fontSize=9.5,
        leading=14,
        textColor=TEXT_DIM,
        alignment=TA_CENTER,
    )
    flowables.append(Spacer(1, 4))
    flowables.append(Paragraph("untuk inspirasi tambahan setiap hari", sub_caption))

    flowables.append(HRFlowable(
        width="30%", thickness=0.4, color=GOLD_DIM,
        hAlign="CENTER", spaceBefore=10, spaceAfter=18,
    ))

    flowables.append(Spacer(1, 16 * mm))

    # by @pinokioarab — italic Playfair
    by = ParagraphStyle(
        "by",
        fontName=F_DISP_I,
        fontSize=14,
        textColor=TEXT,
        alignment=TA_CENTER,
    )
    flowables.append(Paragraph(f'by <font color="#C9A961">@pinokioarab</font>', by))
    flowables.append(PageBreak())

    return flowables


# ============================================================
# MAIN BUILD
# ============================================================

def build_pdf():
    ebook_dir = BASE_DIR / "ebook"
    out_dir = BASE_DIR / "dist"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "ebook-pinokioarab-250-hook.pdf"

    md_files = sorted(
        f for f in ebook_dir.glob("*.md")
        if f.name != "00-cover.md"
    )

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
    story.extend(build_cover_flowables())
    story.append(NextPageTemplate("Content"))

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
