"""5-Client Pilot Launch Broadcast System for Coach Hilawe.

Ultra-personalized, high-converting, concise broadcast engine segmenting by:
- Gender (MALE / FEMALE Amharic verb and honorific conjugations)
- Customer status (PAID workout/club buyers vs UNPAID cold leads)
- 5-spot pilot exclusivity & Coach Hilawe personal verification
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiogram import Bot, F, Router, types
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from database.db import Database
from meal_plan.runtime import admin_ids, frontend_url, frontend_url_is_valid, reviewer_ids

logger = logging.getLogger("PILOT_BROADCAST")
router = Router(name="meal_plan_pilot_broadcast")


def _authorized_admin(telegram_id: int) -> bool:
    allowed = set(settings.ADMIN_IDS) | set(admin_ids()) | set(reviewer_ids())
    return telegram_id in allowed


def format_pilot_broadcast_message(
    full_name: str | None,
    gender: str | None,
    has_bought: bool,
    mini_app_url: str | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """Generates a short, punchy, high-converting broadcast message and markup."""
    name_clean = (full_name or "").strip().split()[0].capitalize() if full_name else ""
    is_female = str(gender or "").strip().upper() == "FEMALE"

    if not name_clean:
        name_clean = "እህቴ" if is_female else "ወንድሜ"

    if has_bought:
        if is_female:
            text = (
                f"<b>🚨 {name_clean}፣ ይህ ለአንቺ የተዘጋጀ ልዩ ጥሪ ነው!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"{name_clean} 👋 አሰልጣኝ ህላዌ ነኝ።\n\n"
                f"የስፖርት ፕሮግራሜን ይዘሽ ለውጥ ለማምጣት እየደከምሽ እንደሆነ አውቃለሁ፤ "
                f"ነገር ግን <b>የሰውነት ቅርጽና ክብደት 80% የሚወሰነው በምንመገበው ምግብ ላይ ነው።</b> "
                f"ያለ ትክክለኛ የምግብ እቅድ መልፋት ውጤቱን ያዘገየዋል።\n\n"
                f"ለአንቺ የሰውነት ክብደት እና ግብ ብቻ ተሰልቶ የተዘጋጀውን <b>የግል የምግብ እቅድ (Personalized Meal Plan)</b> ስርዓት ዛሬ ይፋ አድርጌያለሁ።\n\n"
                f"⚠️ <b>ለጥራት ስንል የምንቀበለው 5 ሰዎችን ብቻ ነው!</b> እያንዳንዱን እቅድ እኔ ራሴ በጥንቃቄ አይቼ የማጸድቀው ስለሆነ 5ቱ ቦታዎች እንዳለቁ ወዲያውኑ ይዘጋል።\n\n"
                f"👇 <b>ከ5ቱ አንዷ ለመሆን አሁኑኑ ያዢ፦</b>"
            )
            btn_text = f"🥗 የ5ቱን ልዩ ቦታ ያዢ ({name_clean})"
        else:
            text = (
                f"<b>🚨 {name_clean}፣ ይህ ለአንተ የተዘጋጀ ልዩ ጥሪ ነው!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"{name_clean} 👋 አሰልጣኝ ህላዌ ነኝ።\n\n"
                f"የስፖርት ፕሮግራሜን ይዘህ እየሰራህ እንደሆነ አውቃለሁ፤ "
                f"ነገር ግን <b>80% የሰውነት ለውጥ የሚመጣው በምንበላው ምግብ ላይ ነው።</b> "
                f"ያለ ትክክለኛ የምግብ እቅድ ጅምናዚየም መልፋት ውጤቱን ያዘገየዋል።\n\n"
                f"ለአንተ የሰውነት ክብደት እና ግብ ብቻ ተሰልቶ የተዘጋጀውን <b>የግል የምግብ እቅድ (Personalized Meal Plan)</b> ስርዓት ዛሬ ይፋ አድርጌያለሁ።\n\n"
                f"⚠️ <b>ለጥራት ስንል የምንቀበለው 5 ሰዎችን ብቻ ነው!</b> እያንዳንዱን እቅድ እኔ ራሴ በጥንቃቄ አይቼ የማጸድቀው ስለሆነ 5ቱ ቦታዎች እንዳለቁ ወዲያውኑ ይዘጋል።\n\n"
                f"👇 <b>ከ5ቱ አንዱ ለመሆን አሁኑኑ ያዝ፦</b>"
            )
            btn_text = f"🥗 የ5ቱን ልዩ ቦታ ያዝ ({name_clean})"
    else:
        if is_female:
            text = (
                f"<b>⚡️ {name_clean}፣ ሰውነትሽን የምትቀይሪበት ትክክለኛ ጊዜ አሁን ነው!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"{name_clean} 👋 አሰልጣኝ ህላዌ ነኝ።\n\n"
                f"ቦቱ ላይ ገብተሽ መረጃሽን ከሞላሽ ቆይተሻል፤ ነገር ግን እውነተኛ ለውጥ የሚጀምረው ከትክክለኛ አመጋገብ ነው። "
                f"በየቀኑ በሀገራችን ምግቦች ምን ያህል መመገብ እንዳለብሽ የሚያሳይ <b>የግል የምግብ እቅድ (Personalized Meal Plan)</b> ስርዓት አዘጋጅቼልሻለሁ።\n\n"
                f"ይህ በጅምላ የሚሰጥ ሳይሆን ለአንቺ የሰውነት ክብደትና ግብ ብቻ በጥናት የተሰላ ነው።\n\n"
                f"⚠️ <b>ማሳሰቢያ፦</b> አገልግሎቱን በከፍተኛ ጥራት ለመስጠት በመጀመሪያው ዙር <b>5 ሰዎችን ብቻ</b> እንቀበላለን። 5ቱ ቦታዎች እንዳለቁ ምዝገባው ወዲያውኑ ይዘጋል።\n\n"
                f"👇 <b>ቦታሽን አሁኑኑ ለማስከበር ተጠቀሚ፦</b>"
            )
            btn_text = f"⚡️ ከ5ቱ አንዷ ሁኚ ({name_clean})"
        else:
            text = (
                f"<b>⚡️ {name_clean}፣ ሰውነትህን የምትቀይርበት ትክክለኛ ጊዜ አሁን ነው!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"{name_clean} 👋 አሰልጣኝ ህላዌ ነኝ።\n\n"
                f"ቦቱ ላይ ገብተህ መረጃህን ከሞላህ ቆይተሃል፤ ነገር ግን እውነተኛ ለውጥ የሚጀምረው ከትክክለኛ አመጋገብ ነው። "
                f"በየቀኑ በሀገራችን ምግቦች ምን ያህል መመገብ እንዳለብህ የሚያሳይ <b>የግል የምግብ እቅድ (Personalized Meal Plan)</b> ስርዓት አዘጋጅቼልሃለሁ።\n\n"
                f"ይህ በጅምላ የሚሰጥ ሳይሆን ለአንተ የሰውነት ክብደትና ግብ ብቻ በጥናት የተሰላ ነው።\n\n"
                f"⚠️ <b>ማሳሰቢያ፦</b> አገልግሎቱን በከፍተኛ ጥራት ለመስጠት በመጀመሪያው ዙር <b>5 ሰዎችን ብቻ</b> እንቀበላለን። 5ቱ ቦታዎች እንዳለቁ ምዝገባው ወዲያውኑ ይዘጋል።\n\n"
                f"👇 <b>ቦታህን አሁኑኑ ለማስከበር ተጠቀም፦</b>"
            )
            btn_text = f"⚡️ ከ5ቱ አንዱ ሁን ({name_clean})"

    # Construct the button action
    resolved_url = mini_app_url or frontend_url()
    if frontend_url_is_valid(resolved_url) and not resolved_url.startswith("http://localhost"):
        button = InlineKeyboardButton(text=btn_text, web_app=WebAppInfo(url=resolved_url))
    else:
        # Fallback to menu command if no public HTTPS domain configured yet
        button = InlineKeyboardButton(text=btn_text, callback_data="meal_pilot_app_open")

    kb = InlineKeyboardMarkup(inline_keyboard=[[button]])
    return text, kb


async def fetch_broadcast_targets(db: Database, segment: str = "all") -> list[dict[str, Any]]:
    """Fetches user targets with purchase state and gender details."""
    query = """
        SELECT 
            u.telegram_id,
            u.full_name,
            u.username,
            u.gender,
            u.language,
            EXISTS (
                SELECT 1 FROM payments p 
                WHERE p.user_id = u.telegram_id AND p.status = 'approved'
                UNION
                SELECT 1 FROM club_payments cp 
                WHERE cp.user_id = u.telegram_id AND cp.status = 'approved'
            ) AS has_bought
        FROM users u
        WHERE u.telegram_id > 0
    """
    if segment == "paid":
        query += """ AND EXISTS (
            SELECT 1 FROM payments p WHERE p.user_id = u.telegram_id AND p.status = 'approved'
            UNION
            SELECT 1 FROM club_payments cp WHERE cp.user_id = u.telegram_id AND cp.status = 'approved'
        )"""
    elif segment == "unpaid":
        query += """ AND NOT EXISTS (
            SELECT 1 FROM payments p WHERE p.user_id = u.telegram_id AND p.status = 'approved'
            UNION
            SELECT 1 FROM club_payments cp WHERE cp.user_id = u.telegram_id AND cp.status = 'approved'
        )"""

    rows = await db._pool.fetch(query)
    return [dict(r) for r in rows]


def pilot_broadcast_admin_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🧪 Test Preview (Admin Chat)", callback_data="pilot_bc:test")
    builder.button(text="🎯 Send to Unpaid Leads", callback_data="pilot_bc:unpaid")
    builder.button(text="🔥 Send to Paid Buyers", callback_data="pilot_bc:paid")
    builder.button(text="📣 Broadcast to All Users", callback_data="pilot_bc:all")
    builder.button(text="❌ Cancel", callback_data="pilot_bc:cancel")
    builder.adjust(1, 2, 1, 1)
    return builder.as_markup()


@router.message(Command("meal_pilot_broadcast", "pilot_broadcast"))
async def admin_pilot_broadcast_dashboard(message: types.Message, db: Database):
    """Admin command to review targeting and launch the 5-client pilot broadcast."""
    if not _authorized_admin(message.from_user.id):
        return

    # Aggregate live stats
    stats_query = """
        SELECT 
            COUNT(1) as total,
            COUNT(1) FILTER (WHERE EXISTS (
                SELECT 1 FROM payments p WHERE p.user_id = u.telegram_id AND p.status = 'approved'
                UNION
                SELECT 1 FROM club_payments cp WHERE cp.user_id = u.telegram_id AND cp.status = 'approved'
            )) as paid_total,
            COUNT(1) FILTER (WHERE NOT EXISTS (
                SELECT 1 FROM payments p WHERE p.user_id = u.telegram_id AND p.status = 'approved'
                UNION
                SELECT 1 FROM club_payments cp WHERE cp.user_id = u.telegram_id AND cp.status = 'approved'
            )) as unpaid_total,
            COUNT(1) FILTER (WHERE UPPER(TRIM(COALESCE(u.gender, 'MALE'))) = 'FEMALE') as female_total
        FROM users u
        WHERE u.telegram_id > 0
    """
    stats = await db._pool.fetchrow(stats_query)
    total = stats["total"] if stats else 0
    paid = stats["paid_total"] if stats else 0
    unpaid = stats["unpaid_total"] if stats else 0
    female = stats["female_total"] if stats else 0
    male = total - female

    app_url = frontend_url()
    url_status = "✅ HTTPS Configured" if frontend_url_is_valid(app_url) else "⚠️ Fallback/Not Public"

    dashboard = (
        "🚀 <b>5-SPOT MEAL PLAN PILOT BROADCAST CENTER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Total Subscribers:</b> <code>{total:,}</code>\n"
        f"├ 🛍️ <b>Paid Program Buyers:</b> <code>{paid:,}</code>\n"
        f"└ 🎯 <b>Unpaid Leads:</b> <code>{unpaid:,}</code>\n\n"
        f"⚧️ <b>Gender Breakdown:</b>\n"
        f"├ 🚹 Men: <code>{male:,}</code>\n"
        f"└ 🚺 Women: <code>{female:,}</code>\n\n"
        f"🌐 <b>Mini App Link:</b> <code>{app_url}</code> ({url_status})\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Click <b>'Test Preview'</b> to receive all 4 personalized variations in your chat, "
        "or choose a segment to execute the launch broadcast:"
    )

    await message.answer(dashboard, reply_markup=pilot_broadcast_admin_kb(), parse_mode="HTML")


@router.callback_query(F.data == "pilot_bc:test")
async def execute_admin_test_previews(callback: types.CallbackQuery, bot: Bot):
    """Sends all 4 structural variations to the admin."""
    if not _authorized_admin(callback.from_user.id):
        return await callback.answer("⚠️ Access Denied", show_alert=True)

    await callback.answer("Delivering 4 personalized previews...")
    chat_id = callback.message.chat.id

    # 1. Paid Male
    txt, kb = format_pilot_broadcast_message("ዳዊት", "MALE", has_bought=True)
    await bot.send_message(chat_id, f"📝 <b>[PREVIEW 1/4: PAID MALE]</b>\n\n{txt}", reply_markup=kb, parse_mode="HTML")

    # 2. Paid Female
    txt, kb = format_pilot_broadcast_message("ሰላም", "FEMALE", has_bought=True)
    await bot.send_message(chat_id, f"📝 <b>[PREVIEW 2/4: PAID FEMALE]</b>\n\n{txt}", reply_markup=kb, parse_mode="HTML")

    # 3. Unpaid Male
    txt, kb = format_pilot_broadcast_message("ዮናስ", "MALE", has_bought=False)
    await bot.send_message(chat_id, f"📝 <b>[PREVIEW 3/4: UNPAID MALE]</b>\n\n{txt}", reply_markup=kb, parse_mode="HTML")

    # 4. Unpaid Female
    txt, kb = format_pilot_broadcast_message("ሄለን", "FEMALE", has_bought=False)
    await bot.send_message(chat_id, f"📝 <b>[PREVIEW 4/4: UNPAID FEMALE]</b>\n\n{txt}", reply_markup=kb, parse_mode="HTML")

    await bot.send_message(
        chat_id,
        "✅ <b>All 4 preview variants delivered!</b>\nVerify formatting, tone, and buttons above before broadcasting live.",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("pilot_bc:"))
async def execute_live_pilot_broadcast(callback: types.CallbackQuery, bot: Bot, db: Database):
    """Executes live broadcast with rate-limiting, error handling, and live progress."""
    admin_id = callback.from_user.id
    if not _authorized_admin(admin_id):
        return await callback.answer("⚠️ Access Denied", show_alert=True)

    segment = callback.data.split(":")[1]
    if segment == "cancel":
        await callback.message.edit_text("🚫 Broadcast cancelled.")
        return await callback.answer()

    if segment not in {"paid", "unpaid", "all"}:
        return

    await callback.answer(f"Starting {segment} broadcast...")
    targets = await fetch_broadcast_targets(db, segment)
    total = len(targets)

    if total == 0:
        return await callback.message.answer(f"⚠️ No users found in segment '{segment}'.")

    status_msg = await callback.message.answer(
        f"🚀 <b>Broadcasting to {total:,} users ({segment.upper()})...</b>\n"
        f"Progress: 0/{total}\n"
        f"✅ Sent: 0 | 🚫 Failed: 0",
        parse_mode="HTML",
    )

    sent = 0
    failed = 0
    app_url = frontend_url()

    for idx, user in enumerate(targets, start=1):
        uid = user["telegram_id"]
        fname = user.get("full_name") or ""
        gender = user.get("gender") or "MALE"
        has_bought = bool(user.get("has_bought"))

        text, kb = format_pilot_broadcast_message(fname, gender, has_bought, mini_app_url=app_url)

        try:
            await bot.send_message(chat_id=uid, text=text, reply_markup=kb, parse_mode="HTML")
            sent += 1
        except (TelegramForbiddenError, TelegramAPIError) as exc:
            failed += 1
            logger.debug("Failed sending to user %s: %s", uid, exc)
        except Exception as exc:
            failed += 1
            logger.warning("Unexpected error sending to user %s: %s", uid, exc)

        # Rate-limiting safety sleep
        await asyncio.sleep(0.04)

        if idx % 50 == 0 or idx == total:
            try:
                await status_msg.edit_text(
                    f"🚀 <b>Broadcasting to {total:,} users ({segment.upper()})...</b>\n"
                    f"Progress: {idx}/{total}\n"
                    f"✅ Sent: {sent} | 🚫 Failed: {failed}",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    await callback.message.answer(
        f"🏁 <b>Pilot Broadcast Complete!</b>\n\n"
        f"🎯 Segment: <code>{segment.upper()}</code>\n"
        f"👥 Total Targeted: <code>{total:,}</code>\n"
        f"✅ Delivered: <code>{sent:,}</code>\n"
        f"🚫 Inactive/Blocked: <code>{failed:,}</code>",
        parse_mode="HTML",
    )
