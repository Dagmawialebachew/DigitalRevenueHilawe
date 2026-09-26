"""
export_payments.py
──────────────────
Pulls every APPROVED payment from BOTH revenue streams, groups them by
created_at date, downloads Telegram proof screenshots into stream-separated
sub-folders, and produces premium PDF summaries per day + a master audit.

━━━ REVENUE STREAMS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Stream A  →  payments       (product sales, variable amount, joined to products)
  Stream B  →  club_payments  (club subscriptions, fixed 299 ETB, processed_by)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Folder layout:
  payments_export/
  ├── 2025-01-10/
  │   ├── product_sales/
  │   │   ├── pay_42_user_123456.jpg
  │   │   └── pay_43_user_789012.jpg
  │   ├── club_payments/
  │   │   ├── club_7_user_111222.jpg
  │   │   └── club_8_user_333444.jpg
  │   └── DAILY_SUMMARY_2025-01-10.pdf
  ├── 2025-01-11/
  │   └── ...
  └── MASTER_AUDIT.pdf

Usage:
  pip install asyncpg aiohttp aiofiles reportlab python-dotenv
  python export_payments.py

  Optional flags:
    --from  2025-01-01   only include payments created on/after this date
    --to    2025-01-31   only include payments created on/before this date
    --stream sales       export only product sales  (default: both)
    --stream club        export only club payments  (default: both)
"""

import asyncio
import asyncpg
import aiohttp
import aiofiles
import argparse
import csv
import io
import json
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

from PIL import Image, ImageDraw, ImageFont, ImageOps
import pytesseract

from handlers.verify import verify_external

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

# Detect Windows tesseract binary if not already on PATH
for _tp in [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Users\kiruk\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
]:
    if os.path.exists(_tp):
        pytesseract.pytesseract.tesseract_cmd = _tp
        break

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
# BRAND PALETTE
# ──────────────────────────────────────────────────────────────────────────────
C_NAVY        = colors.HexColor("#0A2342")
C_NAVY_MID    = colors.HexColor("#1A3A5C")
C_NAVY_LIGHT  = colors.HexColor("#EEF3FA")
C_GOLD        = colors.HexColor("#C9A84C")
C_GOLD_LIGHT  = colors.HexColor("#F5EDD6")
C_WHITE       = colors.white
C_OFF_WHITE   = colors.HexColor("#F8F9FB")
C_RULE        = colors.HexColor("#D6DCE4")
C_TEXT        = colors.HexColor("#1C2833")
C_TEXT_MUTED  = colors.HexColor("#7F8C8D")
C_SUCCESS     = colors.HexColor("#1A7A4A")
C_SUCCESS_BG  = colors.HexColor("#F2FBF2")
C_ROW_ALT     = colors.HexColor("#F0F4FA")
C_WARN        = colors.HexColor("#C0392B")
C_WARN_BG     = colors.HexColor("#FDF2F0")

# Stream accent colours — Sales=Navy family, Club=Gold family
C_SALES_ACCENT = colors.HexColor("#1A3A5C")   # deep navy
C_CLUB_ACCENT  = colors.HexColor("#A07830")   # deep gold/amber
C_CLUB_BG      = colors.HexColor("#FDF8EE")   # warm cream


# ──────────────────────────────────────────────────────────────────────────────
# LETTERHEAD CANVAS — navy stripe header + footer on every page
# ──────────────────────────────────────────────────────────────────────────────
class LetterheadCanvas:
    """Two-pass canvas that stamps header/footer after all pages are laid out."""

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

        # ── Header ────────────────────────────────────────────────────────────
        c.setFillColor(C_NAVY)
        c.rect(0, h - 20*mm, w, 20*mm, fill=1, stroke=0)

        # double rule: gold thick + thin
        c.setFillColor(C_GOLD)
        c.rect(0, h - 20*mm - 2*mm, w, 2*mm, fill=1, stroke=0)
        c.setFillColor(C_NAVY_MID)
        c.rect(0, h - 20*mm - 2.6*mm, w, 0.6*mm, fill=1, stroke=0)

        # Brand wordmark
        c.setFillColor(C_WHITE)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(18*mm, h - 12.5*mm, "DIGITAL REVENUE")

        # Separator dot
        c.setFillColor(C_GOLD)
        c.circle(18*mm + 117, h - 11*mm, 1.8, fill=1, stroke=0)

        # System subtitle
        c.setFillColor(colors.HexColor("#A8BDD4"))
        c.setFont("Helvetica", 8)
        c.drawString(18*mm + 126, h - 12.5*mm, "Payment Intelligence System")

        # Page n / N  (right side)
        c.setFillColor(C_GOLD)
        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(w - 18*mm, h - 12.5*mm, f"Page {page_num} / {total_pages}")

        # ── Footer ────────────────────────────────────────────────────────────
        c.setFillColor(C_RULE)
        c.rect(0, 0, w, 11*mm, fill=1, stroke=0)
        c.setFillColor(C_GOLD)
        c.rect(0, 11*mm, w, 0.8*mm, fill=1, stroke=0)

        c.setFillColor(C_TEXT_MUTED)
        c.setFont("Helvetica", 6.5)
        c.drawString(18*mm, 4*mm,
                     "CONFIDENTIAL — Digital Revenue Internal Audit  ·  Do not distribute.")
        c.drawRightString(
            w - 18*mm, 4*mm,
            f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            f"  ·  Digital Revenue © {datetime.now().year}",
        )

    def __getattr__(self, name):
        return getattr(self._canvas, name)


def _build_doc(path: Path, story: list):
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18*mm,
        rightMargin=18*mm,
        topMargin=28*mm,     # clears 20mm stripe + 2.6mm rule + breathing room
        bottomMargin=17*mm,  # clears 11mm footer + 0.8mm rule
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
        # Document-level
        "doc_title":      s("doc_title",    fontSize=22, textColor=C_NAVY,
                             fontName="Helvetica-Bold", spaceAfter=3, leading=26),
        "doc_subtitle":   s("doc_subtitle", fontSize=10, textColor=C_GOLD,
                             fontName="Helvetica-Bold", spaceAfter=2, leading=13),
        "doc_meta":       s("doc_meta",     fontSize=7.5, textColor=C_TEXT_MUTED, leading=12),

        # Section headers
        "section_h":      s("section_h",    fontSize=10.5, textColor=C_NAVY,
                             fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=2, leading=13),
        "section_sub":    s("section_sub",  fontSize=8, textColor=C_TEXT_MUTED, spaceAfter=4),
        "stream_badge":   s("stream_badge", fontSize=8.5, textColor=C_WHITE,
                             fontName="Helvetica-Bold", alignment=TA_CENTER, leading=11),

        # KPI cards
        "kpi_value":      s("kpi_value",    fontSize=20, textColor=C_NAVY,
                             fontName="Helvetica-Bold", alignment=TA_CENTER, leading=23),
        "kpi_unit":       s("kpi_unit",     fontSize=7, textColor=C_GOLD,
                             fontName="Helvetica-Bold", alignment=TA_CENTER, leading=10),
        "kpi_label":      s("kpi_label",    fontSize=7, textColor=C_TEXT_MUTED,
                             alignment=TA_CENTER, leading=10),

        # Table cells
        "th":             s("th",     fontSize=7.5, textColor=C_WHITE,
                             fontName="Helvetica-Bold", alignment=TA_CENTER, leading=10),
        "th_l":           s("th_l",   fontSize=7.5, textColor=C_WHITE,
                             fontName="Helvetica-Bold", alignment=TA_LEFT,   leading=10),
        "td":             s("td",     fontSize=7.8, textColor=C_TEXT,
                             alignment=TA_LEFT,   leading=11),
        "td_c":           s("td_c",   fontSize=7.8, textColor=C_TEXT,
                             alignment=TA_CENTER, leading=11),
        "td_r":           s("td_r",   fontSize=7.8, textColor=C_TEXT,
                             alignment=TA_RIGHT,  leading=11),
        "td_money":       s("td_money", fontSize=7.8, textColor=C_SUCCESS,
                             fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=11),
        "td_money_club":  s("td_money_club", fontSize=7.8, textColor=C_CLUB_ACCENT,
                             fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=11),
        "td_ok":          s("td_ok",  fontSize=8, textColor=C_SUCCESS,
                             fontName="Helvetica-Bold", alignment=TA_CENTER, leading=11),
        "td_fail":        s("td_fail",fontSize=8, textColor=C_WARN,
                             fontName="Helvetica-Bold", alignment=TA_CENTER, leading=11),

        # Misc
        "body":           s("body",   fontSize=8.5, textColor=C_TEXT, leading=13,
                             alignment=TA_JUSTIFY),
        "note":           s("note",   fontSize=7.8, textColor=C_TEXT_MUTED, leading=12,
                             alignment=TA_JUSTIFY),
        "warn":           s("warn",   fontSize=8, textColor=C_WARN,
                             fontName="Helvetica-Bold", leading=12),
        "total_label":    s("total_label", fontSize=8.5, textColor=C_NAVY,
                             fontName="Helvetica-Bold", alignment=TA_LEFT,  leading=11),
        "total_val":      s("total_val",   fontSize=8.5, textColor=C_SUCCESS,
                             fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=11),
        "total_val_club": s("total_val_club", fontSize=8.5, textColor=C_CLUB_ACCENT,
                             fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=11),
        "big_num":        s("big_num", fontSize=18, textColor=C_SUCCESS,
                             fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=22),
        "big_num_club":   s("big_num_club", fontSize=18, textColor=C_CLUB_ACCENT,
                             fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=22),
        "combined_num":   s("combined_num", fontSize=22, textColor=C_NAVY,
                             fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=26),
    }


# ──────────────────────────────────────────────────────────────────────────────
# LAYOUT HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def _hr(color=C_RULE, thickness=0.75):
    return HRFlowable(width="100%", thickness=thickness, color=color,
                      spaceAfter=0, spaceBefore=0)


def _section(title: str, subtitle: str, s: dict, accent=C_GOLD) -> list:
    return [
        Spacer(1, 0.35*cm),
        Paragraph(title.upper(), s["section_h"]),
        Paragraph(subtitle,      s["section_sub"]),
        _hr(accent, 0.8),
        Spacer(1, 0.2*cm),
    ]


def _stream_divider(label: str, bg_color: colors.Color, s: dict) -> Table:
    """Full-width coloured banner that labels a revenue stream section."""
    t = Table(
        [[Paragraph(label, s["stream_badge"])]],
        colWidths=[A4[0] - 36*mm],
        rowHeights=[0.65*cm],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg_color),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
    ]))
    return t


# ──────────────────────────────────────────────────────────────────────────────
# KPI BLOCKS — 4-card row, stream-aware colours
# ──────────────────────────────────────────────────────────────────────────────
def _kpi_block(kpis: list[tuple], accent_a=C_NAVY, accent_b=C_GOLD) -> Table:
    """
    kpis: list of (value_str, unit_str, label_str) — exactly 4 items
    Alternating top accent: accent_a on cards 0,2  /  accent_b on cards 1,3
    """
    s = _styles()
    val_row   = [Paragraph(v, s["kpi_value"]) for v, _, _ in kpis]
    unit_row  = [Paragraph(u, s["kpi_unit"])  for _, u, _ in kpis]
    label_row = [Paragraph(l, s["kpi_label"]) for _, _, l in kpis]

    card_w = (A4[0] - 36*mm - 9*mm) / 4

    t = Table(
        [val_row, unit_row, label_row],
        colWidths=[card_w] * 4,
        rowHeights=[1.3*cm, 0.4*cm, 0.4*cm],
        hAlign="LEFT",
    )
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_OFF_WHITE),
        *[("BOX", (i, 0), (i, -1), 0.4, C_RULE) for i in range(4)],
        ("LINEABOVE",     (0, 0), (0, 0), 3.5, accent_a),
        ("LINEABOVE",     (1, 0), (1, 0), 3.5, accent_b),
        ("LINEABOVE",     (2, 0), (2, 0), 3.5, accent_a),
        ("LINEABOVE",     (3, 0), (3, 0), 3.5, accent_b),
        ("TOPPADDING",    (0, 0), (-1, 0),  10),
        ("BOTTOMPADDING", (0, 0), (-1, 0),   2),
        ("TOPPADDING",    (0, 1), (-1, -1),  0),
        ("BOTTOMPADDING", (0, 1), (-1, -1),  8),
        ("LEFTPADDING",   (0, 0), (-1, -1),  8),
        ("RIGHTPADDING",  (0, 0), (-1, -1),  8),
    ]))
    return t


def _sales_kpi_block(payments: list[dict]) -> Table:
    total  = sum(float(p["amount"] or 0) for p in payments)
    count  = len(payments)
    avg    = total / count if count else 0
    buyers = len({p["telegram_id"] for p in payments})
    return _kpi_block([
        (f"{total:,.0f}", "ETB", "Product Sales Revenue"),
        (str(count),      "TXN", "Transactions"),
        (f"{avg:,.0f}",   "ETB", "Avg per Sale"),
        (str(buyers),     "USR", "Unique Buyers"),
    ], C_NAVY, C_GOLD)


def _club_kpi_block(club_payments: list[dict]) -> Table:
    total   = sum(float(p["amount"] or 0) for p in club_payments)
    count   = len(club_payments)
    members = len({p["telegram_id"] for p in club_payments})
    avg     = total / count if count else 0
    return _kpi_block([
        (f"{total:,.0f}",   "ETB", "Club Subscription Revenue"),
        (str(count),        "SUB", "Subscriptions"),
        (f"{avg:,.0f}",     "ETB", "Avg per Sub"),
        (str(members),      "MBR", "Unique Members"),
    ], C_CLUB_ACCENT, C_GOLD)


def _combined_kpi_block(payments: list[dict], club_payments: list[dict]) -> Table:
    p_rev  = sum(float(p["amount"] or 0) for p in payments)
    c_rev  = sum(float(p["amount"] or 0) for p in club_payments)
    total  = p_rev + c_rev
    txns   = len(payments) + len(club_payments)
    buyers = len({p["telegram_id"] for p in payments} |
                 {p["telegram_id"] for p in club_payments})
    avg    = total / txns if txns else 0
    return _kpi_block([
        (f"{total:,.0f}", "ETB", "Combined Revenue"),
        (str(txns),       "TXN", "Total Transactions"),
        (f"{avg:,.0f}",   "ETB", "Blended Avg"),
        (str(buyers),     "USR", "Unique Users"),
    ], C_NAVY, C_CLUB_ACCENT)


# ──────────────────────────────────────────────────────────────────────────────
# REVENUE SPLIT BAR  (visual proportion of sales vs club)
# ──────────────────────────────────────────────────────────────────────────────
def _revenue_split_bar(sales_rev: float, club_rev: float) -> Table:
    total = sales_rev + club_rev
    if total == 0:
        return Spacer(1, 0.1*cm)

    s_pct = sales_rev / total * 100
    c_pct = club_rev  / total * 100
    bar_w = A4[0] - 36*mm

    s_w = bar_w * (sales_rev / total)
    c_w = bar_w - s_w

    # Two-cell table that forms the bar
    bar = Table(
        [[" ", " "]],
        colWidths=[s_w, c_w],
        rowHeights=[0.5*cm],
    )
    bar.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), C_NAVY_MID),
        ("BACKGROUND",    (1, 0), (1, 0), C_CLUB_ACCENT),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))

    # Label row beneath the bar
    s = _styles()
    label = Table(
        [[
            Paragraph(
                f"Product Sales  {s_pct:.1f}%  ({sales_rev:,.0f} ETB)",
                ParagraphStyle("bl", parent=getSampleStyleSheet()["Normal"],
                               fontSize=7.5, textColor=C_NAVY_MID,
                               fontName="Helvetica-Bold"),
            ),
            Paragraph(
                f"Club Subscriptions  {c_pct:.1f}%  ({club_rev:,.0f} ETB)",
                ParagraphStyle("br", parent=getSampleStyleSheet()["Normal"],
                               fontSize=7.5, textColor=C_CLUB_ACCENT,
                               fontName="Helvetica-Bold", alignment=TA_RIGHT),
            ),
        ]],
        colWidths=[bar_w / 2, bar_w / 2],
        rowHeights=[0.4*cm],
    )
    label.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))

    return [bar, label]


# ──────────────────────────────────────────────────────────────────────────────
# PRODUCT SALES DETAIL TABLE
# ──────────────────────────────────────────────────────────────────────────────
def _sales_table(payments: list[dict], s: dict) -> Table:
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
            Paragraph(str(i + 1),                           s["td_c"]),
            Paragraph(str(p["payment_id"]),                 s["td_c"]),
            Paragraph((p["full_name"] or "Unknown")[:24],   s["td"]),
            Paragraph(uname[:20],                           s["td"]),
            Paragraph(p.get("language", "EN"),              s["td_c"]),
            Paragraph((p.get("level") or "N/A")[:14],       s["td"]),
            Paragraph((p.get("product_title") or "—")[:26], s["td"]),
            Paragraph(f"{float(p['amount'] or 0):,.2f}",    s["td_money"]),
            Paragraph(submitted,                            s["td_c"]),
            Paragraph(proof_mark,
                      s["td_ok"] if proof_mark == "✓" else s["td_fail"]),
        ])

    col_w = [c * cm for c in [0.65, 1.0, 3.0, 2.4, 0.8, 2.1, 3.5, 2.5, 2.1, 1.0]]

    t = Table(rows, colWidths=col_w, repeatRows=1, splitByRow=True)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (-1, 0),  C_NAVY),
        ("TEXTCOLOR",     (0, 0),  (-1, 0),  C_WHITE),
        ("FONTNAME",      (0, 0),  (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0),  (-1, 0),  7.5),
        ("TOPPADDING",    (0, 0),  (-1, 0),  6),
        ("BOTTOMPADDING", (0, 0),  (-1, 0),  6),
        ("ROWBACKGROUNDS",(0, 1),  (-1, -1), [C_WHITE, C_ROW_ALT]),
        ("GRID",          (0, 0),  (-1, -1), 0.3, C_RULE),
        ("TOPPADDING",    (0, 1),  (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1),  (-1, -1), 4),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 5),
        # Gold bracket around amount column (col 7)
        ("BACKGROUND",    (7, 1),  (7, -1),  C_SUCCESS_BG),
        ("LINEAFTER",     (6, 0),  (6, -1),  0.8, C_GOLD),
        ("LINEBEFORE",    (8, 0),  (8, -1),  0.8, C_GOLD),
    ]))
    return t


# ──────────────────────────────────────────────────────────────────────────────
# CLUB PAYMENTS DETAIL TABLE
# ──────────────────────────────────────────────────────────────────────────────
def _club_table(club_payments: list[dict], s: dict) -> Table:
    headers = ["#", "ID", "Full Name", "Username", "Amount (ETB)",
               "Processed By", "Submitted", "Approved At", "Proof"]

    header_row = [
        Paragraph(h, s["th_l"] if h in ("Full Name", "Username", "Processed By") else s["th"])
        for h in headers
    ]
    rows = [header_row]

    for i, p in enumerate(club_payments):
        submitted   = (p["created_at"].strftime("%d %b %Y\n%H:%M")
                       if p.get("created_at") else "—")
        approved_at = (p["processed_at"].strftime("%d %b %Y\n%H:%M")
                       if p.get("processed_at") else "—")
        proof_mark  = "✓" if p.get("proof_file_id") else "✗"
        uname       = f"@{p['username']}" if p.get("username") and p["username"] != "N/A" else "—"
        proc_by     = str(p.get("processed_by") or "—")[:20]

        rows.append([
            Paragraph(str(i + 1),                           s["td_c"]),
            Paragraph(str(p["club_payment_id"]),            s["td_c"]),
            Paragraph((p.get("full_name") or "Unknown")[:24], s["td"]),
            Paragraph(uname[:18],                           s["td"]),
            Paragraph(f"{float(p['amount'] or 0):,.2f}",    s["td_money_club"]),
            Paragraph(proc_by,                              s["td"]),
            Paragraph(submitted,                            s["td_c"]),
            Paragraph(approved_at,                          s["td_c"]),
            Paragraph(proof_mark,
                      s["td_ok"] if proof_mark == "✓" else s["td_fail"]),
        ])

    col_w = [c * cm for c in [0.6, 0.9, 3.0, 2.3, 2.5, 2.6, 2.1, 2.1, 1.0]]

    t = Table(rows, colWidths=col_w, repeatRows=1, splitByRow=True)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (-1, 0),  C_CLUB_ACCENT),
        ("TEXTCOLOR",     (0, 0),  (-1, 0),  C_WHITE),
        ("FONTNAME",      (0, 0),  (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0),  (-1, 0),  7.5),
        ("TOPPADDING",    (0, 0),  (-1, 0),  6),
        ("BOTTOMPADDING", (0, 0),  (-1, 0),  6),
        ("ROWBACKGROUNDS",(0, 1),  (-1, -1), [C_WHITE, C_CLUB_BG]),
        ("GRID",          (0, 0),  (-1, -1), 0.3, C_RULE),
        ("TOPPADDING",    (0, 1),  (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1),  (-1, -1), 4),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 5),
        # Amber bracket around amount column (col 4)
        ("BACKGROUND",    (4, 1),  (4, -1),  C_GOLD_LIGHT),
        ("LINEAFTER",     (3, 0),  (3, -1),  0.8, C_CLUB_ACCENT),
        ("LINEBEFORE",    (5, 0),  (5, -1),  0.8, C_CLUB_ACCENT),
    ]))
    return t


# ──────────────────────────────────────────────────────────────────────────────
# PRODUCT BREAKDOWN TABLE  (sales stream)
# ──────────────────────────────────────────────────────────────────────────────
def _product_breakdown_table(payments: list[dict], s: dict) -> Table:
    totals: dict[str, dict] = {}
    for p in payments:
        title = p.get("product_title") or "Unknown Product"
        if title not in totals:
            totals[title] = {"count": 0, "revenue": 0.0}
        totals[title]["count"]   += 1
        totals[title]["revenue"] += float(p["amount"] or 0)

    sorted_items = sorted(totals.items(), key=lambda x: x[1]["revenue"], reverse=True)
    grand_rev    = sum(v["revenue"] for v in totals.values())
    grand_count  = sum(v["count"]   for v in totals.values())

    headers = ["Product", "Sales", "Revenue (ETB)", "Share"]
    rows = [[Paragraph(h, s["th_l"] if h == "Product" else s["th"]) for h in headers]]

    for title, data in sorted_items:
        share  = (data["revenue"] / grand_rev * 100) if grand_rev else 0
        filled = int(share / 100 * 12)
        bar    = "▓" * filled + "░" * (12 - filled)
        rows.append([
            Paragraph(title[:46],                s["td"]),
            Paragraph(str(data["count"]),        s["td_c"]),
            Paragraph(f"{data['revenue']:,.2f}", s["td_money"]),
            Paragraph(f"{share:5.1f}%  {bar}",  s["td"]),
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
# RECONCILIATION BOX  — dual stream aware
# ──────────────────────────────────────────────────────────────────────────────
def _recon_box(
    payments: list[dict],
    club_payments: list[dict],
    day_str: str | None,
    s: dict,
    missing_sales: list[int] | None = None,
    missing_club:  list[int] | None = None,
) -> Table:
    p_total = sum(float(p["amount"] or 0) for p in payments)
    c_total = sum(float(p["amount"] or 0) for p in club_payments)
    combined = p_total + c_total
    period   = f"for {day_str}" if day_str else "across this date range"

    note_text = (
        f"Combined expected credit {period}: "
        f"{len(payments)} product sale(s) + {len(club_payments)} club subscription(s). "
        "Compare this figure to your bank statement for each channel. "
        "Gap causes: manual transfers bypassing the bot, cross-date approvals, "
        "or duplicate approvals."
    )

    rows = [
        [
            Paragraph("PRODUCT SALES", s["section_h"]),
            Paragraph(f"{p_total:,.2f} ETB", s["big_num"]),
        ],
        [
            Paragraph("CLUB SUBSCRIPTIONS", s["section_h"]),
            Paragraph(f"{c_total:,.2f} ETB", s["big_num_club"]),
        ],
        [
            Paragraph("COMBINED EXPECTED CREDIT", s["total_label"]),
            Paragraph(f"{combined:,.2f} ETB", s["combined_num"]),
        ],
        [
            Paragraph(note_text, s["note"]),
            Paragraph("", s["note"]),
        ],
    ]

    warn_parts = []
    if missing_sales:
        warn_parts.append(
            f"⚠  Sales proofs unavailable for Payment ID(s): "
            f"{', '.join(str(i) for i in missing_sales)}"
        )
    if missing_club:
        warn_parts.append(
            f"⚠  Club proofs unavailable for Club Payment ID(s): "
            f"{', '.join(str(i) for i in missing_club)}"
        )
    if warn_parts:
        rows.append([
            Paragraph("  ·  ".join(warn_parts) +
                      "  These files may have expired from Telegram's servers.",
                      s["warn"]),
            Paragraph("", s["note"]),
        ])

    span_rows = [("SPAN", (0, i), (-1, i)) for i in range(3, len(rows))]

    t = Table(rows, colWidths=[12*cm, 6.4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (-1, -1), C_OFF_WHITE),
        ("BOX",           (0, 0),  (-1, -1), 0.4, C_RULE),
        ("LINEABOVE",     (0, 0),  (-1, 0),  3.5, C_NAVY),
        # Divider line above combined total row
        ("LINEABOVE",     (0, 2),  (-1, 2),  1.5, C_GOLD),
        ("BACKGROUND",    (0, 2),  (-1, 2),  C_GOLD_LIGHT),
        ("TOPPADDING",    (0, 0),  (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 8),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 12),
        ("VALIGN",        (0, 0),  (-1, 2),  "MIDDLE"),
        *span_rows,
    ]))
    return t


# ──────────────────────────────────────────────────────────────────────────────
# PER-DAY PDF
# ──────────────────────────────────────────────────────────────────────────────
def generate_day_pdf(
    day_str:          str,
    payments:         list[dict],
    club_payments:    list[dict],
    folder:           Path,
    sale_shots:       dict[int, Path | None],
    club_shots:       dict[int, Path | None],
) -> Path:
    pdf_path = folder / f"DAILY_SUMMARY_{day_str}.pdf"
    s = _styles()
    story = []

    total_sales = sum(float(p["amount"] or 0) for p in payments)
    total_club  = sum(float(p["amount"] or 0) for p in club_payments)
    total_all   = total_sales + total_club

    # ── Title block ───────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph("DAILY PAYMENT REPORT", s["doc_title"]))
    story.append(Paragraph(
        f"Period: {day_str}  ·  Both Revenue Streams  ·  Grouped by created_at",
        s["doc_subtitle"],
    ))
    story.append(Paragraph(
        f"Filter: APPROVED ONLY  ·  "
        f"Sales: {len(payments)} txn  ·  Club: {len(club_payments)} subs  ·  "
        f"Combined: {total_all:,.2f} ETB  ·  "
        f"Exported: {datetime.now().strftime('%d %B %Y, %H:%M')}",
        s["doc_meta"],
    ))
    story.append(Spacer(1, 0.25*cm))
    story.append(_hr(C_NAVY, 1.5))

    # ── Combined KPIs ─────────────────────────────────────────────────────────
    story += _section(
        "Portfolio Overview",
        "Aggregated metrics across both revenue streams for this day.",
        s,
    )
    story.append(_combined_kpi_block(payments, club_payments))
    story.append(Spacer(1, 0.25*cm))

    # Revenue split bar
    story += _revenue_split_bar(total_sales, total_club)
    story.append(Spacer(1, 0.3*cm))

    # ═════════════════════════════════════════════════════════════════════════
    # STREAM A — PRODUCT SALES
    # ═════════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 0.2*cm))
    story.append(_stream_divider(
        "STREAM A  —  PRODUCT SALES  (payments table)",
        C_NAVY_MID, s,
    ))

    if payments:
        story += _section(
            "Sales Metrics",
            "Revenue and transaction summary for product sales on this day.",
            s, accent=C_NAVY_MID,
        )
        story.append(_sales_kpi_block(payments))
        story += _section(
            "Sales Transaction Register",
            "All approved product sale payments, ordered chronologically. "
            f"Screenshots saved in: {folder.name}/product_sales/",
            s, accent=C_NAVY_MID,
        )
        story.append(_sales_table(payments, s))
        story += _section(
            "Revenue by Product",
            "Sales breakdown across active products for this day.",
            s, accent=C_NAVY_MID,
        )
        story.append(_product_breakdown_table(payments, s))
    else:
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph("No approved product sales on this day.", s["note"]))

    # ═════════════════════════════════════════════════════════════════════════
    # STREAM B — CLUB SUBSCRIPTIONS
    # ═════════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 0.4*cm))
    story.append(_stream_divider(
        "STREAM B  —  CLUB SUBSCRIPTIONS  (club_payments table)",
        C_CLUB_ACCENT, s,
    ))

    if club_payments:
        story += _section(
            "Club Metrics",
            "Revenue and subscription summary for the club on this day.",
            s, accent=C_CLUB_ACCENT,
        )
        story.append(_club_kpi_block(club_payments))
        story += _section(
            "Club Subscription Register",
            "All approved club payment entries, ordered chronologically. "
            f"Screenshots saved in: {folder.name}/club_payments/",
            s, accent=C_CLUB_ACCENT,
        )
        story.append(_club_table(club_payments, s))
    else:
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph("No approved club subscriptions on this day.", s["note"]))

    # ── Reconciliation ────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(_hr(C_RULE))
    story.append(Spacer(1, 0.3*cm))
    missing_sales = [p["payment_id"]      for p in payments      if not sale_shots.get(p["payment_id"])]
    missing_club  = [p["club_payment_id"] for p in club_payments if not club_shots.get(p["club_payment_id"])]
    story.append(_recon_box(payments, club_payments, day_str, s, missing_sales, missing_club))

    _build_doc(pdf_path, story)
    log.info("  Daily PDF saved: %s", pdf_path.name)
    return pdf_path


# ──────────────────────────────────────────────────────────────────────────────
# MASTER AUDIT PDF
# ──────────────────────────────────────────────────────────────────────────────
def generate_master_pdf(
    all_payments:      list[dict],
    all_club_payments: list[dict],
    output_dir:        Path,
    date_from:         date | None,
    date_to:           date | None,
) -> Path:
    pdf_path = output_dir / "MASTER_AUDIT.pdf"
    s = _styles()
    story = []

    total_sales = sum(float(p["amount"] or 0) for p in all_payments)
    total_club  = sum(float(p["amount"] or 0) for p in all_club_payments)
    total_all   = total_sales + total_club
    dr          = f"{date_from or 'All Time'}  →  {date_to or 'Today'}"

    # ── Cover ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph("MASTER REVENUE AUDIT", s["doc_title"]))
    story.append(Paragraph(
        "Consolidated Dual-Stream Payment Intelligence Report",
        s["doc_subtitle"],
    ))
    story.append(Paragraph(
        f"Date range: {dr}  ·  "
        f"Sales records: {len(all_payments)}  ·  "
        f"Club records: {len(all_club_payments)}  ·  "
        f"Exported: {datetime.now().strftime('%d %B %Y, %H:%M')}",
        s["doc_meta"],
    ))
    story.append(Spacer(1, 0.25*cm))
    story.append(_hr(C_NAVY, 2))

    # ── Portfolio KPIs ────────────────────────────────────────────────────────
    story += _section(
        "Portfolio Overview",
        "Aggregated metrics across both revenue streams for the full date range.",
        s,
    )
    story.append(_combined_kpi_block(all_payments, all_club_payments))
    story.append(Spacer(1, 0.25*cm))
    story += _revenue_split_bar(total_sales, total_club)
    story.append(Spacer(1, 0.3*cm))

    # ── Day-by-Day Combined Summary ───────────────────────────────────────────
    by_day_sales: dict[str, list] = defaultdict(list)
    by_day_club:  dict[str, list] = defaultdict(list)

    for p in all_payments:
        day = p["created_at"].strftime("%Y-%m-%d") if p.get("created_at") else "unknown"
        by_day_sales[day].append(p)
    for p in all_club_payments:
        day = p["created_at"].strftime("%Y-%m-%d") if p.get("created_at") else "unknown"
        by_day_club[day].append(p)

    all_days = sorted(set(by_day_sales) | set(by_day_club))

    story += _section(
        "Day-by-Day Combined Summary",
        "Both streams aggregated per day — sales revenue + club revenue + combined running total.",
        s,
    )

    headers = ["Date", "Sales Txn", "Club Subs",
               "Sales Rev (ETB)", "Club Rev (ETB)",
               "Day Total (ETB)", "Running Total (ETB)"]
    rows = [[Paragraph(h, s["th"]) for h in headers]]

    running = 0.0
    for day in all_days:
        dp  = by_day_sales.get(day, [])
        cp  = by_day_club.get(day, [])
        s_r = sum(float(p["amount"] or 0) for p in dp)
        c_r = sum(float(p["amount"] or 0) for p in cp)
        day_total = s_r + c_r
        running  += day_total
        rows.append([
            Paragraph(day,              s["td_c"]),
            Paragraph(str(len(dp)),     s["td_c"]),
            Paragraph(str(len(cp)),     s["td_c"]),
            Paragraph(f"{s_r:,.2f}",   s["td_money"]),
            Paragraph(f"{c_r:,.2f}",   s["td_money_club"]),
            Paragraph(f"{day_total:,.2f}", ParagraphStyle(
                "dt", parent=getSampleStyleSheet()["Normal"],
                fontSize=7.8, textColor=C_NAVY,
                fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=11,
            )),
            Paragraph(f"{running:,.2f}", s["td_r"]),
        ])

    # Grand total row
    rows.append([
        Paragraph("GRAND TOTAL",             s["total_label"]),
        Paragraph(str(len(all_payments)),    s["total_val"]),
        Paragraph(str(len(all_club_payments)), s["total_val_club"]),
        Paragraph(f"{total_sales:,.2f}",     s["total_val"]),
        Paragraph(f"{total_club:,.2f}",      s["total_val_club"]),
        Paragraph(f"{total_all:,.2f}",       s["total_val"]),
        Paragraph("",                        s["td"]),
    ])

    col_w = [2.5*cm, 1.7*cm, 1.7*cm, 3.2*cm, 3.2*cm, 3.2*cm, 3.4*cm]
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
        ("LEFTPADDING",   (0, 0),  (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 5),
        ("ALIGN",         (1, 0),  (2, -1),  "CENTER"),
        ("ALIGN",         (3, 1),  (6, -1),  "RIGHT"),
        # Sales rev column subtle green tint
        ("BACKGROUND",    (3, 1),  (3, -2),  C_SUCCESS_BG),
        # Club rev column subtle gold tint
        ("BACKGROUND",    (4, 1),  (4, -2),  C_GOLD_LIGHT),
    ]))
    story.append(day_t)

    # ── Page break → Stream A deep-dive ──────────────────────────────────────
    story.append(PageBreak())
    story.append(_stream_divider(
        "STREAM A  —  PRODUCT SALES  ·  All-Time Deep Dive",
        C_NAVY_MID, s,
    ))
    story += _section(
        "Product Performance",
        "Revenue contribution and sales volume per product across the full date range.",
        s, accent=C_NAVY_MID,
    )
    story.append(_product_breakdown_table(all_payments, s))

    # ── Page break → Stream B deep-dive ──────────────────────────────────────
    story.append(PageBreak())
    story.append(_stream_divider(
        "STREAM B  —  CLUB SUBSCRIPTIONS  ·  All-Time Deep Dive",
        C_CLUB_ACCENT, s,
    ))
    story += _section(
        "Club Subscription Register",
        "Full list of all approved club payments across the date range.",
        s, accent=C_CLUB_ACCENT,
    )
    story.append(_club_table(all_club_payments, s))

    # ── Reconciliation ────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.6*cm))
    story.append(_hr(C_RULE))
    story.append(Spacer(1, 0.3*cm))
    story.append(_recon_box(all_payments, all_club_payments, None, s))

    _build_doc(pdf_path, story)
    log.info("Master audit PDF saved: %s", pdf_path)
    return pdf_path


# ──────────────────────────────────────────────────────────────────────────────
# DATABASE QUERIES
# ──────────────────────────────────────────────────────────────────────────────
async def fetch_approved_sales(
    conn: asyncpg.Connection,
    date_from: date | None,
    date_to:   date | None,
) -> list[dict]:
    clauses = ["p.status = 'approved'"]
    params: list = []

    if date_from:
        params.append(date_from)
        clauses.append(f"p.created_at::date >= ${len(params)}")
    if date_to:
        params.append(date_to)
        clauses.append(f"p.created_at::date <= ${len(params)}")

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
        WHERE {" AND ".join(clauses)}
        ORDER BY p.created_at ASC
    """
    rows = await conn.fetch(query, *params)
    return [dict(r) for r in rows]


async def fetch_approved_club(
    conn: asyncpg.Connection,
    date_from: date | None,
    date_to:   date | None,
) -> list[dict]:
    clauses = ["cp.status = 'approved'"]
    params: list = []

    if date_from:
        params.append(date_from)
        clauses.append(f"cp.created_at::date >= ${len(params)}")
    if date_to:
        params.append(date_to)
        clauses.append(f"cp.created_at::date <= ${len(params)}")

    query = f"""
        SELECT
            cp.id                                   AS club_payment_id,
            cp.amount,
            cp.proof_file_id,
            cp.created_at,
            cp.processed_at,
            cp.processed_by,
            cp.user_id                              AS telegram_id,
            COALESCE(u.full_name, 'Unknown')        AS full_name,
            COALESCE(u.username,  'N/A')            AS username,
            COALESCE(u.language,  'EN')             AS language,
            -- pull active subscription state for context
            cs.is_active                            AS sub_is_active,
            cs.expires_at                           AS sub_expires_at
        FROM  club_payments   cp
        LEFT  JOIN users      u  ON u.telegram_id = cp.user_id
        LEFT  JOIN club_subscriptions cs ON cs.user_id = cp.user_id
        WHERE {" AND ".join(clauses)}
        ORDER BY cp.created_at ASC
    """
    rows = await conn.fetch(query, *params)
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────────────────────────────────────
# TRANSACTION AUDIT LEDGER & RECONCILIATION ENGINE
# ──────────────────────────────────────────────────────────────────────────────
TOLERANCE_ETB = 5.0  # Differences <= 5.0 ETB (e.g. 399 vs 400) are accepted as match

def _sanitize_str(text: str) -> str:
    """Sanitize strings for PIL font rendering and file paths."""
    if not text:
        return ""
    return re.sub(r"[^\x00-\x7F\xC0-\xFF]+", " ", str(text)).strip()


class TransactionAuditLedger:
    """Persistent ledger tracking every scanned receipt to expose duplicates and mismatches."""

    def __init__(self, json_path: Path, csv_path: Path):
        self.json_path = json_path
        self.csv_path = csv_path
        self.records: list[dict] = []
        self.seen_txns: dict[str, int] = {}  # txn_id -> original payment_id

        if self.json_path.exists():
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    self.records = json.load(f)
                    for r in self.records:
                        tid = r.get("txn_id")
                        if tid and tid != "Not Detected" and tid not in self.seen_txns:
                            self.seen_txns[tid] = r.get("payment_id")
            except Exception as e:
                log.warning("Could not read previous ledger: %s", e)

    def record(
        self,
        payment_id: int,
        stream: str,
        amount_db: float,
        user_id: int,
        full_name: str,
        username: str,
        date_str: str,
        txn_id: str | None,
        provider: str,
        veritas_info: dict,
        filename: str,
    ) -> dict:
        tid = (txn_id or "").strip().upper()
        if not tid or tid in ("NONE", "NOT DETECTED", "UNKNOWN"):
            tid = "Not Detected"

        is_dup = False
        original_pid = None
        if tid != "Not Detected":
            if tid in self.seen_txns and self.seen_txns[tid] != payment_id:
                is_dup = True
                original_pid = self.seen_txns[tid]
            else:
                self.seen_txns[tid] = payment_id

        bank_amount = float(veritas_info.get("amount") or 0.0)
        gap = amount_db - bank_amount if bank_amount > 0 else 0.0
        within_tolerance = abs(gap) <= TOLERANCE_ETB if bank_amount > 0 else True
        is_mismatch = (bank_amount > 0) and not within_tolerance

        is_verified = bool(veritas_info.get("success", False))

        flagged_reason = None
        if is_dup:
            flagged_reason = f"REPLAY DUPLICATE (First seen in PID #{original_pid})"
        elif is_mismatch:
            flagged_reason = f"AMOUNT MISMATCH: DB had {amount_db:.2f} ETB, Bank settled {bank_amount:.2f} ETB (Gap: {gap:+.2f} ETB)"

        entry = {
            "payment_id": payment_id,
            "stream": stream,
            "amount_db": amount_db,
            "user_id": user_id,
            "full_name": full_name,
            "username": username,
            "created_at": date_str,
            "txn_id": tid,
            "provider": provider,
            "bank_payer": veritas_info.get("payer", "Unknown"),
            "bank_receiver": veritas_info.get("receiver", "Hilawe Sema"),
            "bank_amount": bank_amount,
            "bank_status": veritas_info.get("status", "Unknown"),
            "is_verified": is_verified,
            "verification_state": "verified" if is_verified else veritas_info.get("state", "unverified"),
            "amount_difference": gap,
            "within_tolerance": within_tolerance,
            "is_duplicate": is_dup,
            "duplicate_of_pid": original_pid,
            "flagged": bool(is_dup or is_mismatch),
            "flagged_reason": flagged_reason,
            "screenshot_filename": filename,
            "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Replace existing entry for this payment if already logged
        self.records = [r for r in self.records if not (r.get("payment_id") == payment_id and r.get("stream") == stream)]
        self.records.append(entry)
        return entry

    def save(self):
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(self.records, f, indent=2, ensure_ascii=False)

        fieldnames = [
            "payment_id", "stream", "amount_db", "user_id", "full_name", "username",
            "created_at", "txn_id", "provider", "bank_payer", "bank_receiver",
            "bank_amount", "bank_status", "is_verified", "verification_state",
            "amount_difference", "within_tolerance", "is_duplicate", "duplicate_of_pid",
            "flagged", "flagged_reason", "screenshot_filename", "scanned_at"
        ]
        with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.records)


# ──────────────────────────────────────────────────────────────────────────────
# OCR & VERITAS VERIFICATION ENGINE
# ──────────────────────────────────────────────────────────────────────────────
def _extract_receipt_data(img: Image.Image) -> tuple[str | None, str]:
    """Run local OCR and Ethiopian banking pattern extraction."""
    try:
        text = pytesseract.image_to_string(img)
    except Exception as e:
        log.warning("OCR failed: %s", e)
        text = ""

    upper = text.upper()
    provider = "Generic"
    if "COMMERCIAL BANK OF ETHIOPIA" in upper or "CBE" in upper or "FT" in upper:
        provider = "CBE"
    elif "TELEBIRR" in upper or "ETHIO TELECOM" in upper or "DH" in upper:
        provider = "Telebirr"
    elif "ABYSSINIA" in upper or "BOA" in upper:
        provider = "Abyssinia"
    elif "DASHEN" in upper:
        provider = "Dashen"

    patterns = [
        r"\b(FT[A-Z0-9]{8,14})\b",
        r"\b(DH[A-Z0-9]{8,16})\b",
        r"\b(D[A-Z0-9]{9})\b",
        r"(?:TRANSACTION\s*(?:ID|NO|NUMBER)|REFERENCE\s*(?:ID|NO|NUMBER)|REF\s*NO)[\s:#-]+([A-Z0-9]{8,20})",
        r"\b([A-Z0-9]{10,14})\b",
    ]

    ref = None
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            ref = m.group(1).upper()
            break

    if ref:
        if ref.startswith("FT"):
            provider = "CBE"
        elif ref.startswith("DH") or (len(ref) == 10 and ref.startswith("D")):
            provider = "Telebirr"

    return ref, provider


def _parse_veritas_details(res: dict, provider: str) -> dict:
    raw = res.get("raw_response") or {}
    raw_data = raw.get("data") if isinstance(raw, dict) and isinstance(raw.get("data"), dict) else {}

    payer = res.get("payer")
    if not payer or payer in ("Unknown", "None", ""):
        payer = raw.get("payer") or raw_data.get("payerName") or "Unknown Payer"

    receiver = res.get("receiver")
    if not receiver or receiver in ("N/A", "None", ""):
        receiver = raw.get("receiver") or raw_data.get("creditedPartyName") or "Hilawe Sema Melese"

    amount = res.get("amount") or 0.0
    if not amount or amount == 0.0:
        settled = raw_data.get("settledAmount") or raw.get("settledAmount") or raw_data.get("totalPaidAmount")
        if settled:
            m = re.search(r"(\d+(?:\.\d+)?)", str(settled).replace(",", ""))
            if m:
                amount = float(m.group(1))
        elif raw.get("amount"):
            try:
                amount = float(raw.get("amount"))
            except Exception:
                pass

    status_str = "Verified" if res.get("success") else "Unverified"
    if raw_data.get("transactionStatus"):
        status_str = raw_data.get("transactionStatus")

    return {
        "success": res.get("success", False),
        "state": res.get("verification_state", "unverified"),
        "payer": payer,
        "receiver": receiver,
        "amount": amount,
        "status": status_str,
    }


def _stamp_audit_banner(
    img: Image.Image,
    dest_path: Path,
    amount: float,
    pid: int,
    entry: dict,
) -> Path:
    """Stamps high-contrast, large-font audit banner with live AI verification details."""
    w, h = img.size

    # Extra 4-10px font enlargement as requested by user
    font_path_bold = "C:/Windows/Fonts/arialbd.ttf"
    font_path_reg = "C:/Windows/Fonts/arial.ttf"
    if not os.path.exists(font_path_bold):
        font_path_bold = font_path_reg = "C:/Windows/Fonts/segoeuib.ttf"

    try:
        font_title   = ImageFont.truetype(font_path_bold, size=max(26, int(w * 0.046)))
        font_badge   = ImageFont.truetype(font_path_bold, size=max(14, int(w * 0.026)))
        font_details = ImageFont.truetype(font_path_bold, size=max(16, int(w * 0.028)))
        font_sub     = ImageFont.truetype(font_path_reg,  size=max(13, int(w * 0.024)))
    except Exception:
        font_title = font_badge = font_details = font_sub = ImageFont.load_default()

    banner_h = max(200, int(w * 0.25))

    is_dup = entry.get("is_duplicate", False)
    is_verified = entry.get("is_verified", False)
    within_tol = entry.get("within_tolerance", True)
    gap = entry.get("amount_difference", 0.0)

    # Pick header background color
    if is_dup:
        bg_color = (120, 15, 15)  # Crimson red
    elif not within_tol:
        bg_color = (130, 50, 10)  # Orange-red mismatch
    else:
        bg_color = (10, 30, 58)   # Deep Navy

    new_img = Image.new("RGB", (w, h + banner_h), color=bg_color)
    draw = ImageDraw.Draw(new_img)

    # ── LINE 1: Registered DB Amount + Status Badge ────────────────────────────
    line1_left = f"DB REGISTERED: {amount:,.2f} ETB   |   ID: #{pid}"
    title_color = (255, 80, 80) if is_dup else (255, 215, 0)
    draw.text((22, int(banner_h * 0.09)), line1_left, fill=title_color, font=font_title)

    # Status badge pill
    if is_dup:
        badge_text = f"  REPLAY DUPLICATE (PID #{entry.get('duplicate_of_pid')})  "
        badge_bg = (190, 30, 30)
        badge_fg = (255, 255, 255)
    elif not within_tol:
        badge_text = f"  AMOUNT GAP: {gap:+.0f} ETB  "
        badge_bg = (210, 80, 20)
        badge_fg = (255, 255, 255)
    elif is_verified:
        badge_text = f"  AI VERIFIED ({entry.get('provider', 'CBE').upper()})  "
        badge_bg = (22, 138, 62)  # Emerald green
        badge_fg = (255, 255, 255)
    else:
        badge_text = f"  {entry.get('bank_status', 'MANUAL REVIEW')}  "
        badge_bg = (180, 110, 20)
        badge_fg = (255, 255, 255)

    badge_w = draw.textlength(badge_text, font=font_badge) + 14
    badge_x = w - badge_w - 22
    badge_y = int(banner_h * 0.09)
    badge_height = max(26, int(banner_h * 0.15))

    # If narrow screen, badge drops below
    if badge_x < draw.textlength(line1_left, font=font_title) + 30:
        badge_x = 22
        badge_y = int(banner_h * 0.28)
        line2_y = int(banner_h * 0.47)
        line3_y = int(banner_h * 0.65)
        line4_y = int(banner_h * 0.82)
    else:
        line2_y = int(banner_h * 0.36)
        line3_y = int(banner_h * 0.58)
        line4_y = int(banner_h * 0.78)

    draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_height], radius=6, fill=badge_bg)
    draw.text((badge_x + 7, badge_y + 3), badge_text, fill=badge_fg, font=font_badge)

    # ── LINE 2: Bank Payer & Receiver ──────────────────────────────────────────
    clean_payer = _sanitize_str(entry.get("bank_payer", "Unknown Payer"))
    clean_receiver = _sanitize_str(entry.get("bank_receiver", "Hilawe Sema"))
    line2 = f"Payer: {clean_payer}  →  Receiver: {clean_receiver}"
    draw.text((22, line2_y), line2, fill=(255, 255, 255), font=font_details)

    # ── LINE 3: Txn ID, Bank Settled Amount, and Status ────────────────────────
    tid = entry.get("txn_id", "Not Detected")
    b_amt = entry.get("bank_amount", 0.0)
    b_amt_str = f"{b_amt:,.2f} ETB" if b_amt > 0 else "Confirmed"
    status_label = entry.get("bank_status", "Completed")

    line3 = f"Txn: {tid}   ·   Bank Settled: {b_amt_str}   ·   Status: {status_label}"
    line3_color = (120, 230, 160) if is_verified else (255, 190, 90)
    draw.text((22, line3_y), line3, fill=line3_color, font=font_details)

    # ── LINE 4: Telegram User Details & Date ───────────────────────────────────
    clean_tg_name = _sanitize_str(entry.get("full_name", "Unknown"))
    uname = f"@{entry.get('username')}" if entry.get("username") and entry.get("username") != "N/A" else "No username"
    line4 = f"Telegram: {clean_tg_name} ({uname})   ·   {entry.get('created_at', '')}"
    draw.text((22, line4_y), line4, fill=(185, 210, 240), font=font_sub)

    # Divider bar
    border_color = (255, 80, 80) if is_dup else ((210, 80, 20) if not within_tol else (201, 168, 76))
    draw.line([(0, banner_h - 2), (w, banner_h - 2)], fill=border_color, width=3)

    new_img.paste(img, (0, banner_h))
    new_img.save(dest_path, quality=95)
    return dest_path


# ──────────────────────────────────────────────────────────────────────────────
# TELEGRAM FILE DOWNLOAD & AUDIT PIPELINE
# ──────────────────────────────────────────────────────────────────────────────
async def _get_file_url(session: aiohttp.ClientSession, file_id: str) -> str | None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile"
    try:
        async with session.get(
            url,
            params={"file_id": file_id},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            data = await resp.json()
            if data.get("ok") and data["result"].get("file_path"):
                return (
                    f"https://api.telegram.org/file/bot{BOT_TOKEN}/"
                    f"{data['result']['file_path']}"
                )
    except Exception as e:
        log.warning("getFile failed (%s): %s", file_id[:20], e)
    return None


async def process_and_stamp_payment(
    session: aiohttp.ClientSession,
    payment: dict,
    folder: Path,
    stream: str,
    ledger: TransactionAuditLedger,
    sem: asyncio.Semaphore,
) -> Path | None:
    """Downloads, verifies via Veritas/OCR, records in ledger, stamps banner, and saves formatted screenshot."""
    pid = payment.get("payment_id") or payment.get("club_payment_id")
    amount = float(payment.get("amount") or 0.0)
    user_id = payment.get("telegram_id", 0)
    file_id = payment.get("proof_file_id")

    # Name format requested by user: {int(amount)}Br._id_{pid}_user_{user_id}.jpg
    dest = folder / f"{int(amount)}Br._id_{pid}_user_{user_id}.jpg"

    if dest.exists() and any(r.get("payment_id") == pid and r.get("stream") == stream for r in ledger.records):
        log.info("    Already processed: %s", dest.name)
        return dest

    if not file_id:
        log.warning("  Payment #%s — no proof_file_id.", pid)
        ledger.record(
            payment_id=pid,
            stream=stream,
            amount_db=amount,
            user_id=user_id,
            full_name=payment.get("full_name", "Unknown"),
            username=payment.get("username", "N/A"),
            date_str=payment["created_at"].strftime("%Y-%m-%d %H:%M") if payment.get("created_at") else "",
            txn_id=None,
            provider="None",
            veritas_info={"success": False, "state": "no_proof", "status": "No Proof Attached"},
            filename="NO_PROOF",
        )
        return None

    async with sem:
        url = await _get_file_url(session, file_id)
        if not url:
            log.warning("    Could not resolve Telegram URL for payment #%s", pid)
            return None

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                img_bytes = await resp.read()

            raw_img = Image.open(io.BytesIO(img_bytes))
            img = ImageOps.exif_transpose(raw_img).convert("RGB")

            # Extract Txn ID & detect provider
            txn_id, provider = _extract_receipt_data(img)

            # Call Veritas verification
            veritas_info = {"success": False, "state": "unverified", "status": "Not Verified"}
            if txn_id and txn_id != "Not Detected":
                try:
                    veritas_raw = await asyncio.wait_for(verify_external(txn_id, provider), timeout=8.0)
                    veritas_info = _parse_veritas_details(veritas_raw, provider)
                except Exception as ve:
                    log.warning("Veritas call failed for #%s (%s): %s", pid, txn_id, ve)
                    veritas_info = {"success": False, "state": "unavailable", "status": "Bank Lag / Timeout"}

            date_str = payment["created_at"].strftime("%Y-%m-%d %H:%M") if payment.get("created_at") else ""
            entry = ledger.record(
                payment_id=pid,
                stream=stream,
                amount_db=amount,
                user_id=user_id,
                full_name=payment.get("full_name", "Unknown"),
                username=payment.get("username", "N/A"),
                date_str=date_str,
                txn_id=txn_id,
                provider=provider,
                veritas_info=veritas_info,
                filename=dest.name,
            )

            # Stamp banner & save
            _stamp_audit_banner(img, dest, amount, pid, entry)
            log.info("    ✓ Stamped & Saved: %s (Txn: %s | Verified: %s)", dest.name, txn_id, entry["is_verified"])
            return dest

        except Exception as e:
            log.error("    ✗ Failed processing payment #%s: %s", pid, e)
            return None


# ──────────────────────────────────────────────────────────────────────────────
# AUDIT INTELLIGENCE PDF REPORT
# ──────────────────────────────────────────────────────────────────────────────
def generate_ai_audit_pdf(
    ledger: TransactionAuditLedger,
    output_dir: Path,
    sales_range_str: str,
    club_range_str: str,
) -> Path:
    pdf_path = output_dir / "AUDIT_INTELLIGENCE_REPORT.pdf"
    s = _styles()
    story = []

    records = ledger.records
    total_count = len(records)
    verified_count = sum(1 for r in records if r.get("is_verified"))
    verified_pct = (verified_count / total_count * 100) if total_count else 0

    mismatches = [r for r in records if r.get("flagged") and "AMOUNT MISMATCH" in str(r.get("flagged_reason", ""))]
    duplicates = [r for r in records if r.get("is_duplicate")]
    unverified = [r for r in records if not r.get("is_verified") and not r.get("is_duplicate")]

    total_db = sum(float(r.get("amount_db") or 0) for r in records)
    total_bank = sum(float(r.get("bank_amount") or 0) for r in records if r.get("is_verified"))
    variance = total_db - total_bank

    # ── Cover block ───────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph("AUDIT INTELLIGENCE REPORT", s["doc_title"]))
    story.append(Paragraph(
        "AI Verification & Forensic Discrepancy Reconciliation",
        s["doc_subtitle"],
    ))
    story.append(Paragraph(
        f"Sales Scope: {sales_range_str}  ·  Club Scope: {club_range_str}  ·  "
        f"Total Scanned: {total_count} txn  ·  "
        f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}",
        s["doc_meta"],
    ))
    story.append(Spacer(1, 0.25*cm))
    story.append(_hr(C_NAVY, 1.8))

    # ── Executive KPI Cards ───────────────────────────────────────────────────
    story += _section(
        "Executive Audit Metrics",
        "Overall AI pass rates, detected duplicates, and revenue variance.",
        s,
    )

    card_w = (A4[0] - 36*mm - 9*mm) / 4
    val_row = [
        Paragraph(str(total_count), s["kpi_value"]),
        Paragraph(f"{verified_pct:.0f}%", s["kpi_value"]),
        Paragraph(str(len(duplicates)), ParagraphStyle("kred", parent=s["kpi_value"], textColor=C_WARN)),
        Paragraph(str(len(mismatches)), ParagraphStyle("korg", parent=s["kpi_value"], textColor=C_GOLD)),
    ]
    unit_row = [
        Paragraph("TXN", s["kpi_unit"]),
        Paragraph(f"{verified_count} PASS", s["kpi_unit"]),
        Paragraph("REPLAYS", s["kpi_unit"]),
        Paragraph("> 5 ETB", s["kpi_unit"]),
    ]
    label_row = [
        Paragraph("Total Scanned", s["kpi_label"]),
        Paragraph("AI Verified", s["kpi_label"]),
        Paragraph("Duplicate Receipts", s["kpi_label"]),
        Paragraph("Amount Mismatches", s["kpi_label"]),
    ]
    kpi_t = Table([val_row, unit_row, label_row], colWidths=[card_w]*4, rowHeights=[1.3*cm, 0.4*cm, 0.4*cm])
    kpi_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_OFF_WHITE),
        *[("BOX", (i, 0), (i, -1), 0.4, C_RULE) for i in range(4)],
        ("LINEABOVE",     (0, 0), (0, 0), 3.5, C_NAVY),
        ("LINEABOVE",     (1, 0), (1, 0), 3.5, C_SUCCESS),
        ("LINEABOVE",     (2, 0), (2, 0), 3.5, C_WARN),
        ("LINEABOVE",     (3, 0), (3, 0), 3.5, C_GOLD),
        ("TOPPADDING",    (0, 0), (-1, 0),  10),
        ("BOTTOMPADDING", (0, 0), (-1, 0),   2),
        ("TOPPADDING",    (0, 1), (-1, -1),  0),
        ("BOTTOMPADDING", (0, 1), (-1, -1),  8),
        ("LEFTPADDING",   (0, 0), (-1, -1),  6),
        ("RIGHTPADDING",  (0, 0), (-1, -1),  6),
    ]))
    story.append(kpi_t)
    story.append(Spacer(1, 0.3*cm))

    # ── Revenue Variance Box ──────────────────────────────────────────────────
    recon_rows = [
        [
            Paragraph("TOTAL REGISTERED IN DATABASE", s["section_h"]),
            Paragraph(f"{total_db:,.2f} ETB", s["big_num"]),
        ],
        [
            Paragraph("TOTAL BANK SETTLED (CONFIRMED BY AI)", s["section_h"]),
            Paragraph(f"{total_bank:,.2f} ETB", ParagraphStyle("bgreen", parent=s["big_num"], textColor=C_SUCCESS)),
        ],
        [
            Paragraph("REVENUE GAP (UNCONFIRMED / DIFFERENCE)", s["total_label"]),
            Paragraph(f"{variance:,.2f} ETB", ParagraphStyle("bgold", parent=s["combined_num"], textColor=C_WARN if variance > 0 else C_NAVY)),
        ],
        [
            Paragraph("Tolerance Policy: Differences within 5 ETB (e.g. 399 vs 400 Birr) are treated as valid matches. "
                      "Gaps represent either pending bank API timeouts, unverified receipts, or underpayments.", s["note"]),
            Paragraph("", s["note"]),
        ],
    ]
    recon_t = Table(recon_rows, colWidths=[12*cm, 5.4*cm])
    recon_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (-1, -1), C_OFF_WHITE),
        ("BOX",           (0, 0),  (-1, -1), 0.4, C_RULE),
        ("LINEABOVE",     (0, 0),  (-1, 0),  3.5, C_NAVY),
        ("LINEABOVE",     (0, 2),  (-1, 2),  1.5, C_GOLD),
        ("BACKGROUND",    (0, 2),  (-1, 2),  C_GOLD_LIGHT),
        ("TOPPADDING",    (0, 0),  (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 7),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 10),
        ("SPAN",          (0, 3),  (-1, 3)),
    ]))
    story.append(recon_t)
    story.append(Spacer(1, 0.4*cm))

    # ── SECTION 1: FLAGGED & SUSPICIOUS TRANSACTIONS ──────────────────────────
    flagged = [r for r in records if r.get("flagged")]
    story += _section(
        "Flagged & Suspicious Transactions",
        f"Critical audit findings: {len(flagged)} transaction(s) requiring owner review.",
        s, accent=C_WARN,
    )

    if flagged:
        f_headers = ["#", "Stream", "PID", "Telegram User", "DB (ETB)", "Bank (ETB)", "Issue / Flagged Reason"]
        f_rows = [[Paragraph(h, s["th"]) for h in f_headers]]
        for i, r in enumerate(flagged):
            uname = f"@{r['username']}" if r.get("username") and r["username"] != "N/A" else ""
            user_str = f"{r.get('full_name', 'Unknown')[:18]}<br/>{uname}"
            f_rows.append([
                Paragraph(str(i + 1), s["td_c"]),
                Paragraph(r.get("stream", "").replace("_", " ").title()[:10], s["td_c"]),
                Paragraph(str(r.get("payment_id")), s["td_c"]),
                Paragraph(user_str, s["td"]),
                Paragraph(f"{float(r.get('amount_db') or 0):,.2f}", s["td_money"]),
                Paragraph(f"{float(r.get('bank_amount') or 0):,.2f}", s["td_money"]),
                Paragraph(r.get("flagged_reason", "Suspicious Entry"), ParagraphStyle("fr", parent=s["td"], textColor=C_WARN, fontName="Helvetica-Bold")),
            ])
        f_cols = [0.8*cm, 2.2*cm, 1.2*cm, 3.8*cm, 2.2*cm, 2.2*cm, 5.0*cm]
        f_table = Table(f_rows, colWidths=f_cols, repeatRows=1)
        f_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0),  (-1, 0),  C_WARN),
            ("TEXTCOLOR",     (0, 0),  (-1, 0),  C_WHITE),
            ("FONTNAME",      (0, 0),  (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0),  (-1, 0),  7.5),
            ("ROWBACKGROUNDS",(0, 1),  (-1, -1), [C_WHITE, C_WARN_BG]),
            ("GRID",          (0, 0),  (-1, -1), 0.3, C_RULE),
            ("TOPPADDING",    (0, 0),  (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0),  (-1, -1), 4),
        ]))
        story.append(f_table)
    else:
        story.append(Paragraph("✓ Clean Audit: Zero duplicate transactions or large amount mismatches found.", s["note"]))

    story.append(Spacer(1, 0.4*cm))

    # ── SECTION 2: AI VERIFICATION & EXTRACTION FAILURES ──────────────────────
    story += _section(
        "AI Verification & Extraction Log",
        "Records where bank API connection timed out or screenshot OCR was inconclusive.",
        s, accent=C_GOLD,
    )

    if unverified:
        u_headers = ["#", "PID", "Telegram User", "Extracted Txn", "Provider", "Verification State"]
        u_rows = [[Paragraph(h, s["th"]) for h in u_headers]]
        for i, r in enumerate(unverified):
            u_rows.append([
                Paragraph(str(i + 1), s["td_c"]),
                Paragraph(str(r.get("payment_id")), s["td_c"]),
                Paragraph(r.get("full_name", "Unknown")[:20], s["td"]),
                Paragraph(r.get("txn_id", "Not Detected"), s["td_c"]),
                Paragraph(r.get("provider", "Generic"), s["td_c"]),
                Paragraph(r.get("bank_status", "Unverified"), s["td_c"]),
            ])
        u_cols = [0.8*cm, 1.4*cm, 4.5*cm, 3.8*cm, 2.5*cm, 4.4*cm]
        u_table = Table(u_rows, colWidths=u_cols, repeatRows=1)
        u_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0),  (-1, 0),  C_NAVY_MID),
            ("TEXTCOLOR",     (0, 0),  (-1, 0),  C_WHITE),
            ("FONTNAME",      (0, 0),  (-1, 0),  "Helvetica-Bold"),
            ("ROWBACKGROUNDS",(0, 1),  (-1, -1), [C_WHITE, C_ROW_ALT]),
            ("GRID",          (0, 0),  (-1, -1), 0.3, C_RULE),
            ("TOPPADDING",    (0, 0),  (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0),  (-1, -1), 4),
        ]))
        story.append(u_table)
    else:
        story.append(Paragraph("✓ All scanned receipts were successfully verified.", s["note"]))

    story.append(Spacer(1, 0.4*cm))

    # ── SECTION 3: FULL AUDIT REGISTER ────────────────────────────────────────
    story.append(PageBreak())
    story += _section(
        "Full AI Reconciliation Register",
        "Comprehensive ledger of all scanned payments across both revenue streams.",
        s,
    )

    r_headers = ["#", "Str", "PID", "Telegram User", "DB Birr", "Bank Settled", "AI Status", "Txn Ref"]
    r_rows = [[Paragraph(h, s["th"]) for h in r_headers]]
    for i, r in enumerate(records):
        st_short = "Sale" if "sale" in r.get("stream", "").lower() else "Club"
        is_ok = r.get("is_verified", False)
        status_text = "PASS" if is_ok else ("DUP" if r.get("is_duplicate") else "MANUAL")
        status_style = s["td_ok"] if is_ok else (s["td_fail"] if r.get("is_duplicate") else s["td_c"])

        b_settled_str = f"{float(r.get('bank_amount') or 0):,.0f}" if r.get("bank_amount") else "—"

        r_rows.append([
            Paragraph(str(i + 1), s["td_c"]),
            Paragraph(st_short, s["td_c"]),
            Paragraph(str(r.get("payment_id")), s["td_c"]),
            Paragraph(r.get("full_name", "Unknown")[:20], s["td"]),
            Paragraph(f"{float(r.get('amount_db') or 0):,.0f}", s["td_money"]),
            Paragraph(b_settled_str, s["td_money_club"] if st_short == "Club" else s["td_money"]),
            Paragraph(status_text, status_style),
            Paragraph((r.get("txn_id") or "—")[:16], s["td_c"]),
        ])

    r_cols = [0.8*cm, 1.4*cm, 1.2*cm, 4.0*cm, 2.2*cm, 2.2*cm, 1.8*cm, 3.8*cm]
    r_table = Table(r_rows, colWidths=r_cols, repeatRows=1, splitByRow=True)
    r_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (-1, 0),  C_NAVY),
        ("TEXTCOLOR",     (0, 0),  (-1, 0),  C_WHITE),
        ("FONTNAME",      (0, 0),  (-1, 0),  "Helvetica-Bold"),
        ("ROWBACKGROUNDS",(0, 1),  (-1, -1), [C_WHITE, C_ROW_ALT]),
        ("GRID",          (0, 0),  (-1, -1), 0.3, C_RULE),
        ("TOPPADDING",    (0, 0),  (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 3.5),
    ]))
    story.append(r_table)

    _build_doc(pdf_path, story)
    log.info("Audit Intelligence PDF saved: %s", pdf_path)
    return pdf_path


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
async def main(
    date_from: date | None,
    date_to: date | None,
    stream: str,
    sales_from: date | None = None,
    sales_to: date | None = None,
    club_from: date | None = None,
    club_to: date | None = None,
):
    if not DATABASE_URL:
        log.error("DATABASE_URL not set in .env"); sys.exit(1)
    if not BOT_TOKEN:
        log.error("BOT_TOKEN not set in .env"); sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Determine effective date ranges
    s_from = sales_from or date_from
    s_to   = sales_to   or date_to
    c_from = club_from  or date_from
    c_to   = club_to    or date_to

    log.info("Connecting to database …")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        all_payments      = []
        all_club_payments = []

        if stream in ("both", "sales"):
            all_payments = await fetch_approved_sales(conn, s_from, s_to)
            log.info("  Stream A (product sales)  : %d records (%s -> %s)", len(all_payments), s_from or "All", s_to or "Now")

        if stream in ("both", "club"):
            all_club_payments = await fetch_approved_club(conn, c_from, c_to)
            log.info("  Stream B (club payments)  : %d records (%s -> %s)", len(all_club_payments), c_from or "All", c_to or "Now")
    finally:
        await conn.close()

    if not all_payments and not all_club_payments:
        log.warning("No approved payments found in either stream. Nothing to export.")
        return

    # Initialize ledger in output directory
    ledger = TransactionAuditLedger(
        json_path=OUTPUT_DIR / "scanned_transactions.json",
        csv_path=OUTPUT_DIR / "scanned_transactions.csv",
    )

    # Group by day
    by_day_sales: dict[str, list] = defaultdict(list)
    by_day_club:  dict[str, list] = defaultdict(list)

    for p in all_payments:
        day = p["created_at"].strftime("%Y-%m-%d") if p.get("created_at") else "unknown"
        by_day_sales[day].append(p)
    for p in all_club_payments:
        day = p["created_at"].strftime("%Y-%m-%d") if p.get("created_at") else "unknown"
        by_day_club[day].append(p)

    all_days = sorted(set(by_day_sales) | set(by_day_club))
    log.info("Days to process: %s", ", ".join(all_days))

    # Concurrency semaphore for safe, fast Telegram & Veritas processing
    sem = asyncio.Semaphore(4)

    # ── Per-day processing ───────────────────────────────────────────────────
    async with aiohttp.ClientSession() as session:
        for day in all_days:
            day_sales = by_day_sales.get(day, [])
            day_club  = by_day_club.get(day, [])

            day_folder   = OUTPUT_DIR / day
            sales_folder = day_folder / "product_sales"
            club_folder  = day_folder / "club_payments"

            day_folder.mkdir(parents=True, exist_ok=True)
            if day_sales: sales_folder.mkdir(parents=True, exist_ok=True)
            if day_club:  club_folder.mkdir(parents=True, exist_ok=True)

            log.info("── %s  (sales: %d  |  club: %d) ──", day, len(day_sales), len(day_club))

            # Download & verify sale screenshots
            sale_tasks = [
                process_and_stamp_payment(session, p, sales_folder, "product_sales", ledger, sem)
                for p in day_sales
            ]
            sale_results = await asyncio.gather(*sale_tasks)
            sale_shots = {p["payment_id"]: res for p, res in zip(day_sales, sale_results)}

            # Download & verify club screenshots
            club_tasks = [
                process_and_stamp_payment(session, p, club_folder, "club_payments", ledger, sem)
                for p in day_club
            ]
            club_results = await asyncio.gather(*club_tasks)
            club_shots = {p["club_payment_id"]: res for p, res in zip(day_club, club_results)}

            generate_day_pdf(day, day_sales, day_club, day_folder, sale_shots, club_shots)

    # Save finalized ledger
    ledger.save()

    # ── Master audit PDF ─────────────────────────────────────────────────────
    log.info("Generating master audit PDF …")
    generate_master_pdf(all_payments, all_club_payments, OUTPUT_DIR, s_from, s_to)

    # ── AI Audit Intelligence PDF ────────────────────────────────────────────
    log.info("Generating AI audit intelligence PDF …")
    sales_range_label = f"{s_from or 'All'} to {s_to or 'Now'}"
    club_range_label  = f"{c_from or 'All'} to {c_to or 'Now'}"
    generate_ai_audit_pdf(ledger, OUTPUT_DIR, sales_range_label, club_range_label)

    # ── Summary banner ────────────────────────────────────────────────────────
    total_sales = sum(float(p["amount"] or 0) for p in all_payments)
    total_club  = sum(float(p["amount"] or 0) for p in all_club_payments)
    total_all   = total_sales + total_club

    verified_n = sum(1 for r in ledger.records if r.get("is_verified"))
    flagged_n  = sum(1 for r in ledger.records if r.get("flagged"))
    dup_n      = sum(1 for r in ledger.records if r.get("is_duplicate"))

    print("\n" + "=" * 66)
    print("  DIGITAL REVENUE -- FORENSIC DUAL-STREAM AUDIT COMPLETE")
    print("=" * 66)
    print(f"  Output folder           : {OUTPUT_DIR.resolve()}")
    print(f"  Sales Range             : {sales_range_label}")
    print(f"  Club Range              : {club_range_label}")
    print(f"  Total Scanned           : {len(ledger.records)}")
    if ledger.records:
        print(f"  AI Verified (Pass)      : {verified_n} / {len(ledger.records)} ({verified_n/len(ledger.records)*100:.1f}%)")
    print(f"  Replay Duplicates       : {dup_n}")
    print(f"  Flagged Transactions    : {flagged_n}")
    print(f"  -- Financial Summary -----------------------------------")
    print(f"  Product Sales Rev (DB)  : {total_sales:>14,.2f} ETB ({len(all_payments)} txn)")
    print(f"  Club Subscription (DB)  : {total_club:>14,.2f} ETB ({len(all_club_payments)} subs)")
    print(f"  Total Registered Rev    : {total_all:>14,.2f} ETB")
    print("=" * 66)
    print("  AUDIT ARTIFACTS CREATED:")
    print("  [OK] MASTER_AUDIT.pdf               - Consolidated financial ledger")
    print("  [OK] AUDIT_INTELLIGENCE_REPORT.pdf  - Forensic AI verification & discrepancy report")
    print("  [OK] scanned_transactions.csv       - Full Excel-ready audit ledger")
    print("  [OK] scanned_transactions.json      - Machine-readable transaction state")
    print("=" * 66 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Digital Revenue — Export and verify approved payments with AI forensics.",
    )
    parser.add_argument(
        "--from", dest="date_from", metavar="YYYY-MM-DD",
        help="Default start date for both streams",
    )
    parser.add_argument(
        "--to", dest="date_to", metavar="YYYY-MM-DD",
        help="Default end date for both streams",
    )
    parser.add_argument(
        "--sales-from", dest="sales_from", metavar="YYYY-MM-DD",
        help="Start date for product sales stream",
    )
    parser.add_argument(
        "--sales-to", dest="sales_to", metavar="YYYY-MM-DD",
        help="End date for product sales stream",
    )
    parser.add_argument(
        "--club-from", dest="club_from", metavar="YYYY-MM-DD",
        help="Start date for club payments stream",
    )
    parser.add_argument(
        "--club-to", dest="club_to", metavar="YYYY-MM-DD",
        help="End date for club payments stream",
    )
    parser.add_argument(
        "--stream", dest="stream", choices=["both", "sales", "club"],
        default="both",
        help="Which revenue stream to export (default: both)",
    )
    args = parser.parse_args()

    def _d(v): return datetime.strptime(v, "%Y-%m-%d").date() if v else None

    asyncio.run(main(
        date_from=_d(args.date_from),
        date_to=_d(args.date_to),
        stream=args.stream,
        sales_from=_d(args.sales_from),
        sales_to=_d(args.sales_to),
        club_from=_d(args.club_from),
        club_to=_d(args.club_to),
    ))
