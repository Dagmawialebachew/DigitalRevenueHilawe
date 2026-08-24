from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .copy import copy_for, slot_label, day_label
from .helpers import local_food_name, rounded, review_warning_lines
from .models import DocumentContext
from .theme import BORDER, GRAPHITE, INK, IVORY, MUTED, ORANGE, ORANGE_SOFT, PAPER, resolve_pdf_fonts

PAGE_W, PAGE_H = A4
MARGIN_X = 16 * mm
TOP = 17 * mm
BOTTOM = 16 * mm


def _hex(value: str):
    return colors.HexColor(value)


def _is_ethiopic(char: str) -> bool:
    cp = ord(char)
    return (0x1200 <= cp <= 0x139F) or (0x2D80 <= cp <= 0x2DDF) or (0xAB00 <= cp <= 0xAB2F)


def _fontify(text: Any, fonts: dict[str, str], *, bold: bool = False) -> str:
    raw = str(text if text is not None else "")
    if not raw:
        return ""
    chunks: list[tuple[bool, str]] = []
    current_kind = _is_ethiopic(raw[0])
    current = [raw[0]]
    for char in raw[1:]:
        kind = _is_ethiopic(char)
        if kind == current_kind:
            current.append(char)
        else:
            chunks.append((current_kind, "".join(current)))
            current_kind = kind
            current = [char]
    chunks.append((current_kind, "".join(current)))
    out = []
    for ethiopic, chunk in chunks:
        name = fonts["eth_bold" if bold and ethiopic else "eth_regular" if ethiopic else "latin_bold" if bold else "latin_regular"]
        out.append(f'<font name="{name}">{escape(chunk)}</font>')
    return "".join(out)


def _register_fonts() -> dict[str, str]:
    paths = resolve_pdf_fonts()
    names = {
        "latin_regular": "HilaweLatin",
        "latin_bold": "HilaweLatinBold",
        "eth_regular": "HilaweEthiopic",
        "eth_bold": "HilaweEthiopicBold",
    }
    registrations = [
        (names["latin_regular"], paths.latin_regular),
        (names["latin_bold"], paths.latin_bold),
        (names["eth_regular"], paths.ethiopic_regular),
        (names["eth_bold"], paths.ethiopic_bold),
    ]
    registered = set(pdfmetrics.getRegisteredFontNames())
    for name, path in registrations:
        if name not in registered:
            pdfmetrics.registerFont(TTFont(name, str(path)))
    return names


def _styles(fonts: dict[str, str]) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    regular = fonts["latin_regular"]
    bold = fonts["latin_bold"]
    return {
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName=regular, fontSize=8.5, leading=11, textColor=_hex(GRAPHITE), spaceAfter=3),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontName=regular, fontSize=7.2, leading=9.2, textColor=_hex(GRAPHITE)),
        "micro": ParagraphStyle("micro", parent=base["BodyText"], fontName=regular, fontSize=6.4, leading=8, textColor=_hex(MUTED)),
        "kicker": ParagraphStyle("kicker", parent=base["BodyText"], fontName=bold, fontSize=7.5, leading=9, textColor=_hex(ORANGE), spaceAfter=3),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName=bold, fontSize=20, leading=23, textColor=_hex(INK), spaceAfter=8),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName=bold, fontSize=12.5, leading=15, textColor=_hex(INK), spaceAfter=5),
        "metric": ParagraphStyle("metric", parent=base["BodyText"], fontName=bold, fontSize=14.5, leading=17, textColor=_hex(INK)),
        "metric_label": ParagraphStyle("metric_label", parent=base["BodyText"], fontName=regular, fontSize=6.8, leading=8, textColor=_hex(GRAPHITE)),
        "meal_title": ParagraphStyle("meal_title", parent=base["BodyText"], fontName=bold, fontSize=10, leading=12, textColor=_hex(INK)),
        "slot": ParagraphStyle("slot", parent=base["BodyText"], fontName=bold, fontSize=6.8, leading=8, textColor=_hex(ORANGE)),
        "swap": ParagraphStyle("swap", parent=base["BodyText"], fontName=regular, fontSize=7, leading=9, textColor=_hex(ORANGE)),
        "white": ParagraphStyle("white", parent=base["BodyText"], fontName=bold, fontSize=8, leading=10, textColor=colors.white),
        "center": ParagraphStyle("center", parent=base["BodyText"], fontName=regular, fontSize=8, leading=10, textColor=_hex(GRAPHITE), alignment=TA_CENTER),
    }


def _p(text: Any, style: ParagraphStyle, fonts: dict[str, str], *, bold: bool = False) -> Paragraph:
    return Paragraph(_fontify(text, fonts, bold=bold), style)


def _footer_canvas(canvas, doc, *, context: DocumentContext, fonts: dict[str, str]):
    canvas.saveState()
    canvas.setFillColor(_hex(IVORY))
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(_hex(ORANGE))
    canvas.rect(MARGIN_X, PAGE_H - 10.5 * mm, 18 * mm, 1.6 * mm, fill=1, stroke=0)
    canvas.setFillColor(_hex(GRAPHITE))
    canvas.setFont(fonts["latin_regular"], 6.4)
    canvas.drawString(MARGIN_X, 8.5 * mm, f"HILAWE  ·  {context.plan_public_id}  ·  V{context.version_number}")
    canvas.setFont(fonts["latin_bold"], 6.4)
    canvas.drawRightString(PAGE_W - MARGIN_X, 8.5 * mm, f"{doc.page}")
    canvas.restoreState()


def _cover_canvas(canvas, doc, *, context: DocumentContext, fonts: dict[str, str]):
    canvas.saveState()
    canvas.setFillColor(_hex(IVORY))
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(_hex(ORANGE))
    canvas.rect(0, 0, 5.5 * mm, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(_hex(ORANGE_SOFT))
    canvas.roundRect(118 * mm, 30 * mm, 72 * mm, 108 * mm, 8 * mm, fill=1, stroke=0)
    image_path = Path(context.coach_image_path).expanduser() if context.coach_image_path else None
    if image_path and image_path.exists():
        try:
            image = ImageReader(str(image_path))
            canvas.drawImage(image, 126 * mm, 42 * mm, width=58 * mm, height=84 * mm, preserveAspectRatio=True, anchor='c', mask='auto')
        except Exception:
            canvas.setFillColor(_hex(ORANGE))
            canvas.circle(155 * mm, 84 * mm, 26 * mm, fill=1, stroke=0)
            canvas.setFillColor(colors.white)
            canvas.setFont(fonts["latin_bold"], 19)
            canvas.drawCentredString(155 * mm, 80 * mm, "H")
    else:
        canvas.setFillColor(_hex(ORANGE))
        canvas.circle(155 * mm, 84 * mm, 26 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont(fonts["latin_bold"], 19)
        canvas.drawCentredString(155 * mm, 80 * mm, "H")
    canvas.setFillColor(_hex(GRAPHITE))
    canvas.setFont(fonts["latin_regular"], 6.5)
    canvas.drawString(18 * mm, 12 * mm, f"{context.plan_public_id}  ·  V{context.version_number}")
    canvas.restoreState()


def _metric_card(label: str, value: str, styles, fonts):
    return Table(
        [[_p(value, styles["metric"], fonts, bold=True)], [_p(label, styles["metric_label"], fonts)]],
        colWidths=[53 * mm],
        rowHeights=[11 * mm, 8 * mm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _hex(PAPER)),
            ("BOX", (0, 0), (-1, -1), 0.6, _hex(BORDER)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ]),
    )


def _meal_block(meal: dict[str, Any], language: str, styles, fonts):
    macros = meal.get("macros") or {}
    content = [
        [_p(slot_label(str(meal.get("slot") or "Meal"), language).upper(), styles["slot"], fonts, bold=True)],
        [_p(str(meal.get("meal_name") or "Meal"), styles["meal_title"], fonts, bold=True)],
        [_p(
            f"{rounded(macros.get('kcal'))} kcal  ·  P {rounded(macros.get('protein'))}g  ·  C {rounded(macros.get('carbs'))}g  ·  F {rounded(macros.get('fat'))}g",
            styles["small"], fonts,
        )],
    ]
    for item in meal.get("items") or []:
        name = local_food_name(str(item.get("food_id") or ""), str(item.get("food_name") or "Food"), language)
        familiar = str(item.get("familiar") or "").strip()
        details = f"{name}  ·  {rounded(item.get('grams'))} g"
        if familiar:
            details += f"  ·  {familiar}"
        content.append([_p(details, styles["small"], fonts)])
    exchanges = meal.get("exchange_options") or []
    if exchanges and exchanges[0].get("options"):
        opt = exchanges[0]["options"][0]
        swap_name = local_food_name(str(opt.get("food_id") or ""), str(opt.get("food_name") or ""), language)
        content.append([_p(f"SWAP  ·  {swap_name}  ·  {rounded(opt.get('exchange_weight_g'))} g", styles["swap"], fonts, bold=False)])
    table = Table(content, colWidths=[171 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _hex(PAPER)),
        ("BOX", (0, 0), (-1, -1), 0.55, _hex(BORDER)),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6 * mm),
    ]))
    return table


def render_pdf(plan: dict[str, Any], context: DocumentContext, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fonts = _register_fonts()
    styles = _styles(fonts)
    c = copy_for(context.normalized_language)

    doc = BaseDocTemplate(
        str(path), pagesize=A4,
        leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=TOP, bottomMargin=BOTTOM,
        title=f"{context.client_name} - Coach Hilawe Meal Plan", author="Coach Hilawe",
    )
    frame = Frame(MARGIN_X, BOTTOM, PAGE_W - 2 * MARGIN_X, PAGE_H - TOP - BOTTOM, id="body")
    cover_frame = Frame(18 * mm, 22 * mm, 90 * mm, PAGE_H - 44 * mm, id="cover")
    doc.addPageTemplates([
        PageTemplate("cover", [cover_frame], onPage=lambda can, d: _cover_canvas(can, d, context=context, fonts=fonts)),
        PageTemplate("body", [frame], onPage=lambda can, d: _footer_canvas(can, d, context=context, fonts=fonts)),
    ])

    story = []
    duration = int((plan.get("product") or {}).get("duration_days") or 7)
    cover_title = ParagraphStyle("cover_title", fontName=fonts["latin_bold"], fontSize=24, leading=28, textColor=_hex(INK), spaceAfter=4)
    cover_sub = ParagraphStyle("cover_sub", fontName=fonts["latin_bold"], fontSize=9, leading=11, textColor=_hex(GRAPHITE), spaceAfter=23)
    client_style = ParagraphStyle("client", fontName=fonts["latin_bold"], fontSize=19, leading=22, textColor=_hex(INK), spaceAfter=4)
    goal_style = ParagraphStyle("goal", fontName=fonts["latin_bold"], fontSize=10, leading=12, textColor=_hex(ORANGE))
    story.extend([
        Spacer(1, 29 * mm),
        _p("HILAWE", styles["kicker"], fonts, bold=True),
        _p(c["personalized"], cover_title, fonts, bold=True),
        _p(f"{duration} DAY  ·  {c['nutrition_system']}", cover_sub, fonts, bold=True),
        _p(c["prepared_for"], styles["small"], fonts),
        _p(context.client_name, client_style, fonts, bold=True),
        _p(str((plan.get("profile_summary") or {}).get("goal") or "").replace("_", " ").title(), goal_style, fonts, bold=True),
        Spacer(1, 38 * mm),
        _p(c["draft_banner"] if context.status != "APPROVED" else "APPROVED", styles["kicker"], fonts, bold=True),
        NextPageTemplate("body"),
        PageBreak(),
    ])

    # Plan glance
    story += [_p("01", styles["kicker"], fonts, bold=True), _p(c["plan_glance"], styles["h1"], fonts, bold=True)]
    targets = plan.get("nutrition_targets") or {}
    product = plan.get("product") or {}
    profile = plan.get("profile_summary") or {}
    client = context.client_profile or {}
    metrics = [
        (c["current_weight"], f"{rounded(client.get('current_weight_kg'), 1)} kg" if client.get("current_weight_kg") else c["not_provided"]),
        (c["target_weight"], f"{rounded(client.get('target_weight_kg'), 1)} kg" if client.get("target_weight_kg") else c["not_provided"]),
        (c["daily_energy"], f"{rounded(targets.get('target_kcal'))} kcal"),
        (c["protein"], f"{rounded(targets.get('protein_g'))} g"),
        (c["meals_day"], str(product.get("meals_per_day") or "-")),
        (c["food_style"], str(profile.get("cuisine_style") or "-").replace("_", " ").title()),
    ]
    metric_rows = [[_metric_card(label, value, styles, fonts) for label, value in metrics[i:i+3]] for i in range(0, len(metrics), 3)]
    story.append(Table(metric_rows, colWidths=[57 * mm] * 3, style=TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 2*mm), ("TOPPADDING", (0,0), (-1,-1), 1*mm), ("BOTTOMPADDING", (0,0), (-1,-1), 1*mm)])))
    story += [Spacer(1, 5 * mm)]
    summary_rows = [
        [c["goal"], str(profile.get("goal") or "-").replace("_", " ").title()],
        [c["training"], f"{profile.get('training_days_per_week', '-')} days/week · {str(profile.get('training_type') or '-').replace('_', ' ').title()}"],
        [c["budget"], str(profile.get("grocery_budget") or "-").title()],
        [c["diet"], str(profile.get("dietary_pattern") or "-").replace("_", " ").title()],
        [c["fasting"], str(profile.get("orthodox_fasting") or "-").replace("_", " ").title()],
    ]
    summary_table = Table([[_p(a, styles["small"], fonts, bold=True), _p(b, styles["small"], fonts)] for a,b in summary_rows], colWidths=[45*mm, 126*mm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), _hex(ORANGE_SOFT)), ("BACKGROUND", (1,0), (1,-1), _hex(PAPER)),
        ("BOX", (0,0), (-1,-1), .5, _hex(BORDER)), ("INNERGRID", (0,0), (-1,-1), .35, _hex(BORDER)),
        ("LEFTPADDING", (0,0), (-1,-1), 3*mm), ("RIGHTPADDING", (0,0), (-1,-1), 3*mm),
        ("TOPPADDING", (0,0), (-1,-1), 2*mm), ("BOTTOMPADDING", (0,0), (-1,-1), 2*mm),
    ]))
    story += [summary_table, PageBreak()]

    # How to use
    story += [_p("02", styles["kicker"], fonts, bold=True), _p(c["how_to_use"], styles["h1"], fonts, bold=True)]
    for num, title, body in [("01", c["how_1_title"], c["how_1"]), ("02", c["how_2_title"], c["how_2"]), ("03", c["how_3_title"], c["how_3"])]:
        box = Table([[_p(num, styles["white"], fonts, bold=True), [_p(title, styles["h2"], fonts, bold=True), _p(body, styles["body"], fonts)]]], colWidths=[15*mm, 156*mm])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (0,0), _hex(ORANGE)), ("BACKGROUND", (1,0), (1,0), _hex(PAPER)),
            ("BOX", (0,0), (-1,-1), .55, _hex(BORDER)), ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 4*mm), ("RIGHTPADDING", (0,0), (-1,-1), 4*mm),
            ("TOPPADDING", (0,0), (-1,-1), 3*mm), ("BOTTOMPADDING", (0,0), (-1,-1), 3*mm),
        ]))
        story += [box, Spacer(1, 3*mm)]
    story += [PageBreak()]

    # Rotation map
    story += [_p("03", styles["kicker"], fonts, bold=True), _p(c["month_map"], styles["h1"], fonts, bold=True)]
    rotation = plan.get("rotation") or []
    weeks: dict[int, set[str]] = {}
    for row in rotation:
        weeks.setdefault(int(row.get("week") or 1), set()).add(str(row.get("mode") or "PRIMARY"))
    if not weeks:
        weeks = {1: {"PRIMARY"}}
    rot_rows = []
    for week, modes in sorted(weeks.items()):
        mode = "SWAP" if "SWAP" in modes else "PRIMARY"
        rot_rows.append([_p(f"{c['week']} {week}", styles["meal_title"], fonts, bold=True), _p(c["swap_rotation"] if mode == "SWAP" else c["primary"], styles["body"], fonts)])
    rot_table = Table(rot_rows, colWidths=[55*mm, 116*mm])
    rot_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), _hex(ORANGE_SOFT)), ("BACKGROUND", (1,0), (1,-1), _hex(PAPER)),
        ("BOX", (0,0), (-1,-1), .55, _hex(BORDER)), ("INNERGRID", (0,0), (-1,-1), .35, _hex(BORDER)),
        ("LEFTPADDING", (0,0), (-1,-1), 4*mm), ("RIGHTPADDING", (0,0), (-1,-1), 4*mm),
        ("TOPPADDING", (0,0), (-1,-1), 3*mm), ("BOTTOMPADDING", (0,0), (-1,-1), 3*mm),
    ]))
    story += [rot_table, Spacer(1, 5*mm), _p("7-day core + controlled swap rotation. The detailed meal pages below are the reviewed core used across the purchased duration.", styles["body"], fonts), PageBreak()]

    # Core days
    for day in plan.get("core_week") or []:
        story += [_p(f"DAY {int(day.get('day_index', 0))+1:02d}  ·  {day.get('date','')}", styles["kicker"], fonts, bold=True), _p(day_label(str(day.get("day_name") or "Day"), context.normalized_language), styles["h1"], fonts, bold=True)]
        if day.get("fasting"):
            story.append(_p(c["fasting_day"], styles["kicker"], fonts, bold=True))
        totals = day.get("totals") or {}
        story += [_p(f"{rounded(totals.get('kcal'))} kcal  ·  P {rounded(totals.get('protein'))}g  ·  C {rounded(totals.get('carbs'))}g  ·  F {rounded(totals.get('fat'))}g", styles["body"], fonts), Spacer(1, 2*mm)]
        for meal in day.get("meals") or []:
            story += [KeepTogether([_meal_block(meal, context.normalized_language, styles, fonts), Spacer(1, 2.3*mm)])]
        warnings = day.get("warnings") or []
        if warnings:
            story.append(_p(c["warning"] + ": " + " | ".join(str(x) for x in warnings[:2]), styles["swap"], fonts))
        story.append(PageBreak())

    # Grocery
    story += [_p("04", styles["kicker"], fonts, bold=True), _p(c["grocery"], styles["h1"], fonts, bold=True), _p(c["grocery_intro"], styles["body"], fonts), Spacer(1, 2*mm)]
    grocery_rows = [[_p("Item", styles["white"], fonts, bold=True), _p("Category", styles["white"], fonts, bold=True), _p(c["planned"], styles["white"], fonts, bold=True), _p(c["buy"], styles["white"], fonts, bold=True)]]
    for row in plan.get("grocery") or []:
        grocery_rows.append([
            _p(local_food_name(str(row.get("food_id") or ""), str(row.get("buy_item") or ""), context.normalized_language), styles["small"], fonts),
            _p(str(row.get("category") or ""), styles["micro"], fonts),
            _p(f"{rounded(row.get('planned_grams'))} g", styles["micro"], fonts),
            _p(str(row.get("purchase_quantity") or ""), styles["micro"], fonts),
        ])
    grocery = Table(grocery_rows, colWidths=[67*mm, 40*mm, 30*mm, 34*mm], repeatRows=1)
    grocery.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), _hex(ORANGE)), ("ROWBACKGROUNDS", (0,1), (-1,-1), [_hex(PAPER), _hex(IVORY)]),
        ("GRID", (0,0), (-1,-1), .3, _hex(BORDER)), ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 2.2*mm), ("RIGHTPADDING", (0,0), (-1,-1), 2.2*mm),
        ("TOPPADDING", (0,0), (-1,-1), 1.5*mm), ("BOTTOMPADDING", (0,0), (-1,-1), 1.5*mm),
    ]))
    story += [grocery, PageBreak()]

    # Portion/hydration
    story += [_p("05", styles["kicker"], fonts, bold=True), _p(c["portion_hydration"], styles["h1"], fonts, bold=True), _p(c["hydration"], styles["h2"], fonts, bold=True)]
    if context.hydration_target_l:
        hydration_style = ParagraphStyle("hydr", fontName=fonts["latin_bold"], fontSize=25, leading=28, textColor=_hex(ORANGE), spaceAfter=5)
        story.append(_p(f"{context.hydration_target_l:.1f} L / day", hydration_style, fonts, bold=True))
    story += [_p(c["hydration_general"], styles["body"], fonts), Spacer(1, 5*mm), _p(c["exact"] + " + " + c["familiar"], styles["h2"], fonts, bold=True), _p(c["portion_note"], styles["body"], fonts), Spacer(1, 8*mm), _p(c["coach_note"], styles["kicker"], fonts, bold=True), _p(c["coach_text"], ParagraphStyle("coach", fontName=fonts["latin_bold"], fontSize=11.5, leading=16, textColor=_hex(INK)), fonts, bold=True), PageBreak()]

    # Review page
    story += [_p("06", styles["kicker"], fonts, bold=True), _p(c["review"], styles["h1"], fonts, bold=True), _p(c["review_required"], ParagraphStyle("reviewwarn", fontName=fonts["latin_bold"], fontSize=9.5, leading=12, textColor=_hex(ORANGE), spaceAfter=8), fonts, bold=True)]
    values = [[c["plan_id"], context.plan_public_id], [c["version"], f"V{context.version_number}"], [c["status"], context.status], [c["engine"], str(plan.get("engine_version") or "-")], [c["dataset"], str(plan.get("dataset_version") or "-")]]
    if context.approved_by:
        values.append([c["approved_by"], context.approved_by])
    if context.approved_at:
        values.append([c["approved_at"], context.approved_at])
    review_table = Table([[_p(a, styles["small"], fonts, bold=True), _p(b, styles["small"], fonts)] for a,b in values], colWidths=[45*mm, 126*mm])
    review_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), _hex(ORANGE_SOFT)), ("BACKGROUND", (1,0), (1,-1), _hex(PAPER)),
        ("BOX", (0,0), (-1,-1), .5, _hex(BORDER)), ("INNERGRID", (0,0), (-1,-1), .35, _hex(BORDER)),
        ("LEFTPADDING", (0,0), (-1,-1), 3*mm), ("RIGHTPADDING", (0,0), (-1,-1), 3*mm),
        ("TOPPADDING", (0,0), (-1,-1), 2.3*mm), ("BOTTOMPADDING", (0,0), (-1,-1), 2.3*mm),
    ]))
    story.append(review_table)
    warnings = review_warning_lines(plan)
    if warnings:
        story += [Spacer(1, 6*mm), _p(c["warning"], styles["kicker"], fonts, bold=True)]
        for warning in warnings:
            story.append(_p("• " + warning, styles["small"], fonts))

    doc.build(story)
    return path
