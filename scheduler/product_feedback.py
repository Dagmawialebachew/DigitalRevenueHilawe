# handlers/product_feedback.py

import asyncio
import html
import logging
from datetime import datetime, timezone

from aiogram import Bot, F, Router, types
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from database.db import Database


router = Router(name="product_feedback")
logger = logging.getLogger(__name__)

CAMPAIGN_KEY = "paid_product_feedback_v1"

# Add this environment/config value:
# TESTIMONIAL_ADMIN_CHAT_IDS=-1001234567890
TESTIMONIAL_ADMIN_CHAT_IDS = getattr(
    settings,
    "TESTIMONIAL_ADMIN_CHAT_IDS",
    [
        getattr(
            settings,
            "ADMIN_NEW_USER_LOG_ID",
            settings.ADMIN_IDS[0],
        )
    ],
)


async def send_testimonial_to_admin_chats(
    bot: Bot,
    *,
    source_message: types.Message,
    metadata: str,
) -> dict[int, int | None]:
    """
    Sends the testimonial metadata and forwards the original customer message
    to every configured testimonial admin chat.

    Returns:
        {
            admin_chat_id: forwarded_or_copied_message_id,
            ...
        }
    """
    delivery_results: dict[int, int | None] = {}

    for admin_chat_id in TESTIMONIAL_ADMIN_CHAT_IDS:
        forwarded_message_id = None

        try:
            await bot.send_message(
                chat_id=admin_chat_id,
                text=metadata,
                parse_mode="HTML",
            )

            try:
                forwarded = await bot.forward_message(
                    chat_id=admin_chat_id,
                    from_chat_id=source_message.chat.id,
                    message_id=source_message.message_id,
                )
                forwarded_message_id = forwarded.message_id

            except Exception as forward_error:
                logger.warning(
                    "Original forwarding failed for user %s to admin chat %s: %s",
                    source_message.from_user.id,
                    admin_chat_id,
                    forward_error,
                )

                # Fallback when Telegram forwarding privacy blocks attribution.
                if source_message.voice:
                    copied = await bot.send_voice(
                        chat_id=admin_chat_id,
                        voice=source_message.voice.file_id,
                        caption=(
                            "⚠️ Telegram restricted original forwarding. "
                            "The identity is preserved in the metadata card above."
                        ),
                    )
                    forwarded_message_id = copied.message_id

                elif source_message.audio:
                    copied = await bot.send_audio(
                        chat_id=admin_chat_id,
                        audio=source_message.audio.file_id,
                        caption=source_message.caption,
                    )
                    forwarded_message_id = copied.message_id

                elif source_message.text:
                    copied = await bot.send_message(
                        chat_id=admin_chat_id,
                        text=source_message.text,
                    )
                    forwarded_message_id = copied.message_id

            delivery_results[admin_chat_id] = forwarded_message_id

        except Exception as admin_delivery_error:
            logger.exception(
                "Testimonial delivery failed for admin chat %s: %s",
                admin_chat_id,
                admin_delivery_error,
            )
            delivery_results[admin_chat_id] = None

    return delivery_results

# Protect against accidentally configuring one integer instead of a list.
if isinstance(TESTIMONIAL_ADMIN_CHAT_IDS, int):
    TESTIMONIAL_ADMIN_CHAT_IDS = [TESTIMONIAL_ADMIN_CHAT_IDS]

class ProductFeedbackStates(StatesGroup):
    awaiting_consent = State()
    awaiting_feedback = State()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS product_feedback_sessions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    campaign_key VARCHAR(100) NOT NULL,
    consent_level VARCHAR(30),
    status VARCHAR(20) DEFAULT 'started',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(user_id, campaign_key)
);

CREATE TABLE IF NOT EXISTS product_feedback_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL
        REFERENCES product_feedback_sessions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    message_type VARCHAR(20) NOT NULL,
    telegram_file_id TEXT,
    feedback_text TEXT,
    source_message_id BIGINT,
    forwarded_message_id BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_sessions_campaign
ON product_feedback_sessions(campaign_key, status);

CREATE INDEX IF NOT EXISTS idx_feedback_messages_session
ON product_feedback_messages(session_id);
"""


async def ensure_feedback_schema(db: Database) -> None:
    await db._pool.execute(SCHEMA_SQL)


# ─────────────────────────────────────────────
# MULTILINGUAL BROADCAST COPY
# ─────────────────────────────────────────────

def build_feedback_broadcast(lang: str) -> tuple[str, types.InlineKeyboardMarkup]:
    lang = (lang or "EN").upper()

    kb = InlineKeyboardBuilder()

    if lang == "AM":
        text = (
            "🎙️ <b>ከኮች ህላዌ የተላከ መልዕክት</b>\n\n"
            "ፕሮግራሙን ከገዙ እና መጠቀም ከጀመሩ ጥቂት ጊዜ አልፎዎታል። "
            "አሁን ስለነበረዎት ልምድ በቀጥታ ከእርስዎ መስማት እንፈልጋለን።\n\n"
            "የእርስዎ እውነተኛ ልምድ ፕሮግራሙን እንድናሻሽል እና "
            "በማህበራዊ ድረገጽ ላይ ለሚከታተሉን ሌሎች ሰዎች ትክክለኛ ውሳኔ "
            "እንዲወስኑ ሊረዳ ይችላል።\n\n"
            "🎤 <b>በድምፅ መልዕክት ቢልኩልን እንመርጣለን።</b>\n"
            "በድምፅ መላክ ካልቻሉ በጽሑፍ መላክም ይችላሉ።\n\n"
            "👇 <b>ለመጀመር “ልምዴን ላጋራ” የሚለውን ቁልፍ ይጫኑ።</b>"
        )
        kb.button(
            text="🎙️ ልምዴን ላጋራ",
            callback_data="product_feedback_start",
        )
    else:
        text = (
            "🎙️ <b>A personal request from Coach Hilawe</b>\n\n"
            "You have had some time to open and use the program you purchased. "
            "We would now genuinely like to hear about your experience.\n\n"
            "Your honest feedback will help us improve the program. It may also "
            "help other people who follow Coach Hilawe on Social Media understand what "
            "the program is really like and make a better decision.\n\n"
            "🎤 <b>We would prefer a natural voice message.</b>\n"
            "If you cannot record a voice message, written feedback is completely fine.\n\n"
            "👇 <b>Tap “Share My Experience” below to begin.</b>"
        )
        kb.button(
            text="🎙️ Share My Experience",
            callback_data="product_feedback_start",
        )

    return text, kb.as_markup()


# ─────────────────────────────────────────────
# CONSENT
# ─────────────────────────────────────────────

def build_consent_message(lang: str) -> tuple[str, types.InlineKeyboardMarkup]:
    lang = (lang or "EN").upper()
    kb = InlineKeyboardBuilder()

    if lang == "AM":
        text = (
            "🔐 <b>ከመጀመርዎ በፊት አንድ ምርጫ ያድርጉ</b>\n\n"
            "አስተያየትዎን ኮች ህላዌ በሶሻል ሚዲያ ወይም በሌሎች "
            "ማህበራዊ ገጾች ላይ እንዲጠቀምበት ፈቃድዎን ይምረጡ።\n\n"
            "የምትመርጡትን የግላዊነት ደረጃ እናከብራለን።"
        )
        kb.button(
            text="✅ ከስሜና ዩዘርኔሜ ጋር ይጋራ",
            callback_data="feedback_consent:public_identity",
        )
       
        kb.button(
            text="🔒 ለውስጥ ግምገማ ብቻ",
            callback_data="feedback_consent:private",
        )
    else:
        text = (
            "🔐 <b>Before you begin, choose your sharing preference</b>\n\n"
            "Please tell us whether Coach Hilawe may use your feedback on Social Media "
            "or other social media platforms.\n\n"
            "We will respect the privacy option you select."
        )
        kb.button(
            text="✅ Share with my name and username",
            callback_data="feedback_consent:public_identity",
        )
        kb.button(
            text="🔒 Private feedback only",
            callback_data="feedback_consent:private",
        )

    kb.adjust(1)
    return text, kb.as_markup()


# ─────────────────────────────────────────────
# THREE PRECISE TESTIMONIAL QUESTIONS
# ─────────────────────────────────────────────

def build_feedback_questions(
    lang: str,
) -> tuple[str, types.InlineKeyboardMarkup]:
    lang = (lang or "EN").upper()

    kb = InlineKeyboardBuilder()

    if lang == "AM":
        text = (
            "🎙️ <b>አሁን የእርስዎን እውነተኛ ልምድ ይላኩልን</b>\n\n"
            "የድምፅ መልዕክትዎ ፍጹም የተዘጋጀ መሆን አያስፈልገውም። "
            "በተፈጥሮ ቋንቋዎ ይናገሩ።\n\n"
            "<b>በእነዚህ 3 ጥያቄዎች ዙሪያ ይናገሩ፦</b>\n\n"
            "1️⃣ <b>ፕሮግራሙን ከመግዛትዎ በፊት ዋናው ችግርዎ "
            "ወይም የሰውነት ግብዎ ምን ነበር?</b>\n\n"
            "2️⃣ <b>ፕሮግራሙን ከተጠቀሙ በኋላ በጣም የጠቀምዎት "
            "ክፍል የትኛው ነው? ለምን?</b>\n\n"
            "3️⃣ <b>እስካሁን ምን ለውጥ ወይም ውጤት አይተዋል? "
            "ፕሮግራሙን ለመግዛት ለሚያስብ ሰው ምን ይሉታል?</b>\n\n"
            "🎤 የድምፅ መልዕክት አሁኑኑ ይላኩ።\n"
            "ድምፅ መላክ ካልቻሉ በጽሑፍ ይላኩ።\n\n"
            "ብዙ የድምፅ መልዕክቶችን መላክ ይችላሉ። "
            "ሲጨርሱ ከታች ያለውን ቁልፍ ይጫኑ።"
        )
        kb.button(
            text="✅ አስተያየቴን ጨርሻለሁ",
            callback_data="product_feedback_finish",
        )
    else:
        text = (
            "🎙️ <b>Now send us your honest experience</b>\n\n"
            "Your voice message does not need to sound polished or rehearsed. "
            "Speak naturally in your own words.\n\n"
            "<b>Please answer these three questions:</b>\n\n"
            "1️⃣ <b>Before buying the program, what was your main struggle or "
            "physical goal?</b>\n\n"
            "2️⃣ <b>After using the program, which part helped you most, and why?</b>\n\n"
            "3️⃣ <b>What change or result have you noticed so far, and what would "
            "you tell someone who is considering buying the program?</b>\n\n"
            "🎤 Send your voice message now.\n"
            "If you cannot send a voice message, write your answer as text.\n\n"
            "You may send more than one voice message. Tap the button below when finished."
        )
        kb.button(
            text="✅ Finish My Feedback",
            callback_data="product_feedback_finish",
        )

    return text, kb.as_markup()


# ─────────────────────────────────────────────
# ADMIN BROADCAST COMMAND WITH PREVIEW
# ─────────────────────────────────────────────

@router.message(
    Command("request_product_feedback"),
    F.from_user.id.in_(settings.ADMIN_IDS),
)
async def request_product_feedback_preview(
    message: types.Message,
    db: Database,
    state: FSMContext,
):
    await state.clear()
    await ensure_feedback_schema(db)

    stats = await db._pool.fetchrow(
        """
        SELECT
            COUNT(*)::INT AS eligible,
            COUNT(*) FILTER (
                WHERE UPPER(COALESCE(u.language, 'EN')) = 'AM'
            )::INT AS am_count,
            COUNT(*) FILTER (
                WHERE UPPER(COALESCE(u.language, 'EN')) = 'EN'
            )::INT AS en_count
        FROM users u
        WHERE EXISTS (
            SELECT 1
            FROM payments p
            WHERE p.user_id = u.telegram_id
              AND p.status = 'approved'
              AND COALESCE(p.approved_at, p.created_at)
                    <= NOW() - INTERVAL '2 days'
        )
        AND NOT EXISTS (
            SELECT 1
            FROM product_feedback_sessions fs
            WHERE fs.user_id = u.telegram_id
              AND fs.campaign_key = $1
              AND fs.status = 'completed'
        )
        """,
        CAMPAIGN_KEY,
    )

    en_text, en_kb = build_feedback_broadcast("EN")
    am_text, am_kb = build_feedback_broadcast("AM")

    await message.answer(
        "📊 <b>PRODUCT FEEDBACK BROADCAST PREVIEW</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"✅ Eligible paid-product users: <code>{stats['eligible']}</code>\n"
        f"🇪🇹 Amharic users: <code>{stats['am_count']}</code>\n"
        f"🇬🇧 English users: <code>{stats['en_count']}</code>\n\n"
        "Targeting rules:\n"
        "• At least one approved standard-product payment\n"
        "• Purchase approved more than 2 days ago\n"
        "• Community-only members excluded\n"
        "• Unpaid users excluded\n"
        "• Completed respondents excluded",
        parse_mode="HTML",
    )

    await message.answer(
        "👀 <b>ENGLISH PREVIEW</b>",
        parse_mode="HTML",
    )
    await message.answer(
        en_text,
        reply_markup=en_kb,
        parse_mode="HTML",
    )

    await message.answer(
        "👀 <b>AMHARIC PREVIEW</b>",
        parse_mode="HTML",
    )
    await message.answer(
        am_text,
        reply_markup=am_kb,
        parse_mode="HTML",
    )

    confirm_kb = InlineKeyboardBuilder()
    confirm_kb.button(
        text="🧪 Send Test to Admins",
        callback_data="product_feedback_broadcast:test",
    )
    confirm_kb.button(
        text=f"🚀 Send to {stats['eligible']} Users",
        callback_data="product_feedback_broadcast:launch",
    )
    confirm_kb.button(
        text="❌ Cancel",
        callback_data="product_feedback_broadcast:cancel",
    )
    confirm_kb.adjust(1)

    await message.answer(
        "⚠️ <b>Review both language versions carefully before launching.</b>",
        reply_markup=confirm_kb.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(
    F.data == "product_feedback_broadcast:cancel",
    F.from_user.id.in_(settings.ADMIN_IDS),
)
async def cancel_product_feedback_broadcast(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    await state.clear()
    await callback.message.edit_text(
        "❌ Product feedback broadcast cancelled."
    )
    await callback.answer()


@router.callback_query(
    F.data == "product_feedback_broadcast:test",
    F.from_user.id.in_(settings.ADMIN_IDS),
)
async def test_product_feedback_broadcast(
    callback: types.CallbackQuery,
    bot: Bot,
):
    sent = 0

    for admin_id in settings.ADMIN_IDS:
        try:
            en_text, en_kb = build_feedback_broadcast("EN")
            await bot.send_message(
                chat_id=admin_id,
                text=en_text,
                reply_markup=en_kb,
                parse_mode="HTML",
            )
            sent += 1
        except Exception as exc:
            logger.exception(
                "Feedback test failed for admin %s: %s",
                admin_id,
                exc,
            )

    await callback.answer(
        f"Test sent to {sent} admin(s).",
        show_alert=True,
    )


@router.callback_query(
    F.data == "product_feedback_broadcast:launch",
    F.from_user.id.in_(settings.ADMIN_IDS),
)
async def launch_product_feedback_broadcast(
    callback: types.CallbackQuery,
    db: Database,
    bot: Bot,
):
    await callback.answer()

    await callback.message.edit_text(
        "⏳ <b>Product feedback broadcast started...</b>",
        parse_mode="HTML",
    )

    targets = await db._pool.fetch(
        """
        SELECT
            u.telegram_id,
            UPPER(COALESCE(u.language, 'EN')) AS language
        FROM users u
        WHERE EXISTS (
            SELECT 1
            FROM payments p
            WHERE p.user_id = u.telegram_id
              AND p.status = 'approved'
              AND COALESCE(p.approved_at, p.created_at)
                    <= NOW() - INTERVAL '2 days'
        )
        AND NOT EXISTS (
            SELECT 1
            FROM product_feedback_sessions fs
            WHERE fs.user_id = u.telegram_id
              AND fs.campaign_key = $1
              AND fs.status = 'completed'
        )
        ORDER BY u.telegram_id
        """,
        CAMPAIGN_KEY,
    )

    stats = {
        "sent": 0,
        "failed": 0,
        "blocked": 0,
    }

    semaphore = asyncio.Semaphore(20)

    async def send_to_user(record):
        uid = record["telegram_id"]
        lang = record["language"]

        async with semaphore:
            text, markup = build_feedback_broadcast(lang)

            while True:
                try:
                    await bot.send_message(
                        chat_id=uid,
                        text=text,
                        reply_markup=markup,
                        parse_mode="HTML",
                    )
                    stats["sent"] += 1
                    break

                except TelegramRetryAfter as exc:
                    await asyncio.sleep(exc.retry_after)

                except TelegramForbiddenError:
                    stats["blocked"] += 1
                    break

                except Exception as exc:
                    stats["failed"] += 1
                    logger.exception(
                        "Feedback broadcast failed for %s: %s",
                        uid,
                        exc,
                    )
                    break

            await asyncio.sleep(0.05)

    await asyncio.gather(
        *(send_to_user(record) for record in targets)
    )

    report = (
        "🏁 <b>PRODUCT FEEDBACK BROADCAST COMPLETE</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"✅ Delivered: <code>{stats['sent']}</code>\n"
        f"🚫 Blocked: <code>{stats['blocked']}</code>\n"
        f"❌ Failed: <code>{stats['failed']}</code>\n"
        f"👥 Total selected: <code>{len(targets)}</code>"
    )

    await bot.send_message(
        chat_id=callback.from_user.id,
        text=report,
        parse_mode="HTML",
    )


# ─────────────────────────────────────────────
# USER CLICKS “SHARE MY EXPERIENCE”
# ─────────────────────────────────────────────

@router.callback_query(F.data == "product_feedback_start")
async def start_product_feedback(
    callback: types.CallbackQuery,
    state: FSMContext,
    db: Database,
):
    await callback.answer()
    await ensure_feedback_schema(db)

    uid = callback.from_user.id

    eligible = await db._pool.fetchval(
        """
        SELECT EXISTS (
            SELECT 1
            FROM payments p
            WHERE p.user_id = $1
              AND p.status = 'approved'
              AND COALESCE(p.approved_at, p.created_at)
                    <= NOW() - INTERVAL '2 days'
        )
        """,
        uid,
    )

    user = await db._pool.fetchrow(
        """
        SELECT COALESCE(language, 'EN') AS language
        FROM users
        WHERE telegram_id = $1
        """,
        uid,
    )

    lang = (
        user["language"]
        if user and user["language"]
        else "EN"
    ).upper()

    if not eligible:
        text = (
            "This feedback request is currently available only to customers "
            "who purchased the program more than two days ago."
            if lang == "EN"
            else
            "ይህ የአስተያየት ጥያቄ ፕሮግራሙን ከገዙ ከ2 ቀናት "
            "በላይ ለሆናቸው ደንበኞች ብቻ ነው።"
        )
        return await callback.message.answer(text)

    existing = await db._pool.fetchrow(
        """
        SELECT id, status
        FROM product_feedback_sessions
        WHERE user_id = $1
          AND campaign_key = $2
        """,
        uid,
        CAMPAIGN_KEY,
    )

    if existing and existing["status"] == "completed":
        text = (
            "✅ Thank you. You have already completed this feedback request."
            if lang == "EN"
            else
            "✅ እናመሰግናለን። ይህን የአስተያየት ጥያቄ ቀድሞውኑ ጨርሰዋል።"
        )
        return await callback.message.answer(text)

    await state.update_data(
        feedback_language=lang,
        campaign_key=CAMPAIGN_KEY,
    )

    consent_text, consent_kb = build_consent_message(lang)

    await callback.message.answer(
        consent_text,
        reply_markup=consent_kb,
        parse_mode="HTML",
    )
    await state.set_state(ProductFeedbackStates.awaiting_consent)


# ─────────────────────────────────────────────
# USER CHOOSES SHARING PERMISSION
# ─────────────────────────────────────────────

@router.callback_query(
    ProductFeedbackStates.awaiting_consent,
    F.data.startswith("feedback_consent:"),
)
async def process_feedback_consent(
    callback: types.CallbackQuery,
    state: FSMContext,
    db: Database,
):
    await callback.answer()

    uid = callback.from_user.id
    consent_level = callback.data.split(":", 1)[1]

    data = await state.get_data()
    lang = data.get("feedback_language", "EN")

    session_id = await db._pool.fetchval(
        """
        INSERT INTO product_feedback_sessions (
            user_id,
            campaign_key,
            consent_level,
            status,
            started_at
        )
        VALUES ($1, $2, $3, 'collecting', NOW())
        ON CONFLICT (user_id, campaign_key)
        DO UPDATE SET
            consent_level = EXCLUDED.consent_level,
            status = 'collecting',
            started_at = NOW(),
            completed_at = NULL
        RETURNING id
        """,
        uid,
        CAMPAIGN_KEY,
        consent_level,
    )

    await state.update_data(
        feedback_session_id=session_id,
        feedback_consent=consent_level,
        feedback_message_count=0,
    )

    prompt, finish_kb = build_feedback_questions(lang)

    await callback.message.answer(
        prompt,
        reply_markup=finish_kb,
        parse_mode="HTML",
    )
    await state.set_state(ProductFeedbackStates.awaiting_feedback)


# ─────────────────────────────────────────────
# ACCEPT VOICE, AUDIO OR TEXT
# ─────────────────────────────────────────────

@router.message(
    ProductFeedbackStates.awaiting_feedback,
    F.voice | F.audio | F.text,
)
async def collect_product_feedback(
    message: types.Message,
    state: FSMContext,
    db: Database,
    bot: Bot,
):
    data = await state.get_data()

    session_id = data.get("feedback_session_id")
    consent_level = data.get("feedback_consent", "private")
    lang = data.get("feedback_language", "EN")
    current_count = int(data.get("feedback_message_count", 0))

    if not session_id:
        await state.clear()
        return await message.answer(
            "Your feedback session expired. Please tap the feedback button again."
            if lang == "EN"
            else
            "የአስተያየት ጊዜዎ አልፏል። እባክዎ የአስተያየት ቁልፉን እንደገና ይጫኑ።"
        )

    uid = message.from_user.id
    full_name = message.from_user.full_name or "Unknown"
    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Not set"
    )

    if message.voice:
        message_type = "voice"
        file_id = message.voice.file_id
        feedback_text = None

    elif message.audio:
        message_type = "audio"
        file_id = message.audio.file_id
        feedback_text = message.caption

    else:
        message_type = "text"
        file_id = None
        feedback_text = message.text

    purchase = await db._pool.fetchrow(
        """
        SELECT
            p.id AS payment_id,
            p.amount,
            COALESCE(p.approved_at, p.created_at) AS purchase_date,
            pr.title AS product_title
        FROM payments p
        LEFT JOIN products pr ON pr.id = p.product_id
        WHERE p.user_id = $1
          AND p.status = 'approved'
        ORDER BY COALESCE(p.approved_at, p.created_at) DESC
        LIMIT 1
        """,
        uid,
    )

    consent_labels = {
        "public_identity": "PUBLIC — name and username permitted",
        "anonymous": "PUBLIC — identity must be hidden",
        "private": "PRIVATE — do not publish",
    }

    # Send a metadata card before the original forwarded message.
    metadata = (
        "🎙️ <b>NEW PAID-PRODUCT TESTIMONIAL</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🧾 Session ID: <code>{session_id}</code>\n"
        f"👤 Name: <b>{html.escape(full_name)}</b>\n"
        f"🔗 Current username: <code>{html.escape(username)}</code>\n"
        f"🆔 Telegram ID: <code>{uid}</code>\n"
        f"🌍 Language: <code>{html.escape(lang)}</code>\n"
        f"📨 Submission: <code>{message_type}</code>\n"
        f"🔐 Consent: <b>{html.escape(consent_labels.get(consent_level, consent_level))}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📦 Product: <b>{html.escape(str(purchase['product_title'] if purchase else 'Unknown'))}</b>\n"
        f"💰 Amount: <code>{purchase['amount'] if purchase else 'Unknown'} ETB</code>\n"
        f"📅 Purchase date: <code>{purchase['purchase_date'].strftime('%Y-%m-%d') if purchase else 'Unknown'}</code>\n\n"
        "👇 <b>The original customer message is forwarded below.</b>"
    )

    admin_delivery_results = await send_testimonial_to_admin_chats(
    bot,
    source_message=message,
    metadata=metadata,
)

    # Keep one message ID in the existing database column.
    # Prefer the first successful admin delivery.
    forwarded_message_id = next(
        (
            message_id
            for message_id in admin_delivery_results.values()
            if message_id is not None
        ),
        None,
    )

   

    await db._pool.execute(
        """
        INSERT INTO product_feedback_messages (
            session_id,
            user_id,
            message_type,
            telegram_file_id,
            feedback_text,
            source_message_id,
            forwarded_message_id
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        session_id,
        uid,
        message_type,
        file_id,
        feedback_text,
        message.message_id,
        forwarded_message_id,
    )

    current_count += 1
    await state.update_data(feedback_message_count=current_count)

    finish_kb = InlineKeyboardBuilder()

    if lang == "AM":
        finish_kb.button(
            text="✅ አስተያየቴን ጨርሻለሁ",
            callback_data="product_feedback_finish",
        )
        confirmation = (
            f"✅ <b>መልዕክትዎ ደርሶናል።</b>\n\n"
            f"እስካሁን <b>{current_count}</b> መልዕክት ልከዋል።\n"
            "ተጨማሪ ድምፅ ወይም ጽሑፍ መላክ ይችላሉ። "
            "ሲጨርሱ ከታች ያለውን ቁልፍ ይጫኑ።"
        )
    else:
        finish_kb.button(
            text="✅ Finish My Feedback",
            callback_data="product_feedback_finish",
        )
        confirmation = (
            f"✅ <b>Your message was received.</b>\n\n"
            f"You have submitted <b>{current_count}</b> message(s).\n"
            "You can send another voice message or text. Tap below when you are finished."
        )

    await message.answer(
        confirmation,
        reply_markup=finish_kb.as_markup(),
        parse_mode="HTML",
    )


# ─────────────────────────────────────────────
# FINISH TESTIMONIAL SESSION
# ─────────────────────────────────────────────

@router.callback_query(
    ProductFeedbackStates.awaiting_feedback,
    F.data == "product_feedback_finish",
)
async def finish_product_feedback(
    callback: types.CallbackQuery,
    state: FSMContext,
    db: Database,
    bot: Bot,
):
    await callback.answer()

    data = await state.get_data()
    lang = data.get("feedback_language", "EN")
    session_id = data.get("feedback_session_id")
    message_count = int(data.get("feedback_message_count", 0))

    if message_count < 1:
        warning = (
            "Please send at least one voice or text message before finishing."
            if lang == "EN"
            else
            "እባክዎ ከመጨረስዎ በፊት ቢያንስ አንድ የድምፅ "
            "ወይም የጽሑፍ መልዕክት ይላኩ።"
        )
        return await callback.answer(
            warning,
            show_alert=True,
        )

    await db._pool.execute(
        """
        UPDATE product_feedback_sessions
        SET status = 'completed',
            completed_at = NOW()
        WHERE id = $1
        """,
        session_id,
    )

    user = callback.from_user
    username = (
        f"@{user.username}"
        if user.username
        else "Not set"
    )

    await bot.send_message(
        chat_id=TESTIMONIAL_ADMIN_CHAT_IDS,
        text=(
            "✅ <b>TESTIMONIAL SESSION COMPLETED</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"🧾 Session ID: <code>{session_id}</code>\n"
            f"👤 User: <b>{html.escape(user.full_name)}</b>\n"
            f"🔗 Username: <code>{html.escape(username)}</code>\n"
            f"📨 Messages submitted: <code>{message_count}</code>\n"
            f"🕒 Completed: <code>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</code>"
        ),
        parse_mode="HTML",
    )

    if lang == "AM":
        thank_you = (
            "🙏 <b>ከልብ እናመሰግናለን!</b>\n\n"
            "የላኩት እውነተኛ ልምድ ደርሶናል። "
            "የእርስዎ አስተያየት ፕሮግራሙን እንድናሻሽል "
            "እና ሌሎች ሰዎች ትክክለኛ ውሳኔ እንዲወስኑ ይረዳል።"
        )
    else:
        thank_you = (
            "🙏 <b>Thank you sincerely!</b>\n\n"
            "Your honest experience has been received. Your feedback will help "
            "us improve the program and help other people make a more informed decision."
        )

    await callback.message.answer(
        thank_you,
        parse_mode="HTML",
    )
    await state.clear()