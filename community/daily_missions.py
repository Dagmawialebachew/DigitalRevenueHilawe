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
    0: {  # Monday: The Momentum Builder
        "text": (
            "⚡️ <b>ሚሽን ሰኞ — የሳምንቱ ሞመንተም (Set The Tone!)</b>\n\n"
            "አዲሱን ሳምንት በከፍተኛ ጉልበት እንጀምራለን! ዛሬ ምንም አይነት ምክንያት አይሰራም።\n\n"
            "💧 <b>ለሁላችሁም (Habit Stack)፦</b> ዛሬ ጠዋት እንደነቁ 2 ትላልቅ ብርጭቆ ውሃ መጠጣት + በቀኑ ውስጥ ቢያንስ 3.5 ሊትር ውሃ መሙላት።\n"
            "🥗 <b>ለFat Loss ቡድን፦</b> ዛሬ ከምሽቱ 1:00 ሰዓት በኋላ ምንም አይነት የካርቦሃይድሬት (ዳቦ፣ እንጀራ፣ ሩዝ) ምግብ አለመንካት።\n"
            "🥩 <b>ለMuscle Gain ቡድን፦</b> ዛሬ በየምግባችሁ ላይ ቢያንስ 2 እንቁላል ወይም አኩሪ አተር/ምስር ማካተት።\n\n"
            "👇 <b>ተልዕኮውን የጀመራችሁ ወይም የጨረሳችሁ፦</b> አሁኑኑ <b>'ዝግጁ'</b> ወይም <b>'Done'</b> ብላችሁ ሪፕላይ በማድረግ የመጀመሪያውን ነጥብ አስመዝግቡ!"
        )
    },
    1: {  # Tuesday: Step & Sweat Overload
        "text": (
            "🔥 <b>ሚሽን ማክሰኞ — የ12,000 እርምጃ ፈተና (Step Boss!)</b>\n\n"
            "ትናንት የጀመርነውን የትጋት ጉልበት ዛሬ በእጥፍ እንጨምረዋለን።\n\n"
            "🚶‍♂️ <b>የዛሬው ዋና ፈተና፦</b> ዛሬ ደረጃውን ከፍ አድርገነዋል! ቢያንስ <b>12,000 እርምጃዎች (12k steps)</b> መራመድ ወይም ለ35 ደቂቃ ያህል ሳያቋርጡ ፈጣን የእግር ጉዞ ማድረግ።\n\n"
            "💡 <i>ምክር፦ ስራ ቦታም ሆናችሁ ታክሲ/መኪና ከምትጠብቁ ጥቂት ርቀት በእግርችሁ ተራመዱ!</i>\n\n"
            "👇 <b>ለማረጋገጥ፦</b> የእግር ጉዞችሁን ስታጠናቅቁ ወይም የቴሌግራም/Pedometer ስክሪንሾት በማያያዝ <b>'ዝግጁ'</b> ብላችሁ ይመልሱ!"
        )
    },
    2: {  # Wednesday: Live Session & Upper Body Push
        "text": (
            "🎥 <b>ሚሽን ረቡዕ — የLive Meeting እና የቤት ውስጥ ስፖርት!</b>\n\n"
            "ዛሬ ልዩ ረቡዕ ነው! ማታ ከኮች ሂላዌ ጋር በይፋዊ <b>Live Meeting</b> ላይ እንገናኛለን።\n\n"
            "🏋️‍♂️ <b>የዛሬው የቤት ውስጥ ወርካውት (4 ዙር)፦</b>\n"
            "▪️ 20 Squats\n"
            "▪️ 15 Push-ups (ጉልበት መሬት ላይ አድርጎ መስራት ይቻላል)\n"
            "▪️ 40 ሰከንድ Plank holding\n\n"
            "🚨 <b>ጥያቄና መልስ፦</b> ማታ በLive Session ላይ Coach Hilawe እንዲመልስላችሁ የምትፈልጉትን ጥያቄ <b>Q&A Desk</b> topic ላይ አስቀምጡ።\n\n"
            "👇 <b>ለማረጋገጥ፦</b> ስፖርቱን ሰርታችሁ ስትጨርሱ <b>'ዝግጁ'</b> ብላችሁ ፃፉ!"
        )
    },
    3: {  # Thursday: Local Protein & Clean Eating
        "text": (
            "🥩 <b>ሚሽን ሐሙስ — የሀበሻ ፕሮቲን ፈተና (Habesha Fuel)</b>\n\n"
            "ውድ የውጭ ምግቦችን ሳንገዛ በቤታችን ባለው የሀበሻ ምግብ ሰውነታችንን እንገነባለን!\n\n"
            "🍽 <b>የዛሬው ተልዕኮ፦</b> ዛሬ በወሰዳችሁት ዋና ምግብ ላይ ከፍተኛ ፕሮቲን ያለው የሀገራችንን ምግብ (ዶሮ፣ ስጋ፣ እንቁላል፣ አተር/ምስር ወጥ) መመገብ እና ከምሽቱ 2:30 በኋላ ምንም አለመብላት።\n\n"
            "🚫 <b>የሚከለከል፦</b> ዛሬ ምንም አይነት የታሸጉ ምግቦች፣ ቺፕሶች ወይም ለስላሳ መጠጦች አይፈቀዱም።\n\n"
            "👇 <b>ለማረጋገጥ፦</b> ይህንን የምግብ ስነ-ስርዓት የጠበቃችሁ አሁኑኑ <b>'ዝግጁ'</b> ብላችሁ አስመዝግቡ!"
        )
    },
    4: {  # Friday: Mental Toughness & Core Shield
        "text": (
            "🛡 <b>ሚሽን አርብ — የጽናት እና የኮር (Abs/Core) ቀን!</b>\n\n"
            "ሳምንቱ ሊጠናቀቅ ሲል ዘና ማለት የለም፤ ጠንካሮች የሚያወጡት በፈተና ወቅት ነው!\n\n"
            "🔥 <b>የዛሬው የሆድና ቦርጭ ማጥፊያ ስፖርት (3 ዙር)፦</b>\n"
            "▪️ 25 Mountain Climbers\n"
            "▪️ 20 Leg Raises\n"
            "▪️ 40 ሰከንድ Wall Sit (ግድግዳ ላይ መደገፍ)\n\n"
            "👇 <b>ለማረጋገጥ፦</b> እያንዳንዱን እንቅስቃሴ አጠናቃችሁ ስትጨርሱ ለዚህ መልዕክት <b>'ዝግጁ'</b> ብላችሁ ሪፕላይ ያድርጉ!"
        )
    },
    5: {  # Saturday: Show Your Plate (Visual Proof)
        "text": (
            "📸 <b>ሚሽን ቅዳሜ — የጤናማ ማዕድ ፎቶ (Show Your Plate!)</b>\n\n"
            "ቅዳሜና እሁድ የብዙዎች የመሰነፍ ቀን ነው—ለእኛ ግን የልዩነት ቀን ነው!\n\n"
            "🥗 <b>የዛሬው የፎቶ ተልዕኮ፦</b> ዛሬ ለቁርስ፣ ለምሳ ወይም ለራት የተመገባችሁትን ጤናማ እና ንጹህ የሀበሻ ምግብ ፎቶ አንስታችሁ እዚህ ግሩፕ ላይ ላኩ።\n\n"
            "💬 <i>የሌሎችን ማዕድ በማየት አዳዲስ ጤናማ የምግብ ሀሳቦችን እንወስዳለን!</i>\n\n"
            "👇 <b>ለማረጋገጥ፦</b> የምግባችሁን ፎቶ ስትልኩ የዛሬው ሚሽናችሁ በራስ-ሰር ይጸድቃል! 📸🔥"
        )
    },
    6: {  # Sunday: Weekly Audit & Leaderboard Launch
        "text": (
            "📊 <b>ሚሽን እሁድ — የሳምንቱ ግምገማ እና የጀግኖች ሰንጠረዥ!</b>\n\n"
            "ያለፈውን 6 ቀን ልፋታችሁን የምታዩበት እና ለቀጣዩ ሳምንት ኃይል የምትሰበስቡበት ቀን ነው።\n\n"
            "📝 <b>የዛሬው ተግባር፦</b> በዚህ ሳምንት ያሳካችሁትን ትልቅ ስኬት ወይም የቀነሳችሁትን ቦርጭ/ክብደት በ1 መስመር ኮሜንት ላይ ጻፉልን።\n\n"
            "🚨 <b>ከምሽቱ 3:00 ሰዓት ላይ፦</b> በዚህ ሳምንት 7ቱንም ቀን ሳይዛነፉ ያጠናቀቁ የሳምንቱ <b>TOP 10 ጀግኖች (Leaderboard)</b> ይፋ ይሆናል!\n\n"
            "👇 <b>ለማረጋገጥ፦</b> የሳምንቱን ጉዞአችሁን ገምግማችሁ ካጠናቀቃችሁ <b>'ዝግጁ'</b> በሉ!"
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
# ─────────────────────────────────────────
# CLEAN REACTION-ONLY CHECK-IN HANDLER
# ─────────────────────────────────────────
@router.message(
    F.chat.id == settings.CLUB_GROUP_ID,
    F.message_thread_id == DAILY_MISSION_THREAD_ID
)
async def handle_mission_checkin(message: types.Message, db: Database):
    """
    Silently tracks member check-ins for ANY post inside the thread (text, photo, video)
    and reacts with a 👍 to confirm without cluttering the group chat.
    """
    uid = message.from_user.id
    today = datetime.now(ADDIS_TZ).date()

    # 1. Prevent double check-in on the exact same day
    already = await db._pool.fetchval("""
        SELECT 1 FROM club_checkins
        WHERE user_id = $1 AND checkin_date = $2
    """, uid, today)

    if already:
        # User already checked in today — react with a subtle thumb up anyway or ignore silently
        try:
            await message.react([types.ReactionTypeEmoji(emoji="👍")])
        except Exception:
            pass
        return

    # 2. Log successful check-in into PostgreSQL
    await db._pool.execute("""
        INSERT INTO club_checkins (user_id, checkin_date)
        VALUES ($1, $2)
        ON CONFLICT DO NOTHING
    """, uid, today)

    # 3. Clean & Silent Confirmation — Thumbs Up Emoji Reaction only!
    try:
        await message.react([types.ReactionTypeEmoji(emoji="👍")])
    except Exception as e:
        logger.error(f"Failed to set 👍 reaction for user {uid}: {e}")

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