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
                f"<b>🥗✨ {name_clean}፣ ለውጥሽን በ2 እጥፍ የሚያፈጥን ልዩ እድል!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"{name_clean} 👋 አሰልጣኝ ህላዌ ነኝ።\n\n"
                f"የስፖርት ፕሮግራሜን ወስደሽ ጥሩ እንቅስቃሴ ላይ መሆንሽ ያኮራል! 🏋️‍♀️👏\n\n"
                f"ነገር ግን የምትፈልጊውን የሰውነት ቅርጽ በፍጥነት ለማምጣት አንድ ወሳኝ ነገር ይቀርሻል፦ <b>80% የሰውነት ለውጥ የሚወሰነው በምንመገበው ምግብ መጠን እና አይነት ነው።</b> 📊\n\n"
                f"በግምት መመገብ ውጤትሽን ስለሚያዘገየው፣ በሀገራችን ምግቦች ለአንቺ ክብደትና ግብ ብቻ በጥናት የተሰላ <b>የግል የምግብ እቅድ (Custom Meal Plan)</b> የምዘጋጅበትን አዲስ ሲስተም ዛሬ ከፍቻለሁ! 🥗🔥\n\n"
                f"<i>⚠️ ማሳሰቢያ፦</i> እያንዳንዱን እቅድ እኔ ራሴ በጥንቃቄ ስለማዘጋጀው፣ በዚህ የመጀመሪያ ዙር <b>የምቀበለው 5 ሰዎችን ብቻ ነው!</b> 💎\n\n"
                f"5ቱ ቦታዎች ሲሞሉ ምዝገባው ወዲያውኑ ይዘጋል። 🔒\n\n"
                f"👇 <b>የአንቺን እቅድ እንድሰራልሽ አሁኑኑ ቦታሽን ያዢ፦</b>"
            )
            btn_text = f"🥗 የ5ቱን ልዩ ቦታ ያዢ ({name_clean})"
        else:
            text = (
                f"<b>🥗✨ {name_clean}፣ ለውጥህን በ2 እጥፍ የሚያፈጥን ልዩ እድል!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"{name_clean} 👋 አሰልጣኝ ህላዌ ነኝ።\n\n"
                f"የስፖርት ፕሮግራሜን ወስደህ ጥሩ እንቅስቃሴ ላይ መሆንህ ያኮራል! 🏋️‍♂️👏\n\n"
                f"ነገር ግን የምትፈልገውን የሰውነት ለውጥ በፍጥነት ለማምጣት አንድ ወሳኝ ነገር ይቀርሃል፦ <b>80% የሰውነት ለውጥ የሚወሰነው በምንበላው ምግብ መጠን እና አይነት ነው።</b> 📊\n\n"
                f"በግምት መመገብ ውጤትህን ስለሚያዘገየው፣ በሀገራችን ምግቦች ለአንተ ክብደትና ግብ ብቻ በጥናት የተሰላ <b>የግል የምግብ እቅድ (Custom Meal Plan)</b> የምዘጋጅበትን አዲስ ሲስተም ዛሬ ከፍቻለሁ! 🥗🔥\n\n"
                f"<i>⚠️ ማሳሰቢያ፦</i> እያንዳንዱን እቅድ እኔ ራሴ በጥንቃቄ ስለማዘጋጀው፣ በዚህ የመጀመሪያ ዙር <b>የምቀበለው 5 ሰዎችን ብቻ ነው!</b> 💎\n\n"
                f"5ቱ ቦታዎች ሲሞሉ ምዝገባው ወዲያውኑ ይዘጋል። 🔒\n\n"
                f"👇 <b>የአንተን እቅድ እንድሰራልህ አሁኑኑ ቦታህን ያዝ፦</b>"
            )
            btn_text = f"🥗 የ5ቱን ልዩ ቦታ ያዝ ({name_clean})"
    else:
        if is_female:
            text = (
                f"<b>🥗🔥 {name_clean}፣ የሰውነት ለውጥሽ ሚስጥር እዚህ አለ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"{name_clean} 👋 አሰልጣኝ ህላዌ ነኝ።\n\n"
                f"ብዙ ሰዎች ክብደት ለመቀነስም ሆነ ቅርጽ ለማውጣት ምግብ መተው ወይም ከባድ ስፖርት መስራት ብቻ ይመስላቸዋል። እውነቱ ግን <b>80% ለውጥ የሚመጣው ትክክለኛውን የሀገራችንን ምግብ በትክክለኛው መጠን በመመገብ ነው!</b> 🎯\n\n"
                f"ሳትራቢ እና የምትወጂውን ምግብ ሳትተዪ፣ ለአንቺ ክብደትና ግብ ብቻ በጥናት የሚሰላ <b>የግል የምግብ እቅድ (Custom Meal Plan)</b> የምዘጋጅበትን ልዩ እድል ዛሬ ከፍቻለሁ! 🥗✨\n\n"
                f"<i>⚠️ ማሳሰቢያ፦</i> የእያንዳንዱን ሰው እቅድ እኔ ራሴ በጥንቃቄ ስለማዘጋጀው፣ በዚህ የመጀመሪያ ዙር <b>የምቀበለው 5 ሰዎችን ብቻ ነው!</b> 💎\n\n"
                f"5ቱ ቦታዎች እንዳለቁ ምዝገባው ወዲያውኑ ይዘጋል። ⏳🔒\n\n"
                f"👇 <b>ከ5ቱ አንዷ ለመሆን አሁኑኑ ቦታሽን ያዢ፦</b>"
            )
            btn_text = f"⚡️ ከ5ቱ አንዷ ሁኚ ({name_clean})"
        else:
            text = (
                f"<b>🥗🔥 {name_clean}፣ የሰውነት ለውጥህ ሚስጥር እዚህ አለ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"{name_clean} 👋 አሰልጣኝ ህላዌ ነኝ።\n\n"
                f"ብዙ ሰዎች ሰውነታቸውን ለመቀየር ከባድ ስፖርት መስራት ብቻ በቂ ይመስላቸዋል። እውነቱ ግን <b>80% የሰውነት ለውጥ የሚመጣው ትክክለኛውን የሀገራችንን ምግብ በትክክለኛው መጠን በመመገብ ነው!</b> 🎯\n\n"
                f"በግምት መመገብን ትተህ፣ ለአንተ ክብደትና ግብ ብቻ በጥናት የሚሰላ <b>የግል የምግብ እቅድ (Custom Meal Plan)</b> የምዘጋጅበትን ልዩ እድል ዛሬ ከፍቻለሁ! 🥗✨\n\n"
                f"<i>⚠️ ማሳሰቢያ፦</i> የእያንዳንዱን ሰው እቅድ እኔ ራሴ በጥንቃቄ ስለማዘጋጀው፣ በዚህ የመጀመሪያ ዙር <b>የምቀበለው 5 ሰዎችን ብቻ ነው!</b> 💎\n\n"
                f"5ቱ ቦታዎች እንዳለቁ ምዝገባው ወዲያውኑ ይዘጋል። ⏳🔒\n\n"
                f"👇 <b>ከ5ቱ አንዱ ለመሆን አሁኑኑ ቦታህን ያዝ፦</b>"
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


# ─────────────────────────────────────────────────────────────
# SHORT FIX BROADCAST (FOR USERS FACING ACCESS ISSUES)
# ─────────────────────────────────────────────────────────────

def format_fix_broadcast_message(mini_app_url: str | None = None) -> tuple[str, InlineKeyboardMarkup]:
    """Short 3-sentence message notifying users that access is fixed, with pilot cap notice."""
    text = (
        "<b>ቅድም የምግብ ፕላኑ «አልሰራ አለኝ» ላላችሁ ይሄው አሁን ተስተካክሏል! ✅</b>\n\n"
        "አሁን ክፍት ስለሆነ ከታች ያለውን በተን ተጭናችሁ በቀጥታ መጀመር ትችላላችሁ። 👇\n\n"
        "<i>(ለ5 ሰው ብቻ ነው የሚዘጋጀው!)</i>"
    )
    resolved_url = mini_app_url or frontend_url()
    btn_text = "🥗 የምግብ ፕላኑን ክፈት"
    if frontend_url_is_valid(resolved_url) and not resolved_url.startswith("http://localhost"):
        button = InlineKeyboardButton(text=btn_text, web_app=WebAppInfo(url=resolved_url))
    else:
        button = InlineKeyboardButton(text=btn_text, callback_data="meal_pilot_app_open")

    kb = InlineKeyboardMarkup(inline_keyboard=[[button]])
    return text, kb


@router.message(Command("fix_broadcast", "meal_fix_broadcast"))
async def admin_fix_broadcast_preview(message: types.Message, db: Database):
    """Admin command to preview and dispatch the short fix announcement."""
    if not _authorized_admin(message.from_user.id):
        return

    text, kb = format_fix_broadcast_message()
    await message.answer(f"👀 <b>[BROADCAST PREVIEW]</b>\n\n{text}", reply_markup=kb, parse_mode="HTML")

    count_row = await db._pool.fetchrow("SELECT COUNT(1) as total FROM users WHERE telegram_id > 0")
    total_users = count_row["total"] if count_row else 0

    builder = InlineKeyboardBuilder()
    builder.button(text=f"🚀 Broadcast to All ({total_users:,} Users)", callback_data="fix_bc:all")
    builder.button(text="❌ Cancel", callback_data="fix_bc:cancel")
    builder.adjust(1)

    await message.answer(
        f"📢 <b>Fix Broadcast Ready!</b>\n"
        f"👥 <b>Target Audience:</b> <code>{total_users:,}</code> registered users.\n\n"
        f"Click below to send this notification now:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("fix_bc:"))
async def execute_fix_broadcast(callback: types.CallbackQuery, bot: Bot, db: Database):
    """Dispatches the short fix announcement to all registered users."""
    admin_id = callback.from_user.id
    if not _authorized_admin(admin_id):
        return await callback.answer("⚠️ Access Denied", show_alert=True)

    action = callback.data.split(":")[1]
    if action == "cancel":
        await callback.message.edit_text("🚫 Fix broadcast cancelled.")
        return await callback.answer()

    if action != "all":
        return

    await callback.answer("Starting broadcast...")
    rows = await db._pool.fetch("SELECT telegram_id FROM users WHERE telegram_id > 0")
    targets = [r["telegram_id"] for r in rows]
    total = len(targets)

    if total == 0:
        return await callback.message.answer("⚠️ No users found in database.")

    status_msg = await callback.message.answer(
        f"🚀 <b>Broadcasting Fix Message to {total:,} users...</b>\n"
        f"Progress: 0/{total}\n"
        f"✅ Sent: 0 | 🚫 Failed: 0",
        parse_mode="HTML",
    )

    text, kb = format_fix_broadcast_message()
    sent = 0
    failed = 0

    for idx, uid in enumerate(targets, start=1):
        try:
            await bot.send_message(chat_id=uid, text=text, reply_markup=kb, parse_mode="HTML")
            sent += 1
        except (TelegramForbiddenError, TelegramAPIError):
            failed += 1
        except Exception as exc:
            failed += 1
            logger.debug("Failed sending fix broadcast to %s: %s", uid, exc)

        await asyncio.sleep(0.04)

        if idx % 50 == 0 or idx == total:
            try:
                await status_msg.edit_text(
                    f"🚀 <b>Broadcasting Fix Message to {total:,} users...</b>\n"
                    f"Progress: {idx}/{total}\n"
                    f"✅ Sent: {sent} | 🚫 Failed: {failed}",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    await callback.message.answer(
        f"🏁 <b>Fix Broadcast Complete!</b>\n\n"
        f"👥 Total Targeted: <code>{total:,}</code>\n"
        f"✅ Delivered: <code>{sent:,}</code>\n"
        f"🚫 Inactive/Blocked: <code>{failed:,}</code>",
        parse_mode="HTML",
    )

