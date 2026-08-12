import asyncio
import html
import logging
import math

from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import Database
from config import settings


router = Router(name="club_renewal")
logger = logging.getLogger(__name__)

def build_renewal_warning(
    lang: str,
    days_left: int,
    expires_at,
    full_name: str = "Champion",
    gender: str = "MALE"
):
    builder = InlineKeyboardBuilder()

    lang = lang.upper() if lang else "EN"
    if lang not in {"AM", "EN"}:
        lang = "EN"

    gender = gender.upper() if gender else "MALE"

    first_name = (
        full_name.strip().split()[0].capitalize()
        if full_name
        else ("ሻምፒዮን" if lang == "AM" else "Champion")
    )

    expiry = expires_at.strftime("%Y-%m-%d")

    # ─────────────────────────────────────────────
    # AMHARIC
    # ─────────────────────────────────────────────
    if lang == "AM":

        if gender == "FEMALE":

            if days_left <= 1:
                    urgency = (
                        f"🚨 <b>{first_name}፣ ዛሬ የክለብ አባልነትሽ "
                        f"የመጨረሻ ቀን ነው!</b>"
                    )
            else:
                urgency = (
                    f"⏳ <b>{first_name}፣ የክለብ አባልነትሽ "
                    f"{days_left} ቀናት ብቻ ቀርቶታል</b>"
                )

            personal_intro = (
                f"{first_name} 👋 ኮች ሂላዌ ነኝ። "
                f"ከእኛ ጋር በ<b>Hilawe Transformation Club</b> "
                f"ውስጥ አንድ ወር ሙሉ ልትሞይ ቀርበሻል።\n\n"
                f"በዚህ ጊዜ የአባላትን ምግብ፣ ስፖርት፣ "
                f"የዕለት ተዕለት progress እና ጥያቄዎች "
                f"እያየሽ ከcommunityው ጋር ተጓዝሻል።"
            )

            ending = (
                f"🔥 <b>{first_name}፣ አሁን ያለሽን momentum "
                f"በዚህ ቦታ ላይ አታቋርጪ።</b>\n\n"
                f"አሁኑኑ ካደስሽ የቀሩሽ ቀናት <b>አይጠፉም</b>። "
                f"አዲሱ 30 ቀን አሁን ያለሽ አባልነት "
                f"ካበቃ በኋላ በቀጥታ ይጨመራል።"
            )

            button_text = "🔄 አባልነቴን ለ30 ቀን ላድስ — 299 ብር"

        else:

            if days_left <= 1:
                    urgency = (
                        f"🚨 <b>{first_name}፣ ዛሬ የክለብ አባልነትህ "
                        f"የመጨረሻ ቀን ነው!</b>"
                    )
            else:
                urgency = (
                    f"⏳ <b>{first_name}፣ የክለብ አባልነትህ "
                    f"{days_left} ቀናት ብቻ ቀርቶታል</b>"
                )

            personal_intro = (
                f"{first_name} 👋 ኮች ሂላዌ ነኝ። "
                f"ከእኛ ጋር በ<b>Hilawe Transformation Club</b> "
                f"ውስጥ አንድ ወር ሙሉ ልትሞላ ቀርበሃል።\n\n"
                f"በዚህ ጊዜ የአባላትን ምግብ፣ ስፖርት፣ "
                f"የዕለት ተዕለት progress እና ጥያቄዎች "
                f"እያየህ ከcommunityው ጋር ተጓዝሃል።"
            )

            ending = (
                f"🔥 <b>{first_name}፣ አሁን ያለህን momentum "
                f"በዚህ ቦታ ላይ አታቋርጥ።</b>\n\n"
                f"አሁኑኑ ካደስክ የቀሩህ ቀናት <b>አይጠፉም</b>። "
                f"አዲሱ 30 ቀን አሁን ያለህ አባልነት "
                f"ካበቃ በኋላ በቀጥታ ይጨመራል።"
            )

            button_text = "🔄 አባልነቴን ለ30 ቀን ላድስ — 299 ብር"

        text = (
            f"{urgency}\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"

            f"{personal_intro}\n\n"

            f"📅 <b>የአባልነትህ/ሽ ማብቂያ፦</b> "
            f"<code>{expiry}</code>\n"
            f"⏳ <b>ቀሪ ጊዜ፦ {days_left} ቀን</b>\n\n"

            f"አባልነቱ ሲያበቃ፣\n"
            f"• 👥 የprivate community access\n"
            f"• 🔥 የዕለት ተዕለት accountability\n"
            f"• 🎥 ከኮች ሂላዌ ጋር Live Sessions\n"
            f"• 💬 የአባላት ድጋፍና ልምድ\n"
            f"ይቋረጣሉ።\n\n"

            f"{ending}\n\n"

            f"💳 <b>የ30 ቀን እድሳት፦ 299 ብር ብቻ</b>\n\n"
            f"👇 <b>ከታች ባለው ቁልፍ አባልነትዎን ያድሱ።</b>"
        )

    # ─────────────────────────────────────────────
    # ENGLISH
    # ─────────────────────────────────────────────
    else:

        if days_left <= 1:
            urgency = (
                f"🚨 <b>{first_name.upper()}, THIS IS YOUR FINAL DAY IN THE CLUB</b>"
            )
        else:
            urgency = (
                f"⏳ <b>{first_name.upper()}, YOU HAVE ONLY "
                f"{days_left} DAYS LEFT</b>"
            )

        text = (
            f"{urgency}\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"

            f"{first_name} 👋 Coach Hilawe here.\n\n"

            f"You've now spent almost a full month inside the "
            f"<b>Hilawe Transformation Club</b> with us.\n\n"

            f"You've seen members sharing their workouts, meals, "
            f"questions, struggles and progress every day — and you've "
            f"been part of that journey too.\n\n"

            f"📅 <b>Your current membership ends:</b> "
            f"<code>{expiry}</code>\n"
            f"⏳ <b>Time remaining: {days_left} day(s)</b>\n\n"

            f"When your membership expires, your access to:\n"
            f"• 👥 The private Transformation Club\n"
            f"• 🔥 Daily accountability\n"
            f"• 🎥 Weekly live sessions with Coach Hilawe\n"
            f"• 💬 Member support and shared progress\n"
            f"will stop.\n\n"

            f"🔥 <b>{first_name}, don't stop the momentum you've "
            f"already built.</b>\n\n"

            f"If you renew now, you lose <b>ZERO</b> of your remaining "
            f"days. Your next 30 days are simply added after your "
            f"current membership ends.\n\n"

            f"💳 <b>30-Day Renewal: 299 ETB</b>\n\n"

            f"Tap below and keep going. 👇"
        )

        button_text = "🔄 Renew My 30 Days — 299 ETB"

    builder.button(
        text=button_text,
        callback_data="renew_club_subscription"
    )

    return text, builder.as_markup()


# ─────────────────────────────────────────────
# ADMIN COMMAND
# /club_renewals
# ─────────────────────────────────────────────
@router.callback_query(
    F.data == "club_renewal_dashboard_preview"
)
async def dashboard_renewal_preview(
    callback: types.CallbackQuery,
    db: Database
):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return await callback.answer(
            "⚠️ Access Denied.",
            show_alert=True
        )

    targets = await db._pool.fetch("""
        SELECT
            cs.user_id,
            cs.expires_at,
            COALESCE(u.language, 'EN') AS language,
            COALESCE(u.full_name, 'Champion') AS full_name,
            COALESCE(u.gender, 'MALE') AS gender
        FROM club_subscriptions cs
        JOIN users u
          ON u.telegram_id = cs.user_id

        WHERE cs.is_active = TRUE
  AND cs.expires_at > NOW()
  AND cs.expires_at <= NOW() + INTERVAL '4 days'

  AND (
      cs.renewal_warning_sent_at IS NULL
      OR cs.renewal_warning_sent_at <= NOW() - INTERVAL '12 hours'
  )

  AND NOT EXISTS (
              SELECT 1
              FROM club_payments cp
              WHERE cp.user_id = cs.user_id
                AND cp.status = 'pending'
                AND cp.payment_type = 'renewal'
          )

        ORDER BY cs.expires_at ASC
    """)

    total = len(targets)

    potential_revenue = total * 299

    text = (
        "⚠️ <b>CLUB RENEWAL WARNING PREVIEW</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Members due warning: <code>{total}</code>\n"
        f"💰 Potential renewals: <code>{potential_revenue:,} ETB</code>\n\n"
        "Target rules:\n"
        "• Active member\n"
        "• 4 days or less remaining\n"
"• Last reminder was at least 12 hours ago\n"
"• No pending renewal payment\n\n"
        "Choose an action:"
    )

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🧪 Preview EN + AM",
        callback_data="club_renewal_preview"
    )

    kb.button(
        text=f"🚀 Send to {total} Members",
        callback_data="club_renewal_launch"
    )

    kb.button(
        text="⬅️ Back to Community",
        callback_data="refresh_club_stats"
    )

    kb.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

    await callback.answer()
    
@router.message(
    Command("club_renewals"),
    F.from_user.id.in_(settings.ADMIN_IDS)
)
async def club_renewal_preview(
    message: types.Message,
    db: Database
):

    stats = await db._pool.fetchrow("""
        SELECT
            COUNT(*) FILTER (
                WHERE is_active = TRUE
                  AND expires_at > NOW()
                  AND expires_at <= NOW() + INTERVAL '4 days'
            )::INT AS due,

            COUNT(*) FILTER (
                WHERE is_active = TRUE
                  AND expires_at <= NOW()
            )::INT AS expired

        FROM club_subscriptions
    """)

    pending = await db._pool.fetchval("""
        SELECT COUNT(*)
        FROM club_payments
        WHERE status = 'pending'
          AND payment_type = 'renewal'
    """)

    due = stats["due"] or 0

    expected = due * 299

    preview = (
        "🔄 <b>CLUB RENEWAL BROADCAST</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ Expiring within 4 days: <code>{due}</code>\n"
        f"💳 Pending renewals: <code>{pending}</code>\n"
        f"❌ Already expired: <code>{stats['expired']}</code>\n\n"
        f"💰 Maximum immediate renewal value:\n"
        f"<code>{expected:,} ETB</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Only active members with ≤4 days remaining "
        "will receive this message."
    )

    builder = InlineKeyboardBuilder()

    builder.button(
        text="🧪 Preview Message",
        callback_data="club_renewal_preview"
    )

    builder.button(
        text=f"🚀 Send to {due} Members",
        callback_data="club_renewal_launch"
    )

    builder.button(
        text="❌ Cancel",
        callback_data="club_renewal_cancel"
    )

    builder.adjust(1)

    await message.answer(
        preview,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(
    F.data == "club_renewal_preview"
)
async def preview_renewal_message(
    callback: types.CallbackQuery
):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return

    from datetime import datetime, timedelta, timezone

    fake_expiry = (
        datetime.now(timezone.utc)
        + timedelta(days=3)
    )

    en_text, en_kb = build_renewal_warning(
        "EN",
        3,
        fake_expiry
    )

    am_text, am_kb = build_renewal_warning(
        "AM",
        3,
        fake_expiry
    )

    await callback.message.answer(
        "🇬🇧 <b>ENGLISH</b>",
        parse_mode="HTML"
    )

    await callback.message.answer(
        en_text,
        reply_markup=en_kb,
        parse_mode="HTML"
    )

    await callback.message.answer(
        "🇪🇹 <b>AMHARIC</b>",
        parse_mode="HTML"
    )

    await callback.message.answer(
        am_text,
        reply_markup=am_kb,
        parse_mode="HTML"
    )

    await callback.answer()


@router.callback_query(
    F.data == "club_renewal_cancel"
)
async def cancel_renewal_broadcast(
    callback: types.CallbackQuery
):
    await callback.message.edit_text(
        "❌ Renewal broadcast cancelled."
    )

    await callback.answer()


@router.callback_query(
    F.data == "club_renewal_launch"
)
async def launch_renewal_broadcast(
    callback: types.CallbackQuery,
    db: Database,
    bot: Bot
):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return

    await callback.answer()

    targets = await db._pool.fetch("""
        SELECT
            cs.user_id,
            cs.expires_at,
            COALESCE(u.language, 'EN') AS language,
            u.full_name,
            COALESCE(u.gender, 'MALE') AS gender
        FROM club_subscriptions cs
        JOIN users u
          ON u.telegram_id = cs.user_id

        WHERE cs.is_active = TRUE
  AND cs.expires_at > NOW()
  AND cs.expires_at <= NOW() + INTERVAL '4 days'

  AND (
      cs.renewal_warning_sent_at IS NULL
      OR cs.renewal_warning_sent_at <= NOW() - INTERVAL '12 hours'
  )

  AND NOT EXISTS (
      SELECT 1
      FROM club_payments cp
      WHERE cp.user_id = cs.user_id
        AND cp.status = 'pending'
        AND cp.payment_type = 'renewal'
  )

        ORDER BY cs.expires_at ASC
    """)

    total = len(targets)

    await callback.message.edit_text(
        f"🚀 Sending renewal warnings to "
        f"<code>{total}</code> members...",
        parse_mode="HTML"
    )

    success = 0
    failed = 0

    for member in targets:

        uid = member["user_id"]

        seconds_left = (
            member["expires_at"].timestamp()
            - __import__("time").time()
        )

        days_left = max(
            1,
            math.ceil(
                seconds_left / 86400
            )
        )

        text, markup = build_renewal_warning(
    lang=member["language"],
    days_left=days_left,
    expires_at=member["expires_at"],
    full_name=member["full_name"],
    gender=member["gender"]
)

        try:

            await bot.send_message(
                chat_id=uid,
                text=text,
                reply_markup=markup,
                parse_mode="HTML"
            )

            await db._pool.execute("""
                UPDATE club_subscriptions
                SET
                    auto_renew_reminded = TRUE,
                    renewal_warning_sent_at = NOW(),
                    updated_at = NOW()
                WHERE user_id = $1
            """, uid)

            success += 1

        except Exception as exc:

            logger.warning(
                f"Renewal warning failed for {uid}: "
                f"{exc}"
            )

            failed += 1

        await asyncio.sleep(0.07)

    await callback.message.answer(
        "🏁 <b>RENEWAL BROADCAST COMPLETE</b>\n\n"
        f"✅ Delivered: <code>{success}</code>\n"
        f"❌ Failed: <code>{failed}</code>",
        parse_mode="HTML"
    )
    


async def enforce_expired_club_members(
    bot: Bot,
    db: Database
):
    """
    Runs periodically.

    Expired:
        is_active -> FALSE
        remove from Telegram group
        send renewal CTA
    """

    rows = await db._pool.fetch("""
        SELECT
            cs.user_id,
            cs.expires_at,
            COALESCE(u.gender, 'MALE') AS gender,
            COALESCE(u.language, 'EN') AS language,
            u.full_name
        FROM club_subscriptions cs
        JOIN users u
          ON u.telegram_id = cs.user_id

        WHERE cs.is_active = TRUE
          AND cs.expires_at IS NOT NULL
          AND cs.expires_at <= NOW()
    """)

    for member in rows:

        uid = member["user_id"]
        lang = member["language"]

        try:
            await bot.ban_chat_member(
                chat_id=settings.CLUB_GROUP_ID,
                user_id=uid
            )

            await bot.unban_chat_member(
                chat_id=settings.CLUB_GROUP_ID,
                user_id=uid
            )

        except Exception as exc:
            logger.warning(
                f"Could not remove expired member {uid}: {exc}"
            )
            continue   # retry next hourly cycle


    # Only mark inactive AFTER successful removal
    await db._pool.execute("""
        UPDATE club_subscriptions
        SET
            is_active = FALSE,
            expired_notice_sent_at = NOW(),
            updated_at = NOW()
        WHERE user_id = $1
        AND is_active = TRUE
    """, uid)

    builder = InlineKeyboardBuilder()

    if lang.upper() == "AM":

        text = (
            "⛔ <b>የክለብ አባልነትዎ አብቅቷል</b>\n\n"
            "የ30 ቀን Hilawe Transformation Club "
            "አባልነትዎ ተጠናቋል።\n\n"
            "እንደገና ወደ community ለመመለስ፣ "
            "Live sessions፣ የአባላት ድጋፍና "
            "accountability ለማግኘት አባልነትዎን "
            "ለሌላ 30 ቀን ማደስ ይችላሉ።\n\n"
            "💳 <b>299 ብር / 30 ቀን</b>"
        )

        button = "🔄 አባልነቴን አድስ — 299 ብር"

    else:

        text = (
            "⛔ <b>YOUR CLUB MEMBERSHIP HAS EXPIRED</b>\n\n"
            "Your 30-day Hilawe Transformation Club "
            "membership has ended.\n\n"
            "Renew to return to the community, weekly "
            "live sessions, accountability and member support.\n\n"
            "💳 <b>299 ETB / 30 days</b>"
        )

        button = "🔄 Restore My Membership — 299 ETB"

    builder.button(
        text=button,
        callback_data="renew_club_subscription"
    )

    try:

        await bot.send_message(
            chat_id=uid,
            text=text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

    except Exception as exc:

        logger.warning(
            f"Expiry notice failed for {uid}: {exc}"
        )

    await asyncio.sleep(0.07)
    
        


# async def club_expiry_loop(
#     bot: Bot,
#     db: Database
# ):
#     while True:

#         try:
#             await enforce_expired_club_members(
#                 bot,
#                 db
#             )

#         except Exception as exc:
#             logger.exception(
#                 f"Club expiry engine error: {exc}"
#             )

#         # Once per hour
#         await asyncio.sleep(3600)