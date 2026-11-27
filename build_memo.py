"""Render the checked-in credit memo to a two-page PDF."""
import re
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Table, TableStyle

ROOT = Path(__file__).resolve().parent
NAVY = colors.HexColor("#172F44")
TEAL = colors.HexColor("#22615A")
INK = colors.HexColor("#263746")
PALE = colors.HexColor("#ECF3F7")


def style(name, size, leading, *, bold=False, color=INK, align=TA_LEFT, before=0, after=0):
    return ParagraphStyle(name, fontName="Helvetica-Bold" if bold else "Helvetica",
                          fontSize=size, leading=leading, textColor=color, alignment=align,
                          spaceBefore=before, spaceAfter=after)


TITLE = style("title", 25, 30, bold=True, color=NAVY, after=8)
DECK = style("deck", 10, 15, bold=True, color=TEAL, after=20)
HEAD = style("heading", 13, 17, bold=True, color=NAVY, before=12, after=6)
BODY = style("paragraph", 10.1, 14.5, after=10)
REF = style("reference", 8.8, 13, after=5)
TABLE_HEAD = style("table head", 8.5, 11, bold=True, color=colors.white)
TABLE_NUM = style("table number", 9.2, 13, align=TA_RIGHT)


def markup(value):
    return re.sub(r"\[([^\]]+)\]\((https://[^)]+)\)",
                  r'<link href="\2" color="#22615A">\1</link>', escape(value))


def case_table(lines):
    rows = [[cell.strip() for cell in row.strip("|").split("|")] for row in lines]
    values = [[Paragraph(escape(x), TABLE_HEAD) for x in rows[0]]]
    values.extend([[Paragraph(escape(row[0]), BODY),
                    *(Paragraph(escape(x), TABLE_NUM) for x in row[1:])] for row in rows[2:]])
    table = Table(values, colWidths=[88, 71, 85, 72, 88, 94], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PALE, colors.white]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, -1), (-1, -1), .5, colors.HexColor("#BBCBD6")),
    ]))
    return table


def footer(pdf, doc):
    pdf.saveState()
    pdf.setTitle("DATA 2023-CNTR Credit Memo")
    pdf.setAuthor("Dominic Bavuso")
    pdf.setStrokeColor(colors.HexColor("#BBCBD6"))
    pdf.line(57, 47, 555, 47)
    pdf.setFont("Helvetica", 8.5)
    pdf.setFillColor(TEAL)
    pdf.drawString(57, 31, "DATA 2023-CNTR  /  CREDIT RESEARCH")
    pdf.drawRightString(555, 31, f"{doc.page} / 2")
    pdf.restoreState()


def main():
    source = (ROOT / "credit_memo.md").read_text(encoding="utf-8")
    story = []
    for block in source.strip().split("\n\n"):
        if block.startswith("# "):
            story.append(Paragraph(markup(block[2:]), TITLE))
        elif block.startswith("**"):
            story.append(Paragraph(markup(block.strip("*")), DECK))
        elif block.startswith("## "):
            if block == "## What breaks the takeout":
                story.append(PageBreak())
            story.append(Paragraph(markup(block[3:]), HEAD))
        elif block.startswith("|"):
            story.append(case_table(block.splitlines()))
        else:
            story.append(Paragraph(markup(block), REF if block.startswith(("[1]", "[2]", "[3]")) else BODY))
    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    pdf = SimpleDocTemplate(str(out / "DATA_2023_CNTR_Credit_Memo.pdf"),
                            pagesize=(612, 792), leftMargin=57, rightMargin=57,
                            topMargin=50, bottomMargin=60, invariant=1)
    pdf.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    main()
