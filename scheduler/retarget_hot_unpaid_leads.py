"""
High-Converting Hot Leads Recovery Engine (Last 7 Days Unpaid Onboarded Users).
Audience: 744 users who finished onboarding this week, received Profile Card, but haven't paid.
Persona: 100% Coach Hilawe Native Addis Amharic (brother-to-brother / brother-to-sister, pure conjugation, exact intake injections).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

# Fix Windows console UTF-8 encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import settings
from database.db import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("HOT_LEADS_RECOVERY")


def get_fallback_product_id(lang: str, gender: str, level: str, freq: int) -> int:
    """
    Guarantees a clean 949 ETB product match for all intake combinations.
    """
    lang = (lang or "AM").upper()
    gender = (gender or "MALE").upper()
    freq = freq if freq in (3, 4, 5) else 3

    if gender == "FEMALE":
        # Female products in catalog (all 949 ETB)
        if lang == "AM":
            mapping = {3: 8, 4: 16, 5: 25}
        else:
            mapping = {3: 7, 4: 12, 5: 21}
        return mapping.get(freq, 8 if lang == "AM" else 7)

    # Male products in catalog (all 949 ETB)
    lvl = (level or "BEGINNER").upper()
    if lang == "AM":
        if "ADVANCED" in lvl:
            mapping = {3: 6, 4: 15, 5: 24}
        elif "INTERMEDIATE" in lvl:
            mapping = {3: 5, 4: 14, 5: 23}
        else:
            mapping = {3: 4, 4: 13, 5: 22}
        return mapping.get(freq, 4)
    else:
        if "ADVANCED" in lvl:
            mapping = {3: 3, 4: 11, 5: 19}
        elif "INTERMEDIATE" in lvl:
            mapping = {3: 2, 4: 10, 5: 18}
        else:
            mapping = {3: 1, 4: 9, 5: 17}
        return mapping.get(freq, 1)


def render_hot_lead_message(user: Dict[str, Any]) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Renders an intensely personalized message from Coach Hilawe injecting:
    - Name
    - Gender (exact male vs female conjugation)
    - Frequency (3, 4, 5 days)
    - Goal (Muscle, Fat loss, Athlete)
    - Obstacle (Diet, Inconsistency, Lack of Structure)
    """
    full_name = user.get("full_name") or ""
    import html
    first_name = html.escape(full_name.strip().split()[0].capitalize()) if full_name else ""

    lang = (user.get("language") or "AM").upper()
    if lang not in ("AM", "EN"):
        lang = "AM"

    raw_gender = (user.get("gender") or "MALE").upper()
    is_female = "FEMALE" in raw_gender

    freq = user.get("frequency") or 3
    if freq not in (3, 4, 5):
        freq = 3

    goal = (user.get("goal") or "MUSCLE").upper()
    obstacle = (user.get("obstacle") or "DIET").upper()
    level = user.get("level") or "BEGINNER"

    product_id = user.get("product_id") or get_fallback_product_id(lang, "FEMALE" if is_female else "MALE", level, freq)

    if lang == "AM":
        # ──────────────────────────────────────────────────────────
        # AMHARIC PERSONALIZATION (Native Addis Coach Hilawe Voice)
        # ──────────────────────────────────────────────────────────
        if is_female:
            greeting = f"{first_name} እህቴ እንዴት ነሽ? አሰልጣኝ ህላዌ ነኝ። 🤝" if first_name else "እህቴ እንዴት ነሽ? አሰልጣኝ ህላዌ ነኝ። 🤝"

            # Goal phrasing (Female)
            if "FATLOSS" in goal:
                goal_phrased = "ያለሽን ቦርጭ አጥፍተሽ ቅርጽሽን ለመያዝ"
            elif "MUSCLE" in goal:
                goal_phrased = "ጡንቻሽን አጠንክረሽ ቅርጽሽን ለማጉላት"
            else:
                goal_phrased = "የአትሌት ብቃትና ጥንካሬሽን ለማሳደግ"

            # Obstacle phrasing (Female)
            if "DIET" in obstacle:
                obs_phrased = "የአመጋገብ ስርዓትሽን ለማስተካከል"
            elif "CONSISTENCY" in obstacle:
                obs_phrased = "የተነሳሽነትና የወጥነት ችግርሽን ለመቅረፍ"
            else:
                obs_phrased = "ግልጽ የሆነ የተዋቀረ እቅድ አግኝተሽ ለመስራት"

            text = (
                f"<b>{greeting}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"በዚህ ሳምንት እኮ ቦቱ ላይ የሰውነት መረጃሽን በሙሉ ሰጥተሽኝ ነበር።\n\n"
                f"በሳምንት <b>{freq} ቀን</b> ሰርተሽ <b>{goal_phrased}</b> እና <b>{obs_phrased}</b> "
                f"ለአንቺ ብቻ የተበጀውን የ8-ሳምንት የልምምድ ፕሮግራም በስነስርዓት አዘጋጅቼ ጨርሼ ነበር።\n\n"
                f"ግን የሰውነት መገለጫሽን (Profile Card) አይተሽ... ክፍያውን ሳትፈጽሚ ዝም አልሽኝ።\n\n"
                f"እህቴ እውነቱን እንነጋገር፦ ሰውነትሽን ለመቀየርና ቅርጽሽን ለመያዝ የወሰንሽው በዚህ ሳምንት ነበር። "
                f"በየቀኑ ማዘግየትና 'ሰኞ እጀምራለሁ' እያሉ በቁጭት መኖር የትም አያደርስሽም።\n\n"
                f"እኔ ቃሌን አክብሬ ፕሮግራምሽን አዘጋጅቼ ጨርሻለሁ፤ አሁን ውሳኔው የአንቺ ነው።\n\n"
                f"ከታች ያለውን ቁልፍ ተጭነሽ የ8-ሳምንት ፕሮግራምሽን አሁኑኑ ክፈቺና እንጀምር፦ 👇"
            )

            btn_text = "⚡️ የ8-ሳምንት ፕሮግራሜን ልክፈት (949 ብር)"

        else:
            # Male Conjugation
            greeting = f"{first_name} ወንድሜ ሰላም ነህ? አሰልጣኝ ህላዌ ነኝ። 🤝" if first_name else "ወንድሜ ሰላም ነህ? አሰልጣኝ ህላዌ ነኝ። 🤝"

            # Goal phrasing (Male)
            if "FATLOSS" in goal:
                goal_phrased = "ያለህን ቦርጭ አጥፍተህ ቅርጽህን ለመያዝ"
            elif "MUSCLE" in goal:
                goal_phrased = "ጠንካራ ጡንቻ ገንብተህ ሰውነትህን ለመቀየር"
            else:
                goal_phrased = "የአትሌት ብቃትና ጥንካሬህን ለማሳደግ"

            # Obstacle phrasing (Male)
            if "DIET" in obstacle:
                obs_phrased = "የአመጋገብ ስርዓትህን ለማስተካከል"
            elif "CONSISTENCY" in obstacle:
                obs_phrased = "የተነሳሽነትና የወጥነት ችግርህን ለመቅረፍ"
            else:
                obs_phrased = "ግልጽ የሆነ የተዋቀረ እቅድ አግኝተህ ለመስራት"

            text = (
                f"<b>{greeting}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"በዚህ ሳምንት እኮ ቦቱ ላይ የሰውነት መረጃህን በሙሉ ሰጥተኸኝ ነበር።\n\n"
                f"በሳምንት <b>{freq} ቀን</b> ሰርተህ <b>{goal_phrased}</b> እና <b>{obs_phrased}</b> "
                f"ለአንተ ብቻ የተበጀውን የ8-ሳምንት የልምምድ ፕሮግራም በስነስርዓት አዘጋጅቼ ጨርሼ ነበር።\n\n"
                f"ግን የሰውነት መገለጫህን (Profile Card) አይተህ... ክፍያውን ሳትፈጽም ዝም አልከኝ።\n\n"
                f"ወንድሜ እውነቱን እንነጋገር፦ ሰውነትህን ለመቀየርና ማንነትህን ለመቀየር የወሰንከው በዚህ ሳምንት ነበር። "
                f"በየቀኑ ማዘግየትና 'ነገ እጀምራለሁ' እያሉ በቁጭት መኖር የትም አያደርስህም።\n\n"
                f"እኔ ቃሌን አክብሬ ፕሮግራምህን አዘጋጅቼ ጨርሻለሁ፤ አሁን ውሳኔው የአንተ ነው።\n\n"
                f"ከታች ያለውን ቁልፍ ተጭነህ የ8-ሳምንት ፕሮግራምህን አሁኑኑ ክፈትና እንጀምር፦ 👇"
            )

            btn_text = "⚡️ የ8-ሳምንት ፕሮግራሜን ልክፈት (949 ብር)"

    else:
        # ──────────────────────────────────────────────────────────
        # ENGLISH PERSONALIZATION (Direct, Authoritative Coach Hilawe Voice)
        # ──────────────────────────────────────────────────────────
        greeting = f"Hey {first_name}... Coach Hilawe here. 🤝" if first_name else "Hey Champion... Coach Hilawe here. 🤝"

        if "FATLOSS" in goal:
            goal_phrased = "strip belly fat and get lean"
        elif "MUSCLE" in goal:
            goal_phrased = "build dense, functional muscle"
        else:
            goal_phrased = "develop athletic strength and conditioning"

        if "DIET" in obstacle:
            obs_phrased = "dial in your daily nutrition"
        elif "CONSISTENCY" in obstacle:
            obs_phrased = "eliminate motivation dips and stay consistent"
        else:
            obs_phrased = "follow a structured, foolproof daily routine"

        text = (
            f"<b>{greeting}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"Earlier this week, you completed your entire evaluation in the bot.\n\n"
            f"I reviewed your numbers and personally finalized your 8-Week Blueprint to train "
            f"<b>{freq} days a week</b>, <b>{goal_phrased}</b>, and <b>{obs_phrased}</b>.\n\n"
            f"You saw your Profile Card... but you stopped right before activating your program.\n\n"
            f"Real talk: You took the time to do the assessment because you wanted genuine change this week. "
            f"Putting it off until 'next Monday' never worked before, and it won't work now.\n\n"
            f"Your custom blueprint is built and waiting. The move is yours.\n\n"
            f"Tap below to unlock your 8-week program right now: 👇"
        )

        btn_text = "⚡️ Unlock My 8-Week Blueprint (949 ETB)"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=btn_text,
                    callback_data=f"pay_{product_id}"
                )
            ]
        ]
    )

    return text, keyboard


async def get_hot_leads(db: Database) -> List[Dict[str, Any]]:
    rows = await db.fetch("""
        SELECT u.telegram_id, u.full_name, u.username, u.language, u.gender, 
               u.level, u.frequency, u.goal, u.obstacle, u.created_at,
               p.id as product_id
        FROM users u
        LEFT JOIN products p ON 
            UPPER(TRIM(u.language)) = UPPER(TRIM(p.language)) AND 
            UPPER(TRIM(u.gender)) = UPPER(TRIM(p.gender)) AND 
            UPPER(REPLACE(TRIM(u.level), ' ', '_')) = UPPER(REPLACE(TRIM(p.level), ' ', '_')) AND 
            u.frequency = p.frequency
        WHERE u.onboarding_completed = TRUE 
          AND (u.has_paid = FALSE OR u.has_paid IS NULL)
          AND u.created_at >= NOW() - INTERVAL '7 days'
        ORDER BY u.created_at DESC;
    """)
    return [dict(r) for r in rows]


async def run_dry_run(db: Database):
    leads = await get_hot_leads(db)
    print("=" * 65)
    print(f"🔥 HOT LEADS DRY-RUN: Found {len(leads)} Unpaid Leads (Past 7 Days)")
    print("=" * 65)

    male_count = sum(1 for u in leads if "FEMALE" not in (u.get("gender") or "MALE").upper())
    female_count = len(leads) - male_count
    am_count = sum(1 for u in leads if (u.get("language") or "AM").upper() == "AM")
    en_count = len(leads) - am_count

    print(f"Male Leads: {male_count} | Female Leads: {female_count}")
    print(f"Amharic Copy: {am_count} | English Copy: {en_count}")
    print("-" * 65)

    # Sample Male Amharic
    sample_male_am = next((u for u in leads if "FEMALE" not in (u.get("gender") or "").upper() and (u.get("language") or "AM").upper() == "AM" and u.get("full_name")), None)
    if sample_male_am:
        print("\n[SAMPLE 1: MALE AMHARIC LEAD]")
        print(f"Target: {sample_male_am['telegram_id']} | Name: {sample_male_am['full_name']} | Split: {sample_male_am['frequency']}d | Goal: {sample_male_am['goal']} | Obstacle: {sample_male_am['obstacle']}")
        txt, kb = render_hot_lead_message(sample_male_am)
        print(txt)
        print("Button:", [[b.text, b.callback_data] for row in kb.inline_keyboard for b in row])

    # Sample Female Amharic
    sample_female_am = next((u for u in leads if "FEMALE" in (u.get("gender") or "").upper() and (u.get("language") or "AM").upper() == "AM" and u.get("full_name")), None)
    if sample_female_am:
        print("\n" + "=" * 65)
        print("[SAMPLE 2: FEMALE AMHARIC LEAD]")
        print(f"Target: {sample_female_am['telegram_id']} | Name: {sample_female_am['full_name']} | Split: {sample_female_am['frequency']}d | Goal: {sample_female_am['goal']} | Obstacle: {sample_female_am['obstacle']}")
        txt, kb = render_hot_lead_message(sample_female_am)
        print(txt)
        print("Button:", [[b.text, b.callback_data] for row in kb.inline_keyboard for b in row])

    # Sample English Lead
    sample_en = next((u for u in leads if (u.get("language") or "").upper() == "EN" and u.get("full_name")), None)
    if sample_en:
        print("\n" + "=" * 65)
        print("[SAMPLE 3: ENGLISH LEAD]")
        print(f"Target: {sample_en['telegram_id']} | Name: {sample_en['full_name']} | Split: {sample_en['frequency']}d | Goal: {sample_en['goal']} | Obstacle: {sample_en['obstacle']}")
        txt, kb = render_hot_lead_message(sample_en)
        print(txt)
        print("Button:", [[b.text, b.callback_data] for row in kb.inline_keyboard for b in row])


async def run_test_admin(db: Database, bot: Bot):
    admin_id = settings.ADMIN_IDS[0] if settings.ADMIN_IDS else None
    if not admin_id:
        print("❌ Error: No ADMIN_IDS configured in settings.")
        return

    print(f"🚀 Sending Live Test Preview to Admin ID: {admin_id}...")

    # Mock Male Lead
    mock_male = {
        "telegram_id": admin_id,
        "full_name": "ዳዊት መኮንን",
        "gender": "MALE",
        "language": "AM",
        "frequency": 4,
        "goal": "MUSCLE",
        "obstacle": "DIET",
        "level": "BEGINNER",
        "product_id": 13
    }
    txt_m, kb_m = render_hot_lead_message(mock_male)
    await bot.send_message(chat_id=admin_id, text=txt_m, reply_markup=kb_m, parse_mode="HTML")
    print("✅ Male Test Message Delivered to Telegram!")

    await asyncio.sleep(1.0)

    # Mock Female Lead
    mock_female = {
        "telegram_id": admin_id,
        "full_name": "ቤዛዊት ፍቅሬ",
        "gender": "FEMALE",
        "language": "AM",
        "frequency": 3,
        "goal": "FATLOSS",
        "obstacle": "CONSISTENCY",
        "level": "BEGINNER",
        "product_id": 8
    }
    txt_f, kb_f = render_hot_lead_message(mock_female)
    await bot.send_message(chat_id=admin_id, text=txt_f, reply_markup=kb_f, parse_mode="HTML")
    print("✅ Female Test Message Delivered to Telegram!")


async def run_launch(db: Database, bot: Bot):
    leads = await get_hot_leads(db)
    total = len(leads)
    print(f"🚀 LAUNCHING HOT LEADS RECOVERY BROADCAST to {total} users...")

    # Clear any old deal prices to lock in strictly 949 ETB full price
    await db.execute("""
        UPDATE users
        SET deal_price = NULL, deal_expires_at = NULL
        WHERE onboarding_completed = TRUE 
          AND (has_paid = FALSE OR has_paid IS NULL)
          AND created_at >= NOW() - INTERVAL '7 days';
    """)
    logger.info("Cleared old deals for hot leads cohort. Enforcing full price 949 ETB.")

    sent = 0
    blocked = 0
    failed = 0

    semaphore = asyncio.Semaphore(20)

    async def send_to_user(u: Dict[str, Any]):
        nonlocal sent, blocked, failed
        uid = u["telegram_id"]
        text, kb = render_hot_lead_message(u)

        async with semaphore:
            try:
                msg = await bot.send_message(
                    chat_id=uid,
                    text=text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                sent += 1
                await db.execute(
                    "UPDATE users SET last_broadcast_msg_id = $1, matched_product_id = $2 WHERE telegram_id = $3",
                    msg.message_id, u.get("product_id") or get_fallback_product_id(u.get("language", "AM"), u.get("gender", "MALE"), u.get("level", "BEGINNER"), u.get("frequency", 3)), uid
                )
            except TelegramForbiddenError:
                blocked += 1
                logger.warning(f"User {uid} has blocked the bot.")
            except TelegramRetryAfter as e:
                logger.warning(f"Rate limited. Sleeping {e.retry_after}s...")
                await asyncio.sleep(e.retry_after)
                try:
                    await bot.send_message(chat_id=uid, text=text, reply_markup=kb, parse_mode="HTML")
                    sent += 1
                except Exception:
                    failed += 1
            except Exception as e:
                try:
                    import re
                    clean_text = re.sub('<[^<]+?>', '', text)
                    msg = await bot.send_message(chat_id=uid, text=clean_text, reply_markup=kb, parse_mode=None)
                    sent += 1
                    await db.execute(
                        "UPDATE users SET last_broadcast_msg_id = $1, matched_product_id = $2 WHERE telegram_id = $3",
                        msg.message_id, u.get("product_id") or get_fallback_product_id(u.get("language", "AM"), u.get("gender", "MALE"), u.get("level", "BEGINNER"), u.get("frequency", 3)), uid
                    )
                except Exception as inner_e:
                    failed += 1
                    logger.error(f"Error sending to {uid}: {e} (fallback error: {inner_e})")

        await asyncio.sleep(0.06)

    tasks = [send_to_user(u) for u in leads]
    await asyncio.gather(*tasks)

    print("=" * 65)
    print("🏁 HOT LEADS BROADCAST FINISHED")
    print(f"Total Targets: {total}")
    print(f"✅ Delivered: {sent}")
    print(f"🚫 Blocked: {blocked}")
    print(f"❌ Failed: {failed}")
    print("=" * 65)

    # Deliver Report to Admin Telegram
    admin_ids = settings.ADMIN_IDS or [1131741322]
    delivery_rate = (sent / total * 100) if total > 0 else 0

    report_text = (
        f"🔥 <b>HOT LEADS RECOVERY REPORT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Audience:</b> Fresh Unpaid Onboarded Leads (Last 7 Days)\n"
        f"👥 <b>Total Targets:</b> {total}\n"
        f"✅ <b>Successfully Delivered:</b> {sent} ({delivery_rate:.1f}%)\n"
        f"🚫 <b>Blocked Bot:</b> {blocked}\n"
        f"❌ <b>Failed:</b> {failed}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>Personalization:</b> Name + Gender + Exact Days ({3}/{4}/{5}d) + Goal + Obstacle\n"
        f"💰 <b>Price Tier:</b> Full Price 949 ETB\n"
        f"🕒 <b>Delivered At:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    )

    for aid in admin_ids:
        try:
            await bot.send_message(chat_id=aid, text=report_text, parse_mode="HTML")
            logger.info(f"Report delivered to Admin {aid} on Telegram.")
        except Exception as e:
            logger.error(f"Failed to send report to Admin {aid}: {e}")


async def main():
    parser = argparse.ArgumentParser(description="High-Converting Hot Leads Recovery Engine")
    parser.add_argument("--dry-run", action="store_true", help="Preview stats and personalized sample copy without sending")
    parser.add_argument("--test-admin", action="store_true", help="Send test messages (Male & Female) to Admin Telegram ID")
    parser.add_argument("--launch", action="store_true", help="Launch live broadcast to all 744 hot leads")
    args = parser.parse_args()

    db = Database(settings.DATABASE_URL)
    await db.connect()

    if args.test_admin or args.launch:
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            if args.test_admin:
                await run_test_admin(db, bot)
            elif args.launch:
                await run_launch(db, bot)
        finally:
            await bot.session.close()
    else:
        await run_dry_run(db)


if __name__ == "__main__":
    asyncio.run(main())

