#!/usr/bin/env python3
"""Render a readable, paginated PDF handover from a reviewed Markdown source.

Research/handovers only; runs exclusively in copilot_project.
"""
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, HRFlowable
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import re
import sys

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
destination.parent.mkdir(parents=True, exist_ok=True)
regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
if Path(regular).exists():
    pdfmetrics.registerFont(TTFont("DejaVu", regular))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold))
    body_font, heading_font = "DejaVu", "DejaVu-Bold"
else:
    body_font, heading_font = "Helvetica", "Helvetica-Bold"

navy = colors.HexColor("#15243A")
blue = colors.HexColor("#1766A3")
muted = colors.HexColor("#546579")
rule = colors.HexColor("#DAE2EC")
styles = {
 "hero": ParagraphStyle("hero", fontName=heading_font, fontSize=17, leading=23,
                        spaceAfter=10, textColor=navy, keepWithNext=True),
 "h2": ParagraphStyle("h2", fontName=heading_font, fontSize=11.5, leading=16,
                      spaceBefore=13, spaceAfter=7, textColor=blue, keepWithNext=True),
 "body": ParagraphStyle("body", fontName=body_font, fontSize=8.15, leading=12.2,
                        spaceAfter=6, textColor=navy, splitLongWords=True),
 "bullet": ParagraphStyle("bullet", fontName=body_font, fontSize=8.15, leading=12,
                         leftIndent=13, firstLineIndent=-10, spaceAfter=4, textColor=navy),
 "code": ParagraphStyle("code", fontName=body_font, fontSize=7.2, leading=11.2,
                       leftIndent=9, spaceAfter=5, textColor=muted),
 "subtitle": ParagraphStyle("subtitle", fontName=body_font, fontSize=8.4, leading=13,
                          spaceAfter=8, textColor=muted),
}
def inline_markup(s: str):
    s = escape(s)
    # Text inside backticks is displayed in a contrasting strong font.
    s = re.sub(r"`([^`]+)`", lambda m: "<font color='#1766A3'>" + m.group(1) + "</font>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return s

doc = SimpleDocTemplate(str(destination), pagesize=A4, leftMargin=18*mm,
                        rightMargin=18*mm, topMargin=21*mm, bottomMargin=19*mm,
                        title="Mist LineageOS 23.2 Technical Handover - 2026-11-12",
                        author="Mist bring-up project")
story = []
for raw in source.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line:
        continue
    if line.startswith("# "):
        story.append(Paragraph(inline_markup(line[2:]), styles["hero"]))
        story.append(HRFlowable(width="100%", thickness=1.1, color=blue, spaceAfter=8))
    elif line.startswith("## "):
        story.append(Paragraph(inline_markup(line[3:]), styles["h2"]))
    elif line.startswith("* ") or line.startswith("- "):
        story.append(Paragraph("&#8226; " + inline_markup(line[2:]), styles["bullet"]))
    elif re.match(r"^\d+[.] ", line):
        story.append(Paragraph(inline_markup(line), styles["bullet"]))
    elif line.startswith("STEP ") or line.startswith("DONE:") or line.startswith("PENDING:"):
        story.append(Paragraph(inline_markup(line), styles["bullet"]))
    else:
        story.append(Paragraph(inline_markup(line), styles["body"]))
def page_decor(canvas, document):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(rule)
    canvas.setLineWidth(.6)
    canvas.line(18*mm, height-14*mm, width-18*mm, height-14*mm)
    canvas.setFont(body_font, 7.1)
    canvas.setFillColor(muted)
    canvas.drawString(18*mm, 12.5*mm, "MIST / LINEAGEOS 23.2   |   VERIFIED TECHNICAL HANDOVER   |   12 NOV 2026")
    canvas.drawRightString(width-18*mm, 12.5*mm, f"Page {document.page}")
    canvas.restoreState()

doc.build(story, onFirstPage=page_decor, onLaterPages=page_decor)
if destination.stat().st_size < 8000:
    raise SystemExit("Generated PDF unexpectedly small")
print(f"PDF created: {destination} ({destination.stat().st_size} bytes)")
