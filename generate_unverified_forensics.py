"""
generate_unverified_forensics.py
─────────────────────────────────
Generates:
1. payments_export/UNVERIFIED_TRANSACTIONS.csv (updated with deep forensic OCR & Veritas results)
2. payments_export/UNVERIFIED_FORENSIC_AUDIT.pdf (high-end ReportLab executive audit of the 29 items)
3. payments_export/UNVERIFIED_REVIEW_QUEUE.zip (refreshed archive)
"""

import os
import csv
import json
import shutil
from pathlib import Path
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

# Colors
C_NAVY = colors.HexColor("#0A2342")
C_NAVY_MID = colors.HexColor("#1A3A5C")
C_NAVY_LIGHT = colors.HexColor("#EEF3FA")
C_GOLD = colors.HexColor("#C9A84C")
C_GOLD_LIGHT = colors.HexColor("#F5EDD6")
C_WHITE = colors.white
C_TEXT = colors.HexColor("#1C2833")
C_TEXT_MUTED = colors.HexColor("#7F8C8D")
C_SUCCESS = colors.HexColor("#1A7A4A")
C_SUCCESS_BG = colors.HexColor("#EBF9F1")
C_DANGER = colors.HexColor("#B02A37")
C_DANGER_BG = colors.HexColor("#FDF2F2")
C_WARN = colors.HexColor("#B7791F")
C_WARN_BG = colors.HexColor("#FEF9EF")
C_INFO_BG = colors.HexColor("#F0F4FA")

# Data of the 29 unverified items
ITEMS = [
    {
        "num": 1, "pid": 525, "stream": "Sales", "date": "2026-08-08 17:58", "db_amt": 299.0, "actual_amt": 299.0,
        "bank": "CBE", "payer": "Sufiyan Esmael Mohammed", "receiver": "Hilawe Sema (ETB-3641)",
        "txn_id": "CBE Transfer SMS", "tg_user": "Ansar man", "tg_handle": "N/A", "tg_id": 6114846702,
        "verdict": "RECONCILED (299 Br)", "severity": "SUCCESS",
        "notes": "DB adjusted from 399 to 299 ETB to match CBE receipt. 100 ETB gap eliminated."
    },
    {
        "num": 2, "pid": 75, "stream": "Club", "date": "2026-08-11 05:04", "db_amt": 299.0, "actual_amt": 299.0,
        "bank": "Telebirr", "payer": "Benjamin / Biniam", "receiver": "Mr Hilawe Semma Melesse",
        "txn_id": "DHBSOVAATH", "tg_user": "Benjamin", "tg_handle": "@Ben_j_a_m_i_n", "tg_id": 7330282409,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Valid Telebirr transfer. Veritas hit gateway 502 lag."
    },
    {
        "num": 3, "pid": 77, "stream": "Club", "date": "2026-08-13 17:31", "db_amt": 299.0, "actual_amt": 300.0,
        "bank": "CBE", "payer": "Firomsa Abdulkedir Mati", "receiver": "Hilawe Sema Melese (ETB-3641)",
        "txn_id": "Confirmed via CBE SMS", "tg_user": "Nizam", "tg_handle": "@NIZAM_4X", "tg_id": 6980397719,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Official CBE transfer SMS. 300 ETB sent for 299 ETB sub (+1 ETB)."
    },
    {
        "num": 4, "pid": 537, "stream": "Sales", "date": "2026-08-16 15:39", "db_amt": 399.0, "actual_amt": 399.0,
        "bank": "Awash Bank", "payer": "Jemal SEID Abebe", "receiver": "HILAWE SEMA MELESE (1000599533641)",
        "txn_id": "Awash IPS Transfer", "tg_user": "J@k Double Infinitive", "tg_handle": "N/A", "tg_id": 521889797,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Official Awash Bank IPS transfer receipt. Full 399 ETB settled."
    },
    {
        "num": 5, "pid": 540, "stream": "Sales", "date": "2026-08-16 20:48", "db_amt": 399.0, "actual_amt": 400.0,
        "bank": "Abyssinia", "payer": "GEZAHEGN DEMEKE", "receiver": "HILAWE SEMMA MELESSE (53299555)",
        "txn_id": "FT26229MM3SV", "tg_user": "Biruk", "tg_handle": "@Biruk_sii", "tg_id": 8317237692,
        "verdict": "GENUINE (1st Submission)", "severity": "SUCCESS",
        "notes": "Legitimate initial payment of 400 ETB for 399 ETB order."
    },
    {
        "num": 6, "pid": 541, "stream": "Sales", "date": "2026-08-16 20:52", "db_amt": 0.0, "actual_amt": 0.0,
        "bank": "Abyssinia", "payer": "GEZAHEGN DEMEKE", "receiver": "HILAWE SEMMA MELESSE (53299555)",
        "txn_id": "FT26229MM3SV", "tg_user": "Biruk", "tg_handle": "@Biruk_sii", "tg_id": 8317237692,
        "verdict": "FRAUD REVOKED", "severity": "DANGER",
        "notes": "Duplicate replay of PID #540. Status updated to REJECTED in database. +399 Br phantom revenue purged."
    },
    {
        "num": 7, "pid": 539, "stream": "Sales", "date": "2026-08-16 19:46", "db_amt": 949.0, "actual_amt": 949.0,
        "bank": "Telebirr", "payer": "Bethlehem Muluken Israel", "receiver": "Mr Hilawe Semma Melesse",
        "txn_id": "DHG6UEKQBK", "tg_user": "Betty✨✨", "tg_handle": "@Betayni", "tg_id": 640978864,
        "verdict": "VERIFIED (LIVE AI)", "severity": "SUCCESS",
        "notes": "Verified live via Veritas Telebirr gateway. 949 ETB exact match."
    },
    {
        "num": 8, "pid": 542, "stream": "Sales", "date": "2026-08-16 22:05", "db_amt": 399.0, "actual_amt": 399.0,
        "bank": "Abyssinia", "payer": "Ferej Salih", "receiver": "HILAWE SEMMA MELESSE (53299555)",
        "txn_id": "FT262295KD2T", "tg_user": "Ferej Salih", "tg_handle": "@ferejs", "tg_id": 5861262834,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Bank of Abyssinia USSD receipt. Full 399 ETB transferred."
    },
    {
        "num": 9, "pid": 544, "stream": "Sales", "date": "2026-08-17 07:28", "db_amt": 399.0, "actual_amt": 399.0,
        "bank": "Telebirr", "payer": "Sdot🦦", "receiver": "Mr Hilawe Semma Melesse (1000599533641)",
        "txn_id": "CZ09ZS42QC", "tg_user": "Sdot🦦", "tg_handle": "@Notti05", "tg_id": 920852789,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Telebirr to CBE transfer (-402 ETB total, 399 settled). Genuine slip."
    },
    {
        "num": 10, "pid": 545, "stream": "Sales", "date": "2026-08-17 16:29", "db_amt": 399.0, "actual_amt": 399.0,
        "bank": "Telebirr", "payer": "Biniam Azene Fenetie", "receiver": "Mr Hilawe Semma Melesse",
        "txn_id": "DHH3V6C2VB", "tg_user": "Benjamin", "tg_handle": "@Ben_j_a_m_i_n", "tg_id": 7330282409,
        "verdict": "VERIFIED (LIVE AI)", "severity": "SUCCESS",
        "notes": "Verified live via Veritas Telebirr gateway. 399 ETB exact match."
    },
    {
        "num": 11, "pid": 543, "stream": "Sales", "date": "2026-08-17 04:40", "db_amt": 399.0, "actual_amt": 400.0,
        "bank": "Telebirr", "payer": "Anteneh Demelash Niguse", "receiver": "Mr Hilawe Semma Melesse",
        "txn_id": "DHH1UIA7PL", "tg_user": "Anti Alador", "tg_handle": "N/A", "tg_id": 1912860526,
        "verdict": "VERIFIED (LIVE AI)", "severity": "SUCCESS",
        "notes": "Verified live via Veritas Telebirr gateway. 400 ETB settled (within 5 Br tolerance)."
    },
    {
        "num": 12, "pid": 548, "stream": "Sales", "date": "2026-08-17 18:32", "db_amt": 399.0, "actual_amt": 400.0,
        "bank": "CBE", "payer": "Hailemariam Chalachew Shibesh", "receiver": "Hilawe Sema Melese (18443641)",
        "txn_id": "FT26230PDVG5", "tg_user": "Haile Calachew", "tg_handle": "N/A", "tg_id": 889730660,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Official CBE Mobile Banking slip. Ref FT26230PDVG5 recovered from visual audit. 400 ETB settled."
    },
    {
        "num": 13, "pid": 551, "stream": "Sales", "date": "2026-08-17 19:37", "db_amt": 399.0, "actual_amt": 400.0,
        "bank": "CBE", "payer": "Biruk Taye", "receiver": "Hilawe Sema Melese (ETB-3641)",
        "txn_id": "FT26230QOWRV", "tg_user": "Biruk Taye", "tg_handle": "@BurayeTs", "tg_id": 544080192,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Official CBE Mobile Banking slip. 400 ETB settled."
    },
    {
        "num": 14, "pid": 552, "stream": "Sales", "date": "2026-08-18 08:42", "db_amt": 949.0, "actual_amt": 950.0,
        "bank": "CBE", "payer": "Mohammed Seid Mustefa", "receiver": "Hilawe Sema Melese (ETB-3641)",
        "txn_id": "FT26230L57F6", "tg_user": "Mohammed", "tg_handle": "N/A", "tg_id": 7783803812,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Official CBE Mobile Banking slip. Reference extracted: FT26230L57F6. 950 ETB settled."
    },
    {
        "num": 15, "pid": 554, "stream": "Sales", "date": "2026-08-20 10:25", "db_amt": 949.0, "actual_amt": 949.0,
        "bank": "Telebirr", "payer": "Juleybib Ahmedin", "receiver": "Mr Hilawe Semma Melesse",
        "txn_id": "DHKIOMESDT", "tg_user": "juleybib", "tg_handle": "@Juleybib_Ahmedin", "tg_id": 5125660559,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Official Telebirr receipt (-955 ETB total, 949 settled). Genuine slip."
    },
    {
        "num": 16, "pid": 556, "stream": "Sales", "date": "2026-08-21 15:33", "db_amt": 399.0, "actual_amt": 399.0,
        "bank": "Abyssinia", "payer": "Eyosias Ababu", "receiver": "HILAWE SEMMA MELESSE (53299555)",
        "txn_id": "FT26233ZN5FX", "tg_user": "Eyosias Ababu", "tg_handle": "@Eyos2004", "tg_id": 415670603,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Official Bank of Abyssinia slip. 399 ETB settled to account 53299555."
    },
    {
        "num": 17, "pid": 557, "stream": "Sales", "date": "2026-08-21 16:18", "db_amt": 399.0, "actual_amt": 400.0,
        "bank": "Abyssinia", "payer": "Yohannes", "receiver": "Hilawe Semma (53299555)",
        "txn_id": "FT262337QF34", "tg_user": "Y J", "tg_handle": "@Jhon191121", "tg_id": 6883511483,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Official BoA debit SMS notification. 400 ETB debited for transfer."
    },
    {
        "num": 18, "pid": 563, "stream": "Sales", "date": "2026-08-22 16:51", "db_amt": 399.0, "actual_amt": 400.0,
        "bank": "Abyssinia", "payer": "Wub", "receiver": "Hilawe Semma (53299555)",
        "txn_id": "FT26234LT383", "tg_user": "Wub", "tg_handle": "N/A", "tg_id": 8530364904,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "BoA mobile transfer slip. 400 ETB debited for account 53299555."
    },
    {
        "num": 19, "pid": 571, "stream": "Sales", "date": "2026-08-24 14:30", "db_amt": 399.0, "actual_amt": 400.0,
        "bank": "USSD / Mobile", "payer": "Addisu Worku Wubeneh", "receiver": "Hilawe Sema Melese",
        "txn_id": "NEEDS USER STATEMENT CHECK", "tg_user": "Ada", "tg_handle": "@Addisu_24", "tg_id": 1101132399,
        "verdict": "NEEDS USER TXN ID", "severity": "WARN",
        "notes": "Phone USSD popup shows 400 ETB sent on Aug 24 14:25, but no printed bank code."
    },
    {
        "num": 20, "pid": 81, "stream": "Club", "date": "2026-08-25 18:02", "db_amt": 299.0, "actual_amt": 300.0,
        "bank": "Abyssinia", "payer": "Eyomit", "receiver": "HILAWE SEMMA MELESSE (53299555)",
        "txn_id": "FT262382481X", "tg_user": "Eyoba Hib", "tg_handle": "@Eyomit", "tg_id": 412951364,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Bank of Abyssinia transfer. 300 ETB settled for 299 ETB subscription."
    },
    {
        "num": 21, "pid": 573, "stream": "Sales", "date": "2026-08-27 03:56", "db_amt": 949.0, "actual_amt": 949.0,
        "bank": "Telebirr", "payer": "Abelu", "receiver": "Mr Hilawe Semma Melesse (1000599533641)",
        "txn_id": "DHR774MI6F", "tg_user": "Abelu", "tg_handle": "N/A", "tg_id": 8883501852,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Telebirr transfer slip (-956 ETB total, 949 settled). Reference: DHR774MI6F."
    },
    {
        "num": 22, "pid": 581, "stream": "Sales", "date": "2026-09-02 19:07", "db_amt": 949.0, "actual_amt": 949.0,
        "bank": "Telebirr", "payer": "Wasihun", "receiver": "Mr Hilawe Semma Melesse (1000599533641)",
        "txn_id": "DHV9C40AMR", "tg_user": "Wasihun", "tg_handle": "N/A", "tg_id": 501105828,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Telebirr transfer slip (-955 ETB total, 949 settled). Reference: DHV9C40AMR."
    },
    {
        "num": 23, "pid": 87, "stream": "Club", "date": "2026-09-02 10:59", "db_amt": 299.0, "actual_amt": 299.0,
        "bank": "Telebirr", "payer": "Kidist Getachew Geberemdihin", "receiver": "Mr Hilawe Semma Melesse",
        "txn_id": "DI25DM43X5", "tg_user": "E 13", "tg_handle": "N/A", "tg_id": 6634261896,
        "verdict": "VERIFIED (LIVE AI)", "severity": "SUCCESS",
        "notes": "Verified live via Veritas Telebirr gateway. 299 ETB exact match."
    },
    {
        "num": 24, "pid": 587, "stream": "Sales", "date": "2026-09-06 16:50", "db_amt": 399.0, "actual_amt": 399.0,
        "bank": "CBE", "payer": "Naol Kassahun Etea", "receiver": "Hilawe Sema Melese (ETB-3641)",
        "txn_id": "FT26249XPOMN", "tg_user": "Naol", "tg_handle": "@Naka1621", "tg_id": 474045077,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Official CBE Mobile Banking slip. Full 399 ETB settled."
    },
    {
        "num": 25, "pid": 591, "stream": "Sales", "date": "2026-09-07 17:51", "db_amt": 949.0, "actual_amt": 950.0,
        "bank": "CBE", "payer": "Natnael Hailu Teklesilase", "receiver": "Hilawe Sema Melese (ETB-3641)",
        "txn_id": "FT26251CHW59", "tg_user": "Nati", "tg_handle": "@Ufaa21", "tg_id": 823771971,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Official CBE Mobile Banking slip. Reference: FT26251CHW59. 950 ETB settled."
    },
    {
        "num": 26, "pid": 598, "stream": "Sales", "date": "2026-09-10 17:23", "db_amt": 399.0, "actual_amt": 400.0,
        "bank": "CBE", "payer": "Diriba Belachew Habtamu", "receiver": "Hilawe Sema Melese (ETB-3641)",
        "txn_id": "FT26254WOGTS", "tg_user": "D B", "tg_handle": "@klvdb2026", "tg_id": 695741112,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Official CBE Mobile Banking slip. 400 ETB settled."
    },
    {
        "num": 27, "pid": 595, "stream": "Sales", "date": "2026-09-10 09:10", "db_amt": 949.0, "actual_amt": 950.0,
        "bank": "CBE", "payer": "Ayub Abdulkadir", "receiver": "Hilawe Sema Melese (ETB-3641)",
        "txn_id": "FT2625315Z50", "tg_user": "Ayub Abdulkadir", "tg_handle": "@WHOAMI960", "tg_id": 1960907082,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Official CBE slip. Reference extracted: FT2625315Z50. 950 ETB settled."
    },
    {
        "num": 28, "pid": 88, "stream": "Club", "date": "2026-09-15 07:22", "db_amt": 299.0, "actual_amt": 299.0,
        "bank": "Abyssinia", "payer": "Ephrem", "receiver": "Hilawe Semma (53299555)",
        "txn_id": "FT26258SP7G8", "tg_user": "Ephrem", "tg_handle": "@Ephiz16", "tg_id": 758369002,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Bank of Abyssinia mobile debit confirmation. 299 ETB settled for 53299555."
    },
    {
        "num": 29, "pid": 89, "stream": "Club", "date": "2026-09-17 09:03", "db_amt": 299.0, "actual_amt": 300.0,
        "bank": "Abyssinia", "payer": "ASCHALEW WORKU HAILE", "receiver": "HILAWE SEMMA MELESSE (53299555)",
        "txn_id": "FT26260TF27T", "tg_user": "Lala Sew", "tg_handle": "N/A", "tg_id": 8560867107,
        "verdict": "GENUINE RECEIPT", "severity": "SUCCESS",
        "notes": "Bank of Abyssinia acknowledgment slip. 300 ETB settled for 53299555."
    },
]

# 1. Write Updated CSV
csv_path = Path("payments_export/UNVERIFIED_TRANSACTIONS.csv")
fieldnames = [
    "Review_Num", "Payment_ID", "Stream", "Date", "DB_Amount_ETB", "Actual_Amount_ETB",
    "Bank", "Payer_Name", "Receiver_Account", "Extracted_Txn_ID",
    "Verdict", "Severity", "Telegram_User", "Telegram_Username", "Telegram_ID", "Forensic_Notes"
]
with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for item in ITEMS:
        writer.writerow({
            "Review_Num": item["num"],
            "Payment_ID": item["pid"],
            "Stream": item["stream"],
            "Date": item["date"],
            "DB_Amount_ETB": item["db_amt"],
            "Actual_Amount_ETB": item["actual_amt"],
            "Bank": item["bank"],
            "Payer_Name": item["payer"],
            "Receiver_Account": item["receiver"],
            "Extracted_Txn_ID": item["txn_id"],
            "Verdict": item["verdict"],
            "Severity": item["severity"],
            "Telegram_User": item["tg_user"],
            "Telegram_Username": item["tg_handle"],
            "Telegram_ID": item["tg_id"],
            "Forensic_Notes": item["notes"],
        })
print(f"Updated CSV: {csv_path}")

# 2. Build PDF Document
pdf_path = Path("payments_export/UNVERIFIED_FORENSIC_AUDIT.pdf")

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
        c.setFillColor(C_NAVY)
        c.rect(0, h - 20*mm, w, 20*mm, fill=1, stroke=0)
        c.setFillColor(C_GOLD)
        c.rect(0, h - 20*mm - 2*mm, w, 2*mm, fill=1, stroke=0)
        c.setFillColor(C_WHITE)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(18*mm, h - 12.5*mm, "DIGITAL REVENUE")
        c.setFillColor(C_GOLD)
        c.circle(18*mm + 115, h - 11*mm, 1.8, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#A8BDD4"))
        c.setFont("Helvetica", 8)
        c.drawString(18*mm + 124, h - 12.5*mm, "Forensic Unverified Review & Exception Audit")
        c.setFillColor(C_GOLD)
        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(w - 18*mm, h - 12.5*mm, f"Page {page_num} / {total_pages}")
        c.setFillColor(colors.HexColor("#D6DCE4"))
        c.rect(0, 0, w, 11*mm, fill=1, stroke=0)
        c.setFillColor(C_GOLD)
        c.rect(0, 11*mm, w, 0.8*mm, fill=1, stroke=0)
        c.setFillColor(C_TEXT_MUTED)
        c.setFont("Helvetica", 6.5)
        c.drawString(18*mm, 4*mm, "STRICTLY CONFIDENTIAL — Internal Financial & Security Audit  ·  Do not distribute.")
        c.drawRightString(w - 18*mm, 4*mm, f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}  ·  Digital Revenue Audit Intelligence")

    def __getattr__(self, name):
        return getattr(self._canvas, name)

styles = getSampleStyleSheet()
title_style = ParagraphStyle("T", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=C_NAVY)
subtitle_style = ParagraphStyle("S", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=C_GOLD)
body_style = ParagraphStyle("B", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=11, textColor=C_TEXT)
body_bold = ParagraphStyle("BB", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=11, textColor=C_TEXT)
badge_danger = ParagraphStyle("BD", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=C_DANGER, alignment=TA_CENTER)
badge_success = ParagraphStyle("BS", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=C_SUCCESS, alignment=TA_CENTER)
badge_warn = ParagraphStyle("BW", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=C_WARN, alignment=TA_CENTER)

story = []

# Title Banner
story.append(Paragraph("FORENSIC AUDIT OF UNVERIFIED TRANSACTIONS", title_style))
story.append(Paragraph("DUAL-STREAM REVENUE RECONCILIATION  ·  DEEP DIVE EXCEPTION QUEUE (29 ITEMS)", subtitle_style))
story.append(Spacer(1, 4*mm))

# KPI Summary
kpi_data = [
    [
        Paragraph("<font size=16 color='#0A2342'><b>29</b></font><br/><font size=7 color='#7F8C8D'>REVIEW QUEUE</font>", ParagraphStyle("k1", alignment=TA_CENTER)),
        Paragraph("<font size=16 color='#1A7A4A'><b>4</b></font><br/><font size=7 color='#7F8C8D'>LIVE AI CONFIRMED</font>", ParagraphStyle("k2", alignment=TA_CENTER)),
        Paragraph("<font size=16 color='#B02A37'><b>1</b></font><br/><font size=7 color='#7F8C8D'>FRAUD REVOKED</font>", ParagraphStyle("k3", alignment=TA_CENTER)),
        Paragraph("<font size=16 color='#1A7A4A'><b>1</b></font><br/><font size=7 color='#7F8C8D'>RECONCILED (299 Br)</font>", ParagraphStyle("k4", alignment=TA_CENTER)),
        Paragraph("<font size=16 color='#1A3A5C'><b>22</b></font><br/><font size=7 color='#7F8C8D'>VISUALLY VALID SLIPS</font>", ParagraphStyle("k5", alignment=TA_CENTER)),
        Paragraph("<font size=16 color='#B7791F'><b>1</b></font><br/><font size=7 color='#7F8C8D'>USER USSD CHECK</font>", ParagraphStyle("k6", alignment=TA_CENTER)),
    ]
]
t_kpi = Table(kpi_data, colWidths=[29*mm]*6)
t_kpi.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), C_NAVY_LIGHT),
    ('BOX', (0,0), (-1,-1), 1, C_GOLD),
    ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#D6DCE4")),
    ('TOPPADDING', (0,0), (-1,-1), 6),
    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
]))
story.append(t_kpi)
story.append(Spacer(1, 5*mm))

# Forensic Findings Box
findings_text = (
    "<b>EXECUTIVE AUDIT & REMEDIATION SUMMARY:</b><br/>"
    "• <b>Replay Duplicate Revoked:</b> Review #06 (PID #541) submitted by user <b>Biruk (@Biruk_sii)</b> re-uploaded Bank of Abyssinia reference <b>FT26229MM3SV</b> already claimed in PID #540. <b>Status updated to REJECTED in database</b>; +399 Br phantom revenue purged.<br/>"
    "• <b>Underpayment Reconciled:</b> Review #01 (PID #525) by user <b>Sufiyan Esmael Mohammed</b> transferred <b>299.00 ETB</b> instead of 399.00 ETB. <b>Database registered amount adjusted to 299.00 ETB</b>; 100 ETB gap eliminated.<br/>"
    "• <b>FT Reference Recovered:</b> Review #12 (PID #548) visual audit extracted <b>FT26230PDVG5</b> (400 ETB CBE transfer). Resolved as 100% genuine.<br/>"
    "• <b>Live Veritas Verified:</b> 4 receipts (PIDs #539, #545, #543, #87) re-verified with 100% match directly from Telebirr gateway.<br/>"
    "• <b>Anti-Replay Guardrail Active:</b> PostgreSQL partial unique indexes and application-level duplicate checks deployed."
)
t_find = Table([[Paragraph(findings_text, body_style)]], colWidths=[174*mm])
t_find.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), C_GOLD_LIGHT),
    ('BOX', (0,0), (-1,-1), 1, C_GOLD),
    ('TOPPADDING', (0,0), (-1,-1), 6),
    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ('LEFTPADDING', (0,0), (-1,-1), 8),
    ('RIGHTPADDING', (0,0), (-1,-1), 8),
]))
story.append(t_find)
story.append(Spacer(1, 5*mm))

# Master Forensic Table
headers = [
    Paragraph("<b>#</b>", ParagraphStyle("h0", parent=body_bold, textColor=C_WHITE, alignment=TA_CENTER)),
    Paragraph("<b>PID</b>", ParagraphStyle("h1", parent=body_bold, textColor=C_WHITE, alignment=TA_CENTER)),
    Paragraph("<b>Stream & Date</b>", ParagraphStyle("h2", parent=body_bold, textColor=C_WHITE)),
    Paragraph("<b>Payer & Telegram</b>", ParagraphStyle("h3", parent=body_bold, textColor=C_WHITE)),
    Paragraph("<b>DB vs Paid</b>", ParagraphStyle("h4", parent=body_bold, textColor=C_WHITE, alignment=TA_RIGHT)),
    Paragraph("<b>Bank / Txn ID</b>", ParagraphStyle("h5", parent=body_bold, textColor=C_WHITE)),
    Paragraph("<b>Audit Verdict & Notes</b>", ParagraphStyle("h6", parent=body_bold, textColor=C_WHITE)),
]
table_rows = [headers]

for item in ITEMS:
    sev = item["severity"]
    if sev == "DANGER":
        badge_p = Paragraph(f"<b>{item['verdict']}</b><br/><font size=6 color='#555555'>{item['notes']}</font>", badge_danger)
        bg = C_DANGER_BG
    elif sev == "WARN":
        badge_p = Paragraph(f"<b>{item['verdict']}</b><br/><font size=6 color='#555555'>{item['notes']}</font>", badge_warn)
        bg = C_WARN_BG
    else:
        badge_p = Paragraph(f"<b>{item['verdict']}</b><br/><font size=6 color='#555555'>{item['notes']}</font>", badge_success)
        bg = C_WHITE if item["num"] % 2 == 0 else C_INFO_BG

    payer_p = Paragraph(f"<b>{item['payer'][:20]}</b><br/><font size=6.5 color='#7F8C8D'>{item['tg_user']} ({item['tg_handle']})</font>", body_style)
    amt_p = Paragraph(f"<b>{item['actual_amt']:,.0f} ETB</b><br/><font size=6.5 color='#7F8C8D'>DB: {item['db_amt']:,.0f}</font>", ParagraphStyle("ra", parent=body_style, alignment=TA_RIGHT))
    txn_p = Paragraph(f"<b>{item['bank']}</b><br/><font size=6.5 color='#1A3A5C'>{item['txn_id']}</font>", body_style)
    date_p = Paragraph(f"<b>{item['stream']}</b><br/><font size=6.5 color='#7F8C8D'>{item['date']}</font>", body_style)

    table_rows.append([
        Paragraph(f"<b>{item['num']:02d}</b>", ParagraphStyle("c0", parent=body_bold, alignment=TA_CENTER)),
        Paragraph(f"#{item['pid']}", ParagraphStyle("c1", parent=body_style, alignment=TA_CENTER)),
        date_p,
        payer_p,
        amt_p,
        txn_p,
        badge_p,
    ])

t_main = Table(
    table_rows,
    colWidths=[8*mm, 12*mm, 25*mm, 35*mm, 20*mm, 28*mm, 46*mm],
    repeatRows=1,
)
t_main.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), C_NAVY),
    ('TEXTCOLOR', (0,0), (-1,0), C_WHITE),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ('TOPPADDING', (0,0), (-1,-1), 4),
    ('LEFTPADDING', (0,0), (-1,-1), 3),
    ('RIGHTPADDING', (0,0), (-1,-1), 3),
    ('INNERGRID', (0,0), (-1,-1), 0.3, colors.HexColor("#D6DCE4")),
    ('BOX', (0,0), (-1,-1), 1, C_NAVY),
]))

for i, item in enumerate(ITEMS, 1):
    if item["severity"] == "DANGER":
        t_main.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), C_DANGER_BG)]))
    elif item["severity"] == "WARN":
        t_main.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), C_WARN_BG)]))
    elif i % 2 == 0:
        t_main.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), C_INFO_BG)]))

story.append(t_main)

doc = SimpleDocTemplate(
    str(pdf_path),
    pagesize=A4,
    leftMargin=18*mm,
    rightMargin=18*mm,
    topMargin=28*mm,
    bottomMargin=17*mm,
)
doc.build(story, canvasmaker=lambda fn, **kw: LetterheadCanvas(fn, pagesize=A4))
print(f"Generated PDF Audit Report: {pdf_path}")

# 3. Re-zip review queue
zip_out = Path("payments_export/UNVERIFIED_REVIEW_QUEUE")
shutil.make_archive(str(zip_out), 'zip', str(Path("payments_export/UNVERIFIED_REVIEW_QUEUE")))
print("Refreshed UNVERIFIED_REVIEW_QUEUE.zip")
