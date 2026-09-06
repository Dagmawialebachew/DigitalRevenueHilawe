"""2019 Ethiopian New Year Free Gift and Growth Funnel Handler.

Provides:
1. Universal interception whenever a user types '2019' alone in any state.
2. Instant delivery of the 5-page 'የ2019 የለውጥ መመሪያ' PDF (cached file_id for 0ms latency).
3. 3.5-second natural coach typing pause.
4. The psychology bridge message transitioning freebie seekers into the paid 8-Week Blueprint assessment.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, F, Router, types
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import Database
from handlers.onboarding import OnboardingStepping
from keyboards import inline as kb
from utils.localization import get_text

router = Router(name="new_year")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = ROOT / "assets" / "new_year_2019_guide.pdf"

# In-memory Telegram file_id cache so uploads happen at most once
_CACHED_NEW_YEAR_FILE_ID: str | None = os.getenv("NEW_YEAR_FREE_PDF_FILE_ID")


def get_new_year_caption(lang: str = "AM") -> str:
    if lang == "EN":
        return (
            "🇪🇹 <b>Happy 2019 Ethiopian New Year!</b>\n\n"
            "<i>“A new year isn't just about changing the calendar; it's about taking true ownership of your body and health.”</i> — <b>Coach Hilawe</b> 🤝\n\n"
            "🎁 Here is your exclusive <b>2019 Transformation Action Guide</b>. Download it below and start reading!"
        )
    return (
        "🇪🇹 <b>እንኳን ለ2019 አዲሱ ዓመት በሰላም አደረሳችሁ!</b>\n\n"
        "<i>“አዲስ ዓመት ማለት የቀን መቁጠሪያ መቀየር ብቻ አይደለም፤ ራስህን የምትቀይርበት እና ጤናህን የምትረከብበት ትክክለኛ ውሳኔ ነው።”</i> — <b>ኮች ህላዌ</b> 🤝\n\n"
        "🎁 ለአዲሱ ዓመት በልዩ ሁኔታ ያዘጋጀሁላችሁ <b>የ2019 የለውጥ መመሪያ</b> ይኸው ተልኮልዎታል፤ አሁኑኑ አውርደው ያንብቡት!"
    )


def get_bridge_text(lang: str = "AM") -> str:
    if lang == "EN":
        return (
            "⚔️ <b>Now champion... let's speak truth:</b>\n\n"
            "This guide gives you the foundation. But real, accelerated body transformation only happens when you follow a <b>personalized 8-week system built specifically for your body type, weight, and weekly routine</b>. 🏆\n\n"
            "Let's make 2019 the year of actual action, not empty resolutions.\n\n"
            "<b>Shall we assess your body and build your custom 8-week program right now?</b>"
        )
    return (
        "⚔️ <b>ነገር ግን ሻምፒዮን... አንድ እውነት እንነጋገር፦</b>\n\n"
        "ይህ መመሪያ የመንገዱን መነሻ ያሳይዎታል። ነገር ግን እውነተኛውና ፈጣኑ ለውጥ የሚመጣው "
        "<b>ለእርስዎ የሰውነት ሁኔታ፣ ክብደትና የሳምንት ቀናት በተዘጋጀው የ8-ሳምንት እቅድ</b> ስትመሩ ብቻ ነው። 🏆\n\n"
        "2019 ዓ.ምን በባዶ ተስፋ ሳይሆን በተግባር የምንቀይርበት ዓመት እናድርገው።\n\n"
        "<b>የአካልዎን ሁኔታ መዝነን የ8-ሳምንት ፕሮግራምዎን አሁኑኑ እናዘጋጅ?</b>"
    )


async def send_new_year_bundle(
    chat_id: int,
    user: types.User,
    bot: Bot,
    db: Database,
    state: FSMContext,
) -> None:
    global _CACHED_NEW_YEAR_FILE_ID

    # 1. Look up user language preference
    user_row = await db.get_user(user.id)
    lang = (user_row.get("language") if user_row else None) or "AM"

    # 2. Record claim in database
    await db.record_new_year_claim(
        telegram_id=user.id,
        full_name=user.full_name or "",
        username=user.username or "",
    )

    caption = get_new_year_caption(lang)

    # 3. Deliver document: use cached file_id if present, else upload local PDF
    try:
        if _CACHED_NEW_YEAR_FILE_ID:
            await bot.send_document(
                chat_id=chat_id,
                document=_CACHED_NEW_YEAR_FILE_ID,
                caption=caption,
                parse_mode="HTML",
            )
        elif PDF_PATH.exists():
            input_file = FSInputFile(
                path=str(PDF_PATH),
                filename="የ2019_የለውጥ_መመሪያ_Coach_Hilawe.pdf",
            )
            sent_doc = await bot.send_document(
                chat_id=chat_id,
                document=input_file,
                caption=caption,
                parse_mode="HTML",
            )
            if sent_doc.document:
                _CACHED_NEW_YEAR_FILE_ID = sent_doc.document.file_id
                logger.info("Cached 2019 Guide Telegram file_id: %s", _CACHED_NEW_YEAR_FILE_ID)
        else:
            logger.error("2019 PDF not found at path: %s", PDF_PATH)
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="HTML",
            )
    except Exception as exc:
        logger.exception("Failed delivering 2019 PDF to %s: %s", user.id, exc)
        # Attempt fallback upload without file_id cache
        if PDF_PATH.exists():
            try:
                input_file = FSInputFile(str(PDF_PATH), filename="የ2019_የለውጥ_መመሪያ_Coach_Hilawe.pdf")
                sent_doc = await bot.send_document(chat_id=chat_id, document=input_file, caption=caption, parse_mode="HTML")
                if sent_doc.document:
                    _CACHED_NEW_YEAR_FILE_ID = sent_doc.document.file_id
            except Exception:
                pass

    # 4. Human-like pause: Coach Hilawe sizing up the client
    try:
        await bot.send_chat_action(chat_id, ChatAction.TYPING)
    except Exception:
        pass
    await asyncio.sleep(3.5)

    # 5. Deliver the Bridge Message leading into the paid 8-week assessment
    bridge_builder = InlineKeyboardBuilder()
    start_btn_text = "🚀 አዎ፣ የ8-ሳምንት እቅዴን አዘጋጅልኝ" if lang == "AM" else "🚀 Yes, Build My 8-Week Plan"
    bridge_builder.button(text=start_btn_text, callback_data="start_new_year_onboarding")
    bridge_builder.adjust(1)

    await bot.send_message(
        chat_id=chat_id,
        text=get_bridge_text(lang),
        reply_markup=bridge_builder.as_markup(),
        parse_mode="HTML",
    )


@router.message(F.text.regexp(r"^\s*2019\s*$"))
async def handle_2019_universal(
    message: types.Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
) -> None:
    """Universal trigger for '2019' anywhere across all chat states."""
    if not message.from_user:
        return
    await send_new_year_bundle(
        chat_id=message.chat.id,
        user=message.from_user,
        bot=bot,
        db=db,
        state=state,
    )


@router.callback_query(F.data == "claim_new_year_2019")
async def handle_2019_claim_button(
    callback: types.CallbackQuery,
    state: FSMContext,
    bot: Bot,
    db: Database,
) -> None:
    """Triggered when user clicks the 2019 gift button directly in onboarding."""
    await callback.answer("🎁 ስጦታዎ በመላክ ላይ ነው...")
    await send_new_year_bundle(
        chat_id=callback.message.chat.id,
        user=callback.from_user,
        bot=bot,
        db=db,
        state=state,
    )


@router.callback_query(F.data == "start_new_year_onboarding")
async def handle_start_onboarding_from_gift(
    callback: types.CallbackQuery,
    state: FSMContext,
    db: Database,
) -> None:
    """Transitions from the free gift bridge directly into the 8-Week Assessment (Gender)."""
    await callback.answer()
    user_row = await db.get_user(callback.from_user.id)
    lang = (user_row.get("language") if user_row else None) or "AM"

    await state.update_data(language=lang)

    text = get_text(lang, "ask_gender")
    await callback.message.answer(text, reply_markup=kb.gender_markup(lang))
    await state.set_state(OnboardingStepping.gender)
