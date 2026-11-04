"""
Personalized Retargeting Engine for Incomplete Onboarding Users.
Target: Users in `users` table who dropped off before completing onboarding.
Positioning: Multi-gender respectful Addis voice ('ጨርሰው'), 380k+ community, 1,700+ buyers, pure onboarding resume.
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
logger = logging.getLogger("RETARGET_ONBOARDING")


def render_retarget_message(user: Dict[str, Any]) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Renders an authentic, grounded, respectful multi-gender Addis message from Coach Hilawe.
    Focuses on social proof (380k+ community, 1,700+ buyers) and directs user to complete onboarding.
    """
    full_name = user.get("full_name") or ""
    first_name = full_name.strip().split()[0].capitalize() if full_name else ""
    
    lang = (user.get("language") or "AM").upper()
    if lang not in ("AM", "EN"):
        lang = "AM"

    if lang == "AM":
        # Multi-gender, respectful Addis tone ('ጨርሰው', 'እርስዎ', 'ሰውነትዎን')
        greeting = f"ሰላም {first_name}... አሰልጣኝ ህላዌ ነኝ። 🤝" if first_name else "ሰላም... አሰልጣኝ ህላዌ ነኝ። 🤝"

        text = (
            f"<b>{greeting}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"ባለፈው እዚህ ቦት ላይ ገብተው ቋንቋ ከመረጡ በኋላ የሰውነት ምዘናዎን ሳያጠናቅቁ አቋርጠው ወጥተዋል።\n\n"
            f"በማህበራዊ ገጾች ከ<b>380 ሺህ በላይ</b> ተከታዮችን በማስተማር እና በማሰልጠን ብዙ አመታትን አሳልፌያለሁ። "
            f"ይህንን የ8-ሳምንት የለውጥ ሲስተም ከ<b>1,700 በላይ ሰዎች</b> ወስደው እውነተኛ የሰውነት ለውጥ አምጥተውበታል።\n\n"
            f"ለእርስዎ ትክክለኛውንና ሳይንሳዊውን የልምምድ እቅድ ለማዘጋጀት ግን የእርስዎን የሰውነት ሁኔታ፣ ግብ እና የልምድ ደረጃ ማወቅ አለብኝ።\n\n"
            f"ያቋረጡትን የጥቂት ሰከንዶች ምዘና አሁኑኑ ጨርሰው ለእርስዎ የተበጀውን እቅድ ይመልከቱ።\n\n"
            f"ከታች ያለውን ቁልፍ ተጭነው ምዘናዎን ይቀጥሉ፦ 👇"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🎯 የሰውነት ምዘናዎን ይጨርሱ",
                        callback_data="retarget_resume"
                    )
                ]
            ]
        )

    else:
        # High-Impact, respectful English Copy
        greeting = f"Hey {first_name}... Coach Hilawe here. 🤝" if first_name else "Hey... Coach Hilawe here. 🤝"

        text = (
            f"<b>{greeting}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"I noticed that after selecting your language, you stepped away before completing your body assessment.\n\n"
            f"Over the years, I've coached a community of over <b>380,000 people</b>, and more than <b>1,700 clients</b> "
            f"have already enrolled in this exact 8-Week Blueprint to achieve genuine physical transformations.\n\n"
            f"To design the right science-based training plan for your body, I need to know your target goals, "
            f"experience level, and weekly split.\n\n"
            f"Take 30 seconds right now to complete your assessment and unlock your personalized program.\n\n"
            f"Tap the button below to continue: 👇"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🎯 Complete My Assessment",
                        callback_data="retarget_resume"
                    )
                ]
            ]
        )

    return text, keyboard


async def get_target_users(db: Database) -> List[Dict[str, Any]]:
    rows = await db.fetch("""
        SELECT telegram_id, full_name, username, language, created_at
        FROM users
        WHERE onboarding_completed = FALSE OR onboarding_completed IS NULL
        ORDER BY created_at DESC;
    """)
    return [dict(r) for r in rows]


async def run_dry_run(db: Database):
    users = await get_target_users(db)
    print("=" * 60)
    print(f"🔍 RETARGETING DRY-RUN: Found {len(users)} Incomplete Users")
    print("=" * 60)

    am_count = sum(1 for u in users if (u.get("language") or "AM").upper() == "AM")
    en_count = sum(1 for u in users if (u.get("language") or "").upper() == "EN")
    named_count = sum(1 for u in users if u.get("full_name"))
    print(f"Amharic Copy Target: {am_count}")
    print(f"English Copy Target: {en_count}")
    print(f"Personalized Names Available: {named_count} / {len(users)}")
    print("-" * 60)

    print("\nSAMPLE 1: Amharic (User with Name)")
    sample_am_named = next((u for u in users if u.get("full_name") and (u.get("language") or "AM").upper() == "AM"), None)
    if sample_am_named:
        txt, kb = render_retarget_message(sample_am_named)
        print(f"User: {sample_am_named['telegram_id']} | Name: {sample_am_named['full_name']}")
        print(txt)
        print("Button:", [[b.text, b.callback_data] for row in kb.inline_keyboard for b in row])

    print("\n" + "=" * 60)
    print("SAMPLE 2: Amharic (User without Name)")
    sample_am_unnamed = next((u for u in users if not u.get("full_name") and (u.get("language") or "AM").upper() == "AM"), None)
    if sample_am_unnamed:
        txt, kb = render_retarget_message(sample_am_unnamed)
        print(f"User: {sample_am_unnamed['telegram_id']}")
        print(txt)
        print("Button:", [[b.text, b.callback_data] for row in kb.inline_keyboard for b in row])

    print("\n" + "=" * 60)
    print("SAMPLE 3: English User")
    sample_en = next((u for u in users if (u.get("language") or "").upper() == "EN"), None)
    if sample_en:
        txt, kb = render_retarget_message(sample_en)
        print(f"User: {sample_en['telegram_id']} | Name: {sample_en.get('full_name')}")
        print(txt)
        print("Button:", [[b.text, b.callback_data] for row in kb.inline_keyboard for b in row])


async def run_test_admin(db: Database, bot: Bot):
    admin_id = settings.ADMIN_IDS[0] if settings.ADMIN_IDS else None
    if not admin_id:
        print("❌ Error: No ADMIN_IDS configured in settings.")
        return

    print(f"🚀 Sending Live Test Preview to Admin ID: {admin_id}...")

    # Test 1: Amharic Version
    mock_am = {
        "telegram_id": admin_id,
        "full_name": "ኮች ህላዌ",
        "language": "AM",
        "created_at": datetime.now(timezone.utc)
    }
    txt_am, kb_am = render_retarget_message(mock_am)
    await bot.send_message(chat_id=admin_id, text=txt_am, reply_markup=kb_am, parse_mode="HTML")
    print("✅ Amharic Test Message Delivered to Telegram!")

    await asyncio.sleep(1.0)

    # Test 2: English Version
    mock_en = {
        "telegram_id": admin_id,
        "full_name": "Coach Hilawe",
        "language": "EN",
        "created_at": datetime.now(timezone.utc)
    }
    txt_en, kb_en = render_retarget_message(mock_en)
    await bot.send_message(chat_id=admin_id, text=txt_en, reply_markup=kb_en, parse_mode="HTML")
    print("✅ English Test Message Delivered to Telegram!")


async def run_launch(db: Database, bot: Bot):
    users = await get_target_users(db)
    total = len(users)
    print(f"🚀 LAUNCHING ONBOARDING COMPLETION BROADCAST to {total} users...")

    sent = 0
    blocked = 0
    failed = 0

    semaphore = asyncio.Semaphore(20)

    async def send_to_user(u: Dict[str, Any]):
        nonlocal sent, blocked, failed
        uid = u["telegram_id"]
        text, kb = render_retarget_message(u)

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
                    "UPDATE users SET last_broadcast_msg_id = $1 WHERE telegram_id = $2",
                    msg.message_id, uid
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
                failed += 1
                logger.error(f"Error sending to {uid}: {e}")

        await asyncio.sleep(0.06)

    tasks = [send_to_user(u) for u in users]
    await asyncio.gather(*tasks)

    print("=" * 60)
    print("🏁 BROADCAST FINISHED")
    print(f"Total Targets: {total}")
    print(f"✅ Delivered: {sent}")
    print(f"🚫 Blocked: {blocked}")
    print(f"❌ Failed: {failed}")
    print("=" * 60)

    # Send Execution Report to Admin Telegram
    admin_ids = settings.ADMIN_IDS or [1131741322]
    delivery_rate = (sent / total * 100) if total > 0 else 0
    blocked_rate = (blocked / total * 100) if total > 0 else 0

    report_text = (
        f"📢 <b>ONBOARDING RETARGETING REPORT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Audience:</b> Incomplete Onboarding Users\n"
        f"👥 <b>Total Targets:</b> {total}\n"
        f"✅ <b>Successfully Delivered:</b> {sent} ({delivery_rate:.1f}%)\n"
        f"🚫 <b>Blocked Bot:</b> {blocked} ({blocked_rate:.1f}%)\n"
        f"❌ <b>Other Failed:</b> {failed}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡️ <b>Campaign Hook:</b> 380k community + 1,700+ buyers proof\n"
        f"🎯 <b>Action:</b> 1-Tap Onboarding Resume (Full-Price 949 ETB Funnel)\n"
        f"🕒 <b>Delivered At:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    )

    for aid in admin_ids:
        try:
            await bot.send_message(chat_id=aid, text=report_text, parse_mode="HTML")
            logger.info(f"Report delivered to Admin {aid} on Telegram.")
        except Exception as e:
            logger.error(f"Failed to send report to Admin {aid}: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Multi-Gender Retargeting for Incomplete Onboarding Users")
    parser.add_argument("--dry-run", action="store_true", help="Preview stats and sample copy without sending")
    parser.add_argument("--test-admin", action="store_true", help="Send test messages to the admin Telegram ID")
    parser.add_argument("--launch", action="store_true", help="Launch live broadcast to all incomplete users")
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
