import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from database.db import Database
from config import settings

logger = logging.getLogger(__name__)
router = Router(name="daily_missions")

ADDIS_TZ = ZoneInfo("Africa/Addis_Ababa")

# ─────────────────────────────────────────
# PSYCHOLOGICAL WEEKLY MISSIONS (AMHARIC VOICE)
# Dynamic split targets to hit both Fat Loss & Muscle Gain groups.
# ─────────────────────────────────────────
WEEKLY_MISSIONS = {
    0: { # Monday
        "text": (
            "🚀 <b>ሚሽን ሰኞ — አዲስ ጅምር (Fresh Start!)</b>\n\n"
            "ሳምንቱን በድል ለመጀመር የዛሬ ግዴታዎቻችን እነዚህ ናቸው፦\n\n"
            "🏃‍♂️ <b>ለሁላችሁም፦</b> ዛሬ ቢያንስ 3 ሊትር ውሃ መጠጣት!\n"
            "🥗 <b>ለFat Loss ቡድን፦</b> ዛሬ ምንም አይነት በሰው ሰራሽ ስኳር የበለፀገ መጠጥ ወይም ጣፋጭ ነገር አለመንካት።\n"
            "💪 <b>ለMuscle/Weight Gain ቡድን፦</b> 3 ዋና ምግቦችን በሰዓቱ መመገብ (ፕሮቲን ማካተት እንዳይረሱ)።\n\n"
            "⚡️ <b>ለማረጋገጥ፦</b> የዛሬውን ተግባር ሲጀምሩ ወይም ሲያጠናቅቁ <b>'ዝግጁ'</b> ወይም <b>'Done'</b> ብለው ሪፕላይ ያድርጉ! 👇"
        )
    },
    1: { # Tuesday
        "text": (
            "🔥 <b>ሚሽን ማክሰኞ — የእንቅስቃሴ ቀን (Keep Moving!)</b>\n\n"
            "ትናንት የነበረውን ጉልበት ዛሬም እንቀጥላለን።\n\n"
            "🏃‍♂️ <b>ለሁላችሁም፦</b> ዛሬ 10,000 እርምጃ (10k steps) መሙላት ወይም ለ30 ደቂቃ ያህል ቀለል ያለ ፈጣን የእግር ጉዞ ማድረግ።\n\n"
            "💬 ዛሬ ከተቀመጡበት ተነስተው ሰውነትዎን ያንቀሳቅሱ! ስራ ቦታም ቢሆኑ ደረጃዎችን ይጠቀሙ።\n\n"
            "⚡️ <b>ለማረጋገጥ፦</b> መልመጃውን ሲያጠናቅቁ ለዚህ መልዕክት <b>'ዝግጁ'</b> ብለው ምላሽ ይስጡ! 👇"
        )
    },
    2: { # Wednesday
        "text": (
            "🎥 <b>ሚሽን ረቡዕ — የLive Session እና የቤት ውስጥ ወርካውት!</b>\n\n"
            "ዛሬ ልዩ ቀን ነው! ማታ የቀጥታ ስርጭት (Live Meeting) ይኖረናል።\n\n"
            "🏋️‍♂️ <b>የዛሬው ስፖርት፦</b> 3 ዙር (15 Push-ups፣ 20 Squats እና 30 ሰከንድ Plank) በቤትዎ ውስጥ ይስሩ።\n\n"
            "🚨 <b>ጠቃሚ ማሳሰቢያ፦</b> ማታ በምናደርገው የቀጥታ ውይይት ላይ Coach Hilawe ጥያቄዎቻችሁን በቀጥታ ይመልሳል። ጥያቄ ካላችሁ አሁኑኑ Q&A ክፍል ላይ አስቀምጡ!\n\n"
            "⚡️ <b>ለማረጋገጥ፦</b> ስፖርቱን ሰርተው ሲጨርሱ <b>'ዝግጁ'</b> ብለው ይጻፉ! 👇"
        )
    },
    3: { # Thursday
        "text": (
            "🥗 <b>ሚሽን ሐሙስ — የምግብ ቁጥጥር (Diet Discipline)</b>\n\n"
            "ስፖርት ብቻውን ለውጥ አያመጣም፤ ዋናው ስራ የሚሰራው ማዕድ ቤት ነው!\n\n"
            "🛑 <b>ለሁላችሁም፦</b> ዛሬ ምሽት ከምሽቱ 2:00 ሰዓት (8:00 PM) በኋላ ምንም አይነት ከባድ ምግብ አለመመገብ።\n"
            "💧 ረሃብ ከተሰማዎት ውሃ ወይም ያለ ስኳር አረንጓዴ ሻይ (Green Tea) ይጠጡ።\n\n"
            "⚡️ <b>ለማረጋገጥ፦</b> ይህንን ስነ-ስርዓት ለመጠበቅ ቃል የገቡ አሁኑኑ <b>'ዝግጁ'</b> ብለው ይመዝገቡ👇"
        )
    },
    4: { # Friday
        "text": (
            "🌟 <b>ሚሽን አርብ — ማህበረሰባዊ ቁርጠኝነት (Family Support)</b>\n\n"
            "ብቻችንን ፈጣን ልንሆን እንችላለን፤ በጋራ ግን ሩቅ እንጓዛለን!\n\n"
            "👥 <b>የዛሬው ተልዕኮ፦</b> ዛሬ ከቤተሰብዎ፣ ከባልደረባዎ ወይም ከጓደኛዎ ጋር ለ30 ደቂቃ አብረው ይራመዱ። በfitness ጉዟችን ሌሎችንም እናነሳሳለን።\n\n"
            "⚡️ <b>ለማረጋገጥ፦</b> የእግር ጉዞውን ሲጨርሱ <b>'ዝግጁ'</b> ብለው ሪፕላይ ያድርጉ! 👇"
        )
    },
    5: { # Saturday
        "text": (
            "📸 <b>ሚሽን ቅዳሜ — የቅዳሜ ፈተና (Weekend Shield)</b>\n\n"
            "ብዙ ሰዎች ቅዳሜና እሁድ ላይ Cheat በማድረግ የሳምንቱን ልፋት ያበላሻሉ! እኛ ግን አንበላሽም።\n\n"
            "🍽 <b>የዛሬው ተልዕኮ፦</b> ዛሬ የሚመገቡትን ምርጥ እና ጤናማ ምግብ ፎቶ አንስተው እዚህ ግሩፕ ላይ ይላኩ። እርስ በርስ እንማማር!\n\n"
            "⚡️ <b>ለማረጋገጥ፦</b> የጤናማ ምግባችሁን ፎቶ ስትልኩ ተልዕኮው በራስ-ሰር ይጸድቃል! 🔥"
        )
    },
    6: { # Sunday
        "text": (
            "🔋 <b>ሚሽን እሁድ — እረፍት እና ቀጣይ እቅድ (Rest & Reset)</b>\n\n"
            "ዛሬ ሰውነትዎ እንዲያገግም እረፍት ይስጡት። ነገር ግን አእምሮዎን ለሚቀጥለው ሳምንት ያዘጋጁ።\n\n"
            "📝 <b>የዛሬው ተግባር፦</b> 10 ደቂቃ ወስደው በሚቀጥለው ሳምንት ማሳካት ስለሚፈልጉት የሰውነት ለውጥ ያስቡ እና ማስታወሻ ደብተርዎ ላይ ይጻፉ።\n\n"
            "🚨 <b>ከምሽቱ 3:00 ሰዓት ላይ፦</b> የሳምንቱ የጀግኖች ሰንጠረዥ (Leaderboard) ይፋ ይሆናል! ማን ቀዳሚ ይሆን?\n\n"
            "⚡️ <b>ለማረጋገጥ፦</b> ለቀጣዩ ሳምንት አእምሮአዊ ዝግጅት ካደረጉ <b>'ዝግጁ'</b> ይበሉ👇"
        )
    },
}

# Dynamic keywords configuration - can easily be extended or pulled from a settings/DB layer
VALID_KEYWORDS = ["ዝግጁ", "done", "ready", "አጠናቅቄያለሁ", "ጀመርኩ", "አጠናቀቅኩ", "እኔ", "yes"]

DAILY_MISSION_THREAD_ID = 4  # የዕለቱ ተልዕኮ topic thread ID


# ─────────────────────────────────────────
# CORE: POST DAILY MISSION
# ─────────────────────────────────────────
async def post_daily_mission(bot: Bot, db: Database):
    try:
        today = datetime.now(ADDIS_TZ).weekday()
        mission = WEEKLY_MISSIONS.get(today)
        if not mission:
            logger.warning(f"No mission configured for weekday {today}")
            return

        await bot.send_message(
            chat_id=settings.CLUB_GROUP_ID,
            message_thread_id=DAILY_MISSION_THREAD_ID,
            text=mission["text"],
            parse_mode="HTML"
        )
        logger.info(f"Daily mission posted for weekday {today}")
    except Exception as e:
        logger.error(f"Failed to post daily mission: {e}")


# ─────────────────────────────────────────
# CORE: POST SUNDAY LEADERBOARD (FOMO GENERATOR)
# ─────────────────────────────────────────
async def post_weekly_leaderboard(bot: Bot, db: Database):
    try:
        rows = await db._pool.fetch("""
            SELECT u.full_name, COUNT(*) as days
            FROM club_checkins c
            JOIN users u ON u.telegram_id = c.user_id
            WHERE c.checkin_date >= CURRENT_DATE - INTERVAL '6 days'
            GROUP BY u.full_name
            ORDER BY days DESC, max(c.checkin_date) ASC
            LIMIT 10
        """)

        if not rows:
            logger.info("No check-ins this week, skipping leaderboard.")
            return

        medals = ["🥇", "🥈", "🥉"]
        lines = [
            "📊 <b>የሳምንቱ የጀግኖች ሰንጠረዥ (Weekly Consistency Leaderboard)</b>\n",
            "በዚህ ሳምንት አንድም ቀን ሳይዛነፉ እለታዊ ሚሽኖችን በትጋት ያጠናቀቁ የክለባችን ምርጥ አትሌቶች፦\n"
        ]

        for i, row in enumerate(rows):
            name = row['full_name'] or "አትሌት"
            days = row['days']
            medal = medals[i] if i < 3 else f"{i + 1}."
            fire = "🔥" if days == 7 else "💪" if days >= 5 else "👍"
            lines.append(f"{medal} {name} — {days}/7 ቀናት {fire}")

        lines.append(
            "\n💥 ቀጣይነት ለውጥ ያመጣል! "
            "በሚቀጥለው ሳምንት በዚህ ሰንጠረዥ ላይ ማን ቀዳሚ ይሆናል? በርትቱ! 🏋️‍♂️"
        )

        await bot.send_message(
            chat_id=settings.CLUB_GROUP_ID,
            message_thread_id=DAILY_MISSION_THREAD_ID,
            text="\n".join(lines),
            parse_mode="HTML"
        )
        logger.info("Weekly leaderboard posted.")
    except Exception as e:
        logger.error(f"Failed to post leaderboard: {e}")

from datetime import datetime, timezone, timedelta
import asyncio

# ─────────────────────────────────────────
# DEFINING THE TIMEZONE (BUILT-IN & RELIABLE)
# ─────────────────────────────────────────
# Addis Ababa is permanently UTC+3
ADDIS_TZ = timezone(timedelta(hours=3))

# ─────────────────────────────────────────
# SCHEDULER LOOP (RUNS ASYNCHRONOUSLY)
# ─────────────────────────────────────────
async def daily_mission_loop(bot: Bot, db: Database):
    last_mission_date = None
    last_leaderboard_date = None

    while True:
        try:
            # Forces the current time into Addis Ababa time, bypassing Render's clock
            now = datetime.now(ADDIS_TZ)

            # Post mission at 6:00 AM every day Addis time
            if now.hour == 6 and now.minute == 0:
                today = now.date()
                if last_mission_date != today:
                    await post_daily_mission(bot, db)
                    last_mission_date = today

            # Post leaderboard at 9:00 PM every Sunday (Weekday 6) Addis time
            if now.weekday() == 6 and now.hour == 21 and now.minute == 0:
                today = now.date()
                if last_leaderboard_date != today:
                    await post_weekly_leaderboard(bot, db)
                    last_leaderboard_date = today

        except Exception as e:
            logger.error(f"daily_mission_loop error: {e}")

        await asyncio.sleep(55)
# ─────────────────────────────────────────
# CHECK-IN HANDLER (SOCIAL PROOF INJECTOR)
# ─────────────────────────────────────────
@router.message(
    F.chat.id == settings.CLUB_GROUP_ID,
    F.message_thread_id == DAILY_MISSION_THREAD_ID
)
async def handle_mission_checkin(message: types.Message, db: Database):
    if not message.text:
        return

    user_text = message.text.strip().lower()
    uid = message.from_user.id
    first_name = message.from_user.first_name or "አትሌት"

    # Flexible keyword engine checker
    if not any(kw in user_text for kw in VALID_KEYWORDS):
        return

    today = datetime.now(ADDIS_TZ).date()

    # Prevent double check-in on the same day
    already = await db._pool.fetchval("""
        SELECT 1 FROM club_checkins
        WHERE user_id = $1 AND checkin_date = $2
    """, uid, today)

    if already:
        return  # Silent to eliminate chat spam

    # Log successful check-in
    await db._pool.execute("""
        INSERT INTO club_checkins (user_id, checkin_date)
        VALUES ($1, $2)
        ON CONFLICT DO NOTHING
    """, uid, today)

    # Get overall historical check-in count for this specific user to calculate current milestone
    total_checkins = await db._pool.fetchval("""
        SELECT COUNT(*) FROM club_checkins WHERE user_id = $1
    """, uid) or 1

    # 1. Fire a cool native message reaction
    try:
        await message.react([types.ReactionTypeEmoji(emoji="🔥")])
    except Exception:
        pass

    # 2. Public Text Reply to create intense Social Proof and FOMO for trailing members
    try:
        reply_text = (
            f"🔥 <b>ፈጣን ምላሽ!</b>\n"
            f"ወዳጃችን <b>{first_name}</b> የዛሬውን ተልዕኮ በተሳካ ሁኔታ አጠናቆ አስመዝግቧል! "
            f"(ጠቅላላ የጽናት ጉዞ፦ {total_checkins} ቀናት) 👏\n\n"
            f"የቀራችሁ አባላት ሰዓቱ ሳይረፍድ አሁኑኑ አጠናቅቁና 'ዝግጁ' በማለት አስመዝግቡ! 👇"
        )
        await message.reply(text=reply_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send public check-in reply: {e}")


# ─────────────────────────────────────────
# ADMIN MANUAL TRIGGERS FOR TESTING
# ─────────────────────────────────────────
@router.message(Command("post_mission"), F.from_user.id.in_(settings.ADMIN_IDS))
async def manual_post_mission(message: types.Message, bot: Bot, db: Database):
    await post_daily_mission(bot, db)
    await message.reply("✅ Mission posted.")


@router.message(Command("post_leaderboard"), F.from_user.id.in_(settings.ADMIN_IDS))
async def manual_post_leaderboard(message: types.Message, bot: Bot, db: Database):
    await post_weekly_leaderboard(bot, db)
    await message.reply("✅ Leaderboard posted.")