"""
export_payments.py
──────────────────
Pulls every APPROVED payment from the DB, groups them by created_at date,
downloads the Telegram proof screenshot for each payment, and saves a
detailed PDF summary per day.

Folder layout:
  payments_export/
    2025-01-10/
      pay_42_user_123456.jpg
      pay_43_user_789012.jpg
      SUMMARY_2025-01-10.pdf
    2025-01-11/
      ...
    MASTER_SUMMARY.pdf

Usage:
  pip install asyncpg aiohttp aiofiles reportlab python-dotenv
  python export_payments.py

  Optional flags:
    --from 2025-01-01   only include payments created on/after this date
    --to   2025-01-31   only include payments created on/before this date
"""

import asyncio
import asyncpg
import aiohttp
import aiofiles
import argparse
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
OUTPUT_DIR   = Path("payments_export")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("payment_export")

# ──────────────────────────────────────────────────────────────────────────────
# BRAND PALETTE — clean corporate (navy + gold)
# ──────────────────────────────────────────────────────────────────────────────
C_NAVY       = colors.HexColor("#0A2342")
C_NAVY_MID   = colors.HexColor("#1A3A5C")
C_GOLD       = colors.HexColor("#C9A84C")
C_GOLD_LIGHT = colors.HexColor("#F5EDD6")
C_WHITE      = colors.white
C_OFF_WHITE  = colors.HexColor("#F8F9FB")
C_RULE       = colors.HexColor("#D6DCE4")
C_TEXT       = colors.HexColor("#1C2833")
C_TEXT_MUTED = colors.HexColor("#7F8C8D")
C_SUCCESS    = colors.HexColor("#1A7A4A")
C_ROW_ALT    = colors.HexColor("#F0F4FA")
C_WARN       = colors.HexColor("#C0392B")


# ──────────────────────────────────────────────────────────────────────────────
# LETTERHEAD CANVAS — navy stripe header + footer on every page
# ──────────────────────────────────────────────────────────────────────────────
class LetterheadCanvas:
    def __init__(self, filename, **kwargs):
        from reportlab.pdfgen import canvas as rl_canvas
        self._canvas = rl_canvas.Canvas(filename, **kwargs)
        self._saved_page_states = []
        self.width, self.height = A4

    def showPage(self):
        self._saved_page_states.append(dict(self._canvas.__dict__))
        self._canvas._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for i, state in enumerate(self._saved_page_states):
            self._canvas.__dict__.update(state)
            self._draw_decorations(i + 1, total)
            self._canvas.showPage()
        self._canvas.save()

    def _draw_decorations(self, page_num: int, total_pages: int):
        c = self._canvas
        w, h = self.width, self.height

        # Navy top stripe
        c.setFillColor(C_NAVY)
        c.rect(0, h - 20*mm, w, 20*mm, fill=1, stroke=0)

        # Gold underline stripe
        c.setFillColor(C_GOLD)
        c.rect(0, h - 20*mm - 1.5*mm, w, 1.5*mm, fill=1, stroke=0)

        # Brand name
        c.setFillColor(C_WHITE)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(18*mm, h - 12*mm, "DIGITAL REVENUE")

        # Separator dot
        c.setFillColor(C_GOLD)
        c.circle(18*mm + 116, h - 10.5*mm, 1.8, fill=1, stroke=0)

        # System subtitle
        c.setFillColor(colors.HexColor("#A8BDD4"))
        c.setFont("Helvetica", 8)
        c.drawString(18*mm + 125, h - 12*mm, "Payment Intelligence System")

        # Page number (right)
        c.setFillColor(C_GOLD)
        c.setFont("Helvetica", 8)
        c.drawRightString(w - 18*mm, h - 12*mm, f"Page {page_num} / {total_pages}")

        # Footer band
        c.setFillColor(C_RULE)
        c.rect(0, 0, w, 11*mm, fill=1, stroke=0)
        c.setFillColor(C_TEXT_MUTED)
        c.setFont("Helvetica", 6.5)
        c.drawString(18*mm, 4*mm, "CONFIDENTIAL — Digital Revenue Internal Audit  ·  Do not distribute.")
        c.drawRightString(
            w - 18*mm, 4*mm,
            f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}  ·  Digital Revenue © {datetime.now().year}",
        )

    def __getattr__(self, name):
        return getattr(self._canvas, name)


def _build_doc(path: Path, story: list):
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18*mm,
        rightMargin=18*mm,
        topMargin=26*mm,    # clears the 20mm stripe + 1.5mm gold + 4.5mm breathing room
        bottomMargin=16*mm, # clears the 11mm footer band
    )
    doc.build(story, canvasmaker=lambda fn, **kw: LetterheadCanvas(fn, pagesize=A4))


# ──────────────────────────────────────────────────────────────────────────────
# STYLES
# ──────────────────────────────────────────────────────────────────────────────
def _styles() -> dict:
    base = getSampleStyleSheet()
    def s(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], **kw)
    return {
        "doc_title":    s("doc_title",   fontSize=24, textColor=C_NAVY,
                          fontName="Helvetica-Bold", spaceAfter=3, leading=28),
        "doc_subtitle": s("doc_subtitle",fontSize=10, textColor=C_GOLD,
                          fontName="Helvetica-Bold", spaceAfter=2, leading=13),
        "doc_meta":     s("doc_meta",    fontSize=8,  textColor=C_TEXT_MUTED, leading=12),

        "section_h":    s("section_h",   fontSize=10.5, textColor=C_NAVY,
                          fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=2, leading=13),
        "section_sub":  s("section_sub", fontSize=8, textColor=C_TEXT_MUTED, spaceAfter=5),

        "kpi_value":    s("kpi_value",   fontSize=21, textColor=C_NAVY,
                          fontName="Helvetica-Bold", alignment=TA_CENTER, leading=24),
        "kpi_unit":     s("kpi_unit",    fontSize=7.5, textColor=C_GOLD,
                          fontName="Helvetica-Bold", alignment=TA_CENTER, leading=10),
        "kpi_label":    s("kpi_label",   fontSize=7.5, textColor=C_TEXT_MUTED,
                          alignment=TA_CENTER, leading=10),

        "th":           s("th",  fontSize=7.5, textColor=C_WHITE,
                          fontName="Helvetica-Bold", alignment=TA_CENTER, leading=10),
        "th_l":         s("th_l",fontSize=7.5, textColor=C_WHITE,
                          fontName="Helvetica-Bold", alignment=TA_LEFT,   leading=10),
        "td":           s("td",  fontSize=8, textColor=C_TEXT,
                          alignment=TA_LEFT,   leading=11),
        "td_c":         s("td_c",fontSize=8, textColor=C_TEXT,
                          alignment=TA_CENTER, leading=11),
        "td_r":         s("td_r",fontSize=8, textColor=C_TEXT,
                          alignment=TA_RIGHT,  leading=11),
        "td_money":     s("td_money", fontSize=8, textColor=C_SUCCESS,
                          fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=11),

        "body":         s("body",  fontSize=9,  textColor=C_TEXT,
                          leading=14, alignment=TA_JUSTIFY),
        "note":         s("note",  fontSize=8,  textColor=C_TEXT_MUTED,
                          leading=12, alignment=TA_JUSTIFY),
        "warn":         s("warn",  fontSize=8,  textColor=C_WARN,
                          fontName="Helvetica-Bold", leading=12),
        "footer":       s("footer",fontSize=7,  textColor=C_TEXT_MUTED,
                          alignment=TA_CENTER, leading=10),
        "total_label":  s("total_label", fontSize=8.5, textColor=C_NAVY,
                          fontName="Helvetica-Bold", alignment=TA_LEFT,  leading=11),
        "total_val":    s("total_val",   fontSize=8.5, textColor=C_SUCCESS,
                          fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=11),
        "big_num":      s("big_num", fontSize=18, textColor=C_SUCCESS,
                          fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=22),
    }


def _hr(color=C_RULE, thickness=0.75):
    return HRFlowable(width="100%", thickness=thickness, color=color,
                      spaceAfter=0, spaceBefore=0)


def _section(title: str, subtitle: str, s: dict) -> list:
    return [
        Spacer(1, 0.35*cm),
        Paragraph(title.upper(), s["section_h"]),
        Paragraph(subtitle,      s["section_sub"]),
        _hr(C_GOLD, 0.8),
        Spacer(1, 0.2*cm),
    ]


# ──────────────────────────────────────────────────────────────────────────────
# KPI CARDS
# ──────────────────────────────────────────────────────────────────────────────
def _kpi_block(payments: list[dict], s: dict) -> Table:
    total  = sum(float(p["amount"] or 0) for p in payments)
    count  = len(payments)
    avg    = total / count if count else 0
    buyers = len({p["telegram_id"] for p in payments})

    kpis = [
        (f"{total:,.0f}", "ETB",  "Total Revenue"),
        (str(count),      "TXN",  "Transactions"),
        (f"{avg:,.0f}",   "ETB",  "Avg per Sale"),
        (str(buyers),     "USR",  "Unique Buyers"),
    ]

    val_row   = [Paragraph(v,  s["kpi_value"]) for v, _, _ in kpis]
    unit_row  = [Paragraph(u,  s["kpi_unit"])  for _, u, _ in kpis]
    label_row = [Paragraph(l,  s["kpi_label"]) for _, _, l in kpis]

    # 4 cards with 3mm gap between = (174mm - 9mm) / 4 each
    card_w = (A4[0] - 36*mm - 9*mm) / 4

    t = Table(
        [val_row, unit_row, label_row],
        colWidths=[card_w]*4,
        rowHeights=[1.35*cm, 0.42*cm, 0.42*cm],
        hAlign="LEFT",
    )
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_OFF_WHITE),
        # Individual card borders
        *[("BOX", (i, 0), (i, -1), 0.4, C_RULE) for i in range(4)],
        # Top accent: navy on 0,2 — gold on 1,3
        ("LINEABOVE",     (0, 0), (0, 0), 3.5, C_NAVY),
        ("LINEABOVE",     (1, 0), (1, 0), 3.5, C_GOLD),
        ("LINEABOVE",     (2, 0), (2, 0), 3.5, C_NAVY),
        ("LINEABOVE",     (3, 0), (3, 0), 3.5, C_GOLD),
        ("TOPPADDING",    (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("TOPPADDING",    (0, 1), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    return t


# ──────────────────────────────────────────────────────────────────────────────
# PAYMENT DETAIL TABLE
# ──────────────────────────────────────────────────────────────────────────────
def _payment_table(payments: list[dict], s: dict) -> Table:
    headers = ["#", "ID", "Full Name", "Username", "Lang",
               "Level", "Product", "Amount (ETB)", "Submitted", "Proof"]

    header_row = [
        Paragraph(h, s["th_l"] if h in ("Full Name", "Username", "Product") else s["th"])
        for h in headers
    ]
    rows = [header_row]

    for i, p in enumerate(payments):
        submitted = (
            p["created_at"].strftime("%d %b %Y\n%H:%M")
            if p.get("created_at") else "—"
        )
        proof_mark = "✓" if p.get("proof_file_id") else "✗"
        uname      = f"@{p['username']}" if p.get("username") and p["username"] != "N/A" else "—"

        rows.append([
            Paragraph(str(i + 1),                s["td_c"]),
            Paragraph(str(p["payment_id"]),       s["td_c"]),
            Paragraph(p["full_name"][:24],        s["td"]),
            Paragraph(uname[:20],                 s["td"]),
            Paragraph(p["language"],              s["td_c"]),
            Paragraph(p["level"][:14],            s["td"]),
            Paragraph(p["product_title"][:26],    s["td"]),
            Paragraph(f"{float(p['amount'] or 0):,.2f}", s["td_money"]),
            Paragraph(submitted,                  s["td_c"]),
            Paragraph(proof_mark,                 s["td_c"]),
        ])

    # total = 174mm
    col_w = [c * cm for c in [0.65, 1.0, 3.1, 2.5, 0.85, 2.1, 3.5, 2.4, 2.1, 1.1]]

    t = Table(rows, colWidths=col_w, repeatRows=1, splitByRow=True)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (-1, 0),  C_NAVY),
        ("TEXTCOLOR",     (0, 0),  (-1, 0),  C_WHITE),
        ("FONTNAME",      (0, 0),  (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0),  (-1, 0),  7.5),
        ("TOPPADDING",    (0, 0),  (-1, 0),  6),
        ("BOTTOMPADDING", (0, 0),  (-1, 0),  6),

        ("FONTSIZE",      (0, 1),  (-1, -1), 8),
        ("ROWBACKGROUNDS",(0, 1),  (-1, -1), [C_WHITE, C_ROW_ALT]),
        ("GRID",          (0, 0),  (-1, -1), 0.3, C_RULE),
        ("TOPPADDING",    (0, 1),  (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1),  (-1, -1), 4),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 5),

        # Gold highlight on the amount column
        ("BACKGROUND",    (7, 1),  (7, -1),  colors.HexColor("#F2FBF2")),
        ("LINEAFTER",     (6, 0),  (6, -1),  0.8, C_GOLD),
        ("LINEBEFORE",    (8, 0),  (8, -1),  0.8, C_GOLD),

        ("ALIGN",         (9, 0),  (9, -1),  "CENTER"),
        ("FONTNAME",      (9, 1),  (9, -1),  "Helvetica-Bold"),
        ("TEXTCOLOR",     (9, 1),  (9, -1),  C_SUCCESS),
    ]))
    return t


# ──────────────────────────────────────────────────────────────────────────────
# PRODUCT BREAKDOWN TABLE
# ──────────────────────────────────────────────────────────────────────────────
def _product_table(payments: list[dict], s: dict) -> Table:
    totals: dict[str, dict] = {}
    for p in payments:
        t = p["product_title"]
        if t not in totals:
            totals[t] = {"count": 0, "revenue": 0.0}
        totals[t]["count"]   += 1
        totals[t]["revenue"] += float(p["amount"] or 0)

    sorted_items = sorted(totals.items(), key=lambda x: x[1]["revenue"], reverse=True)
    grand_rev   = sum(v["revenue"] for v in totals.values())
    grand_count = sum(v["count"]   for v in totals.values())

    headers = ["Product", "Sales", "Revenue (ETB)", "Share"]
    rows = [[Paragraph(h, s["th_l"] if h == "Product" else s["th"]) for h in headers]]

    for title, data in sorted_items:
        share = (data["revenue"] / grand_rev * 100) if grand_rev else 0
        # Simple ASCII bar (max 12 chars wide)
        filled = int(share / 100 * 12)
        bar    = "▓" * filled + "░" * (12 - filled)
        rows.append([
            Paragraph(title[:46],                          s["td"]),
            Paragraph(str(data["count"]),                  s["td_c"]),
            Paragraph(f"{data['revenue']:,.2f}",           s["td_money"]),
            Paragraph(f"{share:5.1f}%  {bar}",             s["td"]),
        ])

    rows.append([
        Paragraph("TOTAL", s["total_label"]),
        Paragraph(str(grand_count), s["total_val"]),
        Paragraph(f"{grand_rev:,.2f}", s["total_val"]),
        Paragraph("100.0%", s["total_label"]),
    ])

    col_w = [9.5*cm, 2.0*cm, 3.8*cm, 4.1*cm]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (-1, 0),  C_NAVY_MID),
        ("TEXTCOLOR",     (0, 0),  (-1, 0),  C_WHITE),
        ("FONTNAME",      (0, 0),  (-1, 0),  "Helvetica-Bold"),
        ("ROWBACKGROUNDS",(0, 1),  (-1, -2), [C_WHITE, C_OFF_WHITE]),
        ("BACKGROUND",    (0, -1), (-1, -1), C_GOLD_LIGHT),
        ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE",     (0, -1), (-1, -1), 1.2, C_GOLD),
        ("GRID",          (0, 0),  (-1, -1), 0.3, C_RULE),
        ("TOPPADDING",    (0, 0),  (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 5),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 7),
        ("ALIGN",         (1, 0),  (3, -1),  "CENTER"),
        ("ALIGN",         (2, 1),  (2, -1),  "RIGHT"),
    ]))
    return t


# ──────────────────────────────────────────────────────────────────────────────
# RECONCILIATION BOX
# ──────────────────────────────────────────────────────────────────────────────
def _recon_box(payments: list[dict], day_str: str | None, s: dict,
               missing_ids: list[int] | None = None) -> Table:
    total = sum(float(p["amount"] or 0) for p in payments)
    period_label = f"for {day_str}" if day_str else "across this date range"

    note_text = (
        f"This is the total collected from {len(payments)} approved payment(s) submitted "
        f"{period_label}. Compare this figure to your bank statement. "
        "Possible causes of a gap: (1) manual transfer that bypassed the bot, "
        "(2) payment approved on a different date than submitted, "
        "(3) a duplicate approval."
    )

    rows = [
        [
            Paragraph("EXPECTED ACCOUNT CREDIT", s["section_h"]),
            Paragraph(f"{total:,.2f} ETB", s["big_num"]),
        ],
        [
            Paragraph(note_text, s["note"]),
            Paragraph("", s["note"]),
        ],
    ]
    if missing_ids:
        rows.append([
            Paragraph(
                f"⚠  Proof screenshots unavailable for Payment IDs: "
                f"{', '.join(str(i) for i in missing_ids)}. "
                "These files may have expired from Telegram's servers.",
                s["warn"],
            ),
            Paragraph("", s["note"]),
        ])

    span_rows = [("SPAN", (0, i), (-1, i)) for i in range(1, len(rows))]

    t = Table(rows, colWidths=[12*cm, 6.4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), C_OFF_WHITE),
        ("BOX",          (0, 0), (-1, -1), 0.4, C_RULE),
        ("LINEABOVE",    (0, 0), (-1, 0),  3.5, C_NAVY),
        ("TOPPADDING",   (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN",       (0, 0), (-1, 0),  "MIDDLE"),
        *span_rows,
    ]))
    return t


# ──────────────────────────────────────────────────────────────────────────────
# PER-DAY PDF
# ──────────────────────────────────────────────────────────────────────────────
def generate_day_pdf(
    day_str: str,
    payments: list[dict],
    folder: Path,
    screenshot_paths: dict[int, Path | None],
) -> Path:
    pdf_path = folder / f"SUMMARY_{day_str}.pdf"
    s = _styles()
    story = []

    # Title block
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph("DAILY PAYMENT REPORT", s["doc_title"]))
    story.append(Paragraph(f"Period: {day_str}  ·  Grouped by submission date (created_at)", s["doc_subtitle"]))
    story.append(Paragraph(
        f"Filter: APPROVED ONLY  ·  Records: {len(payments)}  ·  "
        f"Exported: {datetime.now().strftime('%d %B %Y, %H:%M')}",
        s["doc_meta"],
    ))
    story.append(Spacer(1, 0.25*cm))
    story.append(_hr(C_NAVY, 1.5))

    # KPIs
    story += _section("Key Metrics", "Revenue and transaction summary for this day.", s)
    story.append(_kpi_block(payments, s))

    # Transaction register
    story += _section(
        "Transaction Register",
        "All approved payments submitted on this day, ordered chronologically.",
        s,
    )
    story.append(_payment_table(payments, s))

    # Product breakdown
    story += _section("Revenue by Product", "Sales breakdown across active products.", s)
    story.append(_product_table(payments, s))

    # Reconciliation
    story.append(Spacer(1, 0.5*cm))
    story.append(_hr(C_RULE))
    story.append(Spacer(1, 0.3*cm))
    missing = [p["payment_id"] for p in payments if not screenshot_paths.get(p["payment_id"])]
    story.append(_recon_box(payments, day_str, s, missing))

    _build_doc(pdf_path, story)
    log.info("  PDF saved: %s", pdf_path.name)
    return pdf_path


# ──────────────────────────────────────────────────────────────────────────────
# MASTER PDF
# ──────────────────────────────────────────────────────────────────────────────
def generate_master_pdf(
    all_payments: list[dict],
    output_dir: Path,
    date_from: date | None,
    date_to: date | None,
) -> Path:
    pdf_path = output_dir / "MASTER_SUMMARY.pdf"
    s = _styles()
    story = []

    # Cover
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph("MASTER PAYMENT AUDIT", s["doc_title"]))
    story.append(Paragraph("Consolidated Revenue Intelligence Report", s["doc_subtitle"]))
    dr = f"{date_from or 'All Time'}  →  {date_to or 'Today'}"
    story.append(Paragraph(
        f"Date range: {dr}  ·  Total records: {len(all_payments)}  ·  "
        f"Exported: {datetime.now().strftime('%d %B %Y, %H:%M')}",
        s["doc_meta"],
    ))
    story.append(Spacer(1, 0.25*cm))
    story.append(_hr(C_NAVY, 2))

    # Grand KPIs
    story += _section("Portfolio Overview", "Aggregated metrics across all approved payments.", s)
    story.append(_kpi_block(all_payments, s))

    # Day-by-day table
    by_day: dict[str, list] = defaultdict(list)
    for p in all_payments:
        day_str = p["created_at"].strftime("%Y-%m-%d") if p.get("created_at") else "unknown"
        by_day[day_str].append(p)

    story += _section(
        "Day-by-Day Summary",
        "Revenue and transaction count grouped by payment submission date (created_at).",
        s,
    )

    headers = ["Date", "Transactions", "Unique Buyers", "Revenue (ETB)", "Running Total (ETB)"]
    rows = [[Paragraph(h, s["th"]) for h in headers]]

    running = 0.0
    for day_str in sorted(by_day.keys()):
        dp = by_day[day_str]
        rev = sum(float(p["amount"] or 0) for p in dp)
        running += rev
        rows.append([
            Paragraph(day_str,                                          s["td_c"]),
            Paragraph(str(len(dp)),                                     s["td_c"]),
            Paragraph(str(len({p["telegram_id"] for p in dp})),         s["td_c"]),
            Paragraph(f"{rev:,.2f}",                                    s["td_money"]),
            Paragraph(f"{running:,.2f}",                                s["td_r"]),
        ])

    # Grand total row
    grand_buyers = len({p["telegram_id"] for p in all_payments})
    rows.append([
        Paragraph("GRAND TOTAL",             s["total_label"]),
        Paragraph(str(len(all_payments)),    s["total_val"]),
        Paragraph(str(grand_buyers),         s["total_val"]),
        Paragraph(f"{running:,.2f}",         s["total_val"]),
        Paragraph("",                        s["td"]),
    ])

    col_w = [3.2*cm, 3.0*cm, 3.0*cm, 4.2*cm, 4.5*cm]
    day_t = Table(rows, colWidths=col_w, repeatRows=1)
    day_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (-1, 0),  C_NAVY),
        ("TEXTCOLOR",     (0, 0),  (-1, 0),  C_WHITE),
        ("FONTNAME",      (0, 0),  (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0),  (-1, 0),  7.5),
        ("ROWBACKGROUNDS",(0, 1),  (-1, -2), [C_WHITE, C_ROW_ALT]),
        ("BACKGROUND",    (0, -1), (-1, -1), C_GOLD_LIGHT),
        ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE",     (0, -1), (-1, -1), 1.5, C_GOLD),
        ("GRID",          (0, 0),  (-1, -1), 0.3, C_RULE),
        ("TOPPADDING",    (0, 0),  (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 5),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 7),
        ("ALIGN",         (1, 0),  (-1, -1), "CENTER"),
        ("ALIGN",         (3, 1),  (4, -1),  "RIGHT"),
        ("TEXTCOLOR",     (3, 1),  (3, -2),  C_SUCCESS),
        ("FONTNAME",      (3, 1),  (3, -2),  "Helvetica-Bold"),
    ]))
    story.append(day_t)

    # Product breakdown
    story.append(PageBreak())
    story += _section(
        "All-Time Product Performance",
        "Revenue contribution and sales volume per product, sorted by total revenue.",
        s,
    )
    story.append(_product_table(all_payments, s))

    # Reconciliation
    story.append(Spacer(1, 0.6*cm))
    story.append(_hr(C_RULE))
    story.append(Spacer(1, 0.3*cm))
    story.append(_recon_box(all_payments, None, s))

    _build_doc(pdf_path, story)
    log.info("Master PDF saved: %s", pdf_path)
    return pdf_path


# ──────────────────────────────────────────────────────────────────────────────
# DATABASE QUERY
# ──────────────────────────────────────────────────────────────────────────────
async def fetch_approved_payments(
    conn: asyncpg.Connection,
    date_from: date | None,
    date_to: date | None,
) -> list[dict]:
    where_clauses = ["p.status = 'approved'"]
    params: list = []

    if date_from:
        params.append(date_from)
        where_clauses.append(f"p.created_at::date >= ${len(params)}")
    if date_to:
        params.append(date_to)
        where_clauses.append(f"p.created_at::date <= ${len(params)}")

    where_sql = " AND ".join(where_clauses)

    query = f"""
        SELECT
            p.id                                    AS payment_id,
            p.amount,
            p.proof_file_id,
            p.created_at,
            p.approved_at,
            u.telegram_id,
            COALESCE(u.full_name, 'Unknown')        AS full_name,
            COALESCE(u.username,  'N/A')            AS username,
            COALESCE(u.language,  'EN')             AS language,
            COALESCE(u.gender,    'N/A')            AS gender,
            COALESCE(u.level,     'N/A')            AS level,
            pr.title                                AS product_title,
            pr.price                                AS product_price
        FROM  payments p
        JOIN  users    u  ON u.telegram_id = p.user_id
        JOIN  products pr ON pr.id         = p.product_id
        WHERE {where_sql}
        ORDER BY p.created_at ASC
    """
    rows = await conn.fetch(query, *params)
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────────────────────────────────────
# TELEGRAM FILE DOWNLOAD
# ──────────────────────────────────────────────────────────────────────────────
async def get_file_url(session: aiohttp.ClientSession, file_id: str) -> str | None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile"
    try:
        async with session.get(url, params={"file_id": file_id},
                               timeout=aiohttp.ClientTimeout(total=15)) as resp:
            data = await resp.json()
            if data.get("ok") and data["result"].get("file_path"):
                return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{data['result']['file_path']}"
    except Exception as e:
        log.warning("getFile failed (%s): %s", file_id[:20], e)
    return None


async def download_screenshot(
    session: aiohttp.ClientSession,
    payment: dict,
    folder: Path,
) -> Path | None:
    file_id = payment.get("proof_file_id")
    if not file_id:
        log.warning("Payment #%s — no proof_file_id.", payment["payment_id"])
        return None

    url = await get_file_url(session, file_id)
    if not url:
        log.warning("Payment #%s — could not resolve Telegram URL.", payment["payment_id"])
        return None

    ext      = url.rsplit(".", 1)[-1].lower() if "." in url.rsplit("/", 1)[-1] else "jpg"
    filename = f"pay_{payment['payment_id']}_user_{payment['telegram_id']}.{ext}"
    dest     = folder / filename

    if dest.exists():
        log.info("  Already exists: %s", filename)
        return dest

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            async with aiofiles.open(dest, "wb") as f:
                await f.write(await resp.read())
        log.info("  ✓ %s", filename)
        return dest
    except Exception as e:
        log.error("  ✗ Payment #%s download failed: %s", payment["payment_id"], e)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
async def main(date_from: date | None, date_to: date | None):
    if not DATABASE_URL:
        log.error("DATABASE_URL not set in .env"); sys.exit(1)
    if not BOT_TOKEN:
        log.error("BOT_TOKEN not set in .env"); sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Connecting to database …")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        payments = await fetch_approved_payments(conn, date_from, date_to)
    finally:
        await conn.close()

    if not payments:
        log.warning("No approved payments found. Nothing to export.")
        return

    log.info("Found %d approved payments.", len(payments))

    # Group by created_at date
    by_day: dict[str, list] = defaultdict(list)
    for p in payments:
        day_str = p["created_at"].strftime("%Y-%m-%d") if p.get("created_at") else "unknown"
        by_day[day_str].append(p)

    log.info("Grouped into %d day(s): %s", len(by_day), ", ".join(sorted(by_day.keys())))

    async with aiohttp.ClientSession() as session:
        for day_str in sorted(by_day.keys()):
            day_payments = by_day[day_str]
            folder = OUTPUT_DIR / day_str
            folder.mkdir(parents=True, exist_ok=True)

            log.info("── %s  (%d payments) ──", day_str, len(day_payments))

            screenshot_paths: dict[int, Path | None] = {}
            for p in day_payments:
                screenshot_paths[p["payment_id"]] = await download_screenshot(session, p, folder)

            generate_day_pdf(day_str, day_payments, folder, screenshot_paths)

    log.info("Generating master summary …")
    generate_master_pdf(payments, OUTPUT_DIR, date_from, date_to)

    total_rev = sum(float(p["amount"] or 0) for p in payments)

    print("\n" + "═" * 58)
    print("  DIGITAL REVENUE — EXPORT COMPLETE")
    print("═" * 58)
    print(f"  Output folder  : {OUTPUT_DIR.resolve()}")
    print(f"  Days processed : {len(by_day)}")
    print(f"  Total payments : {len(payments)}")
    print(f"  DB total       : {total_rev:,.2f} ETB")
    print("═" * 58)
    print("  Open MASTER_SUMMARY.pdf → compare the DB total")
    print("  to your bank statement to locate the 4K gap.")
    print("═" * 58 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Digital Revenue — Export approved payments by day.")
    parser.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD",
                        help="Only include payments created on/after this date")
    parser.add_argument("--to",   dest="date_to",   metavar="YYYY-MM-DD",
                        help="Only include payments created on/before this date")
    args = parser.parse_args()

    def _d(v): return datetime.strptime(v, "%Y-%m-%d").date() if v else None

    asyncio.run(main(_d(args.date_from), _d(args.date_to)))