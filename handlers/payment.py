import asyncio
import logging
import html
from datetime import datetime, timezone
from aiogram import Router, F, types, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatAction
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import Database
from keyboards import inline as kb
from keyboards import reply as rb
from utils.localization import get_text
from config import settings

# 🚨 IMPORT THE CORE ENGINES FROM VERIFY.PY Safely
import io
import time
from handlers.verify import extract_local_data, verify_external, is_hilawe_receiver
from handlers.forensic_stamp import process_and_stamp_incoming_proof
from services.coach_ai import generate_coach_reply
from scheduler.retarget_hot_unpaid_leads import get_fallback_product_id
REPORT_CACHE = {}

router = Router(name="payment")
logger = logging.getLogger(__name__)

admin_id = 1131741322

def resolve_user_product_id(user: dict | None) -> int:
    if not user:
        return 4
    prod_id = user.get("matched_product_id")
    if prod_id:
        return int(prod_id)
    return get_fallback_product_id(
        lang=user.get("language") or "AM",
        gender=user.get("gender") or "MALE",
        level=user.get("level") or "BEGINNER",
        freq=user.get("frequency") or 3
    )

def resolve_user_price(user: dict | None, default_price: float = 1299.0) -> float:
    if not user:
        return default_price
    now = datetime.now(timezone.utc)
    deal_price = user.get("deal_price")
    deal_expiry = user.get("deal_expires_at")
    if deal_expiry and deal_expiry.tzinfo is None:
        deal_expiry = deal_expiry.replace(tzinfo=timezone.utc)
    if deal_price and deal_expiry and now < deal_expiry:
        return float(deal_price)
    return default_price

class PaymentStates(StatesGroup):
    awaiting_proof = State()


@router.callback_query(F.data.startswith("pay_"))
async def initiate_payment(callback: types.CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    await callback.answer()  # Stop the spinner immediately
    
    product_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    user_data = await db.get_user(user_id)
    lang = user_data.get("language", "EN") if user_data else "EN"

    product = await db._pool.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
    if not product:
        return await callback.message.answer("⚠️ System Error: Plan not found.")

    # --- Price Logic with Expiry Check ---
    display_price = product['price']
    now = datetime.now(timezone.utc)
    
    deal_price = user_data.get("deal_price")
    deal_expiry = user_data.get("deal_expires_at")

    if deal_expiry and deal_expiry.tzinfo is None:
        deal_expiry = deal_expiry.replace(tzinfo=timezone.utc)

    if deal_price and deal_expiry and now < deal_expiry:
        display_price = deal_price
        print(f"✅ Deal Active! Using price: {display_price}")
    else:
        print(f"❌ Deal Expired or Not Found. Using original: {display_price}")

    await state.update_data(selected_product_id=product_id, amount=display_price)

    def safe_html(val):
        return html.escape(str(val)) if val else "Not Set"

    if lang == "EN":
        instruction = (
            f"🏛 <b>OFFICIAL INVOICE</b>\n"
            "————————————————————\n"
            f"📦 <b>Program:</b> {safe_html(product['title'])}\n"
            f"💰 <b>Price:</b> <code>{display_price} ETB</code>\n\n"
            f"📥 <b>Transfer Details:</b>\n"
            f"🏦 <b>Commercial Bank (CBE)</b>\n<code>{settings.BANK_CBE}</code>\n👤 {safe_html(settings.BANK_CBE_NAME)}\n\n"
            f"🏦 <b>Bank of Abyssinia (BOA)</b>\n<code>{settings.BANK_BOA}</code>\n👤 {safe_html(settings.BANK_BOA_NAME)}\n\n"
            "————————————————————\n"
            "📸 <b>Final Step:</b> Send the screenshot of your transfer below.\n\n"
            "💡 <b>Use the button below if you need to go back.</b>"
        )
    else:
        instruction = (
            f"🏛 <b>ይፋዊ የክፍያ መመሪያ</b>\n"
            "————————————————————\n"
            f"📦 <b>ፕሮግራም፦</b> {safe_html(product['title'])}\n"
            f"💰 <b>የአሰልጣኝ ክፍያ፦</b> <code>{display_price} ብር</code>\n\n"
            f"📥 <b>የባንክ አካውንት ዝርዝር፦</b>\n"
            f"🏦 <b>የኢትዮጵያ ንግድ ባንክ (CBE)</b>\n<code>{settings.BANK_CBE}</code>\n👤 {safe_html(settings.BANK_CBE_NAME)}\n\n"
            f"🏦 <b>አቢሲኒያ ባንክ (BOA)</b>\n<code>{settings.BANK_BOA}</code>\n👤 {safe_html(settings.BANK_BOA_NAME)}\n\n"
            "————————————————————\n"
            "📸 <b>የመጨረሻ ደረጃ፦</b> የከፈሉበትን ደረሰኝ (Screenshot) ይላኩ。\n\n"
            "💡 <b>ለመመለስ ከታች ያለውን ቁልፍ ይጠቀሙ።</b>"
        )

    await bot.send_chat_action(callback.message.chat.id, "typing")
    await callback.message.answer(instruction, reply_markup=rb.cancel_payment_kb(lang), parse_mode="HTML")
    await state.set_state(PaymentStates.awaiting_proof)


@router.message(F.text.in_({"❌ Cancel Payment", "❌ ክፍያውን ሰርዝ"}))
async def cancel_payment(message: types.Message, state: FSMContext, db: Database):
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    lang = user_data.get("language", "EN") if user_data else "EN"

    await state.clear()
    text = "❌ Payment cancelled. Returning to Dashboard..." if lang == "EN" else "❌ ክፍያ ተሰርዟል። ወደ ዋናው ገጽ በመመለስ ላይ..."
    try:
        await message.answer(text, reply_markup=types.ReplyKeyboardRemove())
    except Exception as e:
        logger.warning(f"Failed to send cancel notice: {e}")
    try:
        await message.answer("🏠 <b>DASHBOARD</b>", reply_markup=rb.main_menu(lang), parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Failed to send dashboard menu: {e}")


@router.message(PaymentStates.awaiting_proof, F.photo)
async def handle_payment_proof(message: types.Message, state: FSMContext, db: Database, bot: Bot):
    data = await state.get_data()
    user_id = message.from_user.id
    user_record = await db.get_user(user_id)
    lang = user_record.get("language", "EN") if user_record else "EN"

    product_id = data.get('selected_product_id')
    amount = data.get('amount')
    proof_file_id = message.photo[-1].file_id

    # ANTI-REPLAY / ANTI-FRAUD SHIELD: Prevent reusing existing proof screenshots
    duplicate = await db.check_duplicate_proof(proof_file_id)
    if duplicate:
        await state.clear()
        if lang == "EN":
            dup_msg = (
                "⚠️ <b>DUPLICATE RECEIPT DETECTED</b>\n\n"
                "This transfer screenshot has already been submitted in our system and cannot be reused.\n\n"
                "If you made a new payment, please upload the distinct official transfer receipt for this order."
            )
        else:
            dup_msg = (
                "⚠️ <b>ይህ ደረሰኝ ከዚህ ቀደም ተመዝግቧል!</b>\n\n"
                "ይህ የክፍያ ማረጋገጫ ፎቶ ቀደም ሲል በሲስተሙ ውስጥ ጥቅም ላይ ውሏል፤ ደግመው መጠቀም አይችሉም።\n\n"
                "እባክዎ ለአዲሱ ትዕዛዝ የተከፈለበትን ትክክለኛ እና አዲስ ደረሰኝ ይላኩ።"
            )
        await message.answer(dup_msg, reply_markup=rb.main_menu(lang), parse_mode="HTML")
        return

    # 1. IMMEDIATE FEEDBACK & REMOVE CANCEL KEYBOARD
    progress_text = "📡 <b>Connecting to secure server...</b>" if lang == "EN" else "📡 <b>ከሴኩዩር ሰርቨር ጋር በመገናኘት ላይ...</b>"
    progress_msg = await message.answer(progress_text, reply_markup=types.ReplyKeyboardRemove(), parse_mode="HTML")

    # 2. SAVE TO DATABASE
    payment_id = await db.create_payment(
        user_id=user_id,
        product_id=product_id,
        proof_id=proof_file_id,
        amount=amount
    )

    # 3. BACKGROUND PROGRESS ANIMATION (EDIT)
    stages = [
        ("📤 Syncing receipt...", "📤 ደረሰኝዎን በማመሳሰል ላይ..."),
        ("🔍 Analyzing details...", "🔍 የክፍያ ዝርዝሮችን በመፈተሽ ላይ..."),
        ("⏳ Awaiting Coach Confirmation...", "⏳ የአሰልጣኝ ማረጋገጫ በመጠበቅ ላይ...")
    ]

    for en, am in stages:
        await asyncio.sleep(0.8)
        stage_text = en if lang == "EN" else am
        try:
            await progress_msg.edit_text(f"✨ <b>{html.escape(stage_text)}</b>", parse_mode="HTML")
        except Exception:
            pass

    # 4. THE "SAFE" REVEAL (delete progress message and send fresh one)
    try:
        await progress_msg.delete()
    except Exception:
        pass

    if lang == "EN":
        final_text = (
            "✅ <b>RECEIPT LOGGED</b>\n\n"
            "I've received your transfer. Stay ready.\n"
            "Your product will be delivered here the moment I verify it. 🔥"
        )
    else:
        final_text = (
            "✅ <b>ደረሰኙ ተመዝግቧል</b>\n\n"
            "የላኩትን ደረሰኝ ተቀብያለሁ። ለለውጥ ዝግጁ ይሁኑ፤\n"
            "ልክ እንደተረጋገጠ እቅድዎን እዚህ እልክልዎታለሁ። 🔥"
        )

    # 5. Send fresh message WITH the main menu keyboard
    await message.answer(final_text, reply_markup=rb.main_menu(lang), parse_mode="HTML")

    # 6. Fire-and-forget admin notification (background task)
    asyncio.create_task(
        notify_admin_payment(bot, message, data, payment_id, proof_file_id, db)
    )

    # 7. Final State Clear
    await state.clear()


async def notify_admin_payment(bot: Bot, message: types.Message, data: dict, payment_id: int, proof_id: str, db: Database):
    """The Founder Alert: Performs real-time forensic verification, stamps visual audit banner, and forwards to group."""
    try:
        product = await db._pool.fetchrow("SELECT title FROM products WHERE id = $1", data.get('selected_product_id'))
        product_title = product['title'] if product else "Custom Fitness Plan"

        user_rec = await db.get_user(message.from_user.id)
        lang = (user_rec.get("language") if user_rec else data.get("language")) or "EN"
        amount = float(data.get("amount", 399.0))

        # 1. Run Forensic Pipeline & Stamp Image with Visual Audit Banner
        photo_payload, caption, keyboard = await process_and_stamp_incoming_proof(
            bot=bot,
            db=db,
            proof_file_id=proof_id,
            payment_id=payment_id,
            stream="sales",
            user_id=message.from_user.id,
            user_name=message.from_user.full_name,
            username=message.from_user.username,
            lang=lang,
            expected_amount=amount,
            item_title=product_title,
        )

        # 2. Forward Stamped Image with Executive Caption & Action Buttons to Admin Channel
        await bot.send_photo(
            chat_id=settings.ADMIN_PAYMENT_LOG_ID,
            photo=photo_payload,
            caption=caption,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error("Error in notify_admin_payment for PID #%s: %s", payment_id, e, exc_info=True)
        # Resilient fallback: ensure admin always receives notification
        try:
            kb = InlineKeyboardBuilder()
            kb.button(text="✅ APPROVE & SEND PDF", callback_data=f"approve_{payment_id}")
            kb.button(text="❌ REJECT / FAKE", callback_data=f"reject_{payment_id}")
            kb.adjust(1)
            await bot.send_photo(
                chat_id=settings.ADMIN_PAYMENT_LOG_ID,
                photo=proof_id,
                caption=f"💸 <b>NEW PAYMENT #{payment_id}</b> (Fallback mode)\nUser: {html.escape(message.from_user.full_name)}\nAmount: <code>{data.get('amount')} ETB</code>",
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        except Exception as inner_e:
            logger.error("Critical delivery failure in notify_admin_payment fallback: %s", inner_e)

from datetime import datetime, timezone

def format_audit_report(local, bank_data, elapsed, is_real, is_hilawe):
    # Parsing
    data = bank_data
    payer = data.get("payer", "Unknown")
    receiver = data.get("receiver", "N/A")
    amount = data.get("amount", 0)
    
    # Time Calculation
    time_display = "(Time unknown)"
    try:
        payment_time_str = data.get("date")
        if payment_time_str:
            pay_dt = datetime.fromisoformat(payment_time_str.replace("Z", "+00:00"))
            minutes_diff = int((datetime.now(timezone.utc) - pay_dt).total_seconds() / 60)
            time_display = f"({minutes_diff}m ago)"
    except: pass

    # Construct
    if is_real and is_hilawe:
        return (
            f"✅ <b>TRANSACTION VERIFIED</b>\n"
            f"────────────────────\n"
            f"👤 <b>Payer:</b> <code>{payer}</code>\n"
            f"💰 <b>Amount:</b> {amount:,.2f} ETB\n"
            f"🏦 <b>Bank:</b> {local['provider']} {time_display}\n"
            f"🆔 <b>Ref ID:</b> <code>{local['ref']}</code>\n"
            f"🎯 <b>Receiver:</b> {receiver}\n\n"
            f"🟢 <b>Outcome:</b> Approved.\n"
            f"⏱️ <b>Audit duration:</b> {elapsed:.2f}s"
        )
    else:
        fail_reason = "Receiver name mismatch" if is_real else "Invalid / Not found"
        return (
            f"🚨 <b>TRANSACTION REJECTED</b>\n"
            f"────────────────────\n"
            f"❌ <b>Result:</b> {fail_reason}\n"
            f"👤 <b>Payer:</b> {payer} {time_display}\n"
            f"💰 <b>Amount:</b> {amount:,.2f} ETB\n"
            f"🆔 <b>Ref ID:</b> <code>{local['ref']}</code>\n\n"
            f"⚠️ <b>Protocol:</b> Do not release products.\n"
            f"⏱️ <b>Audit duration:</b> {elapsed:.2f}s"
        )


@router.callback_query(F.data.startswith("info_"))
async def show_full_audit_report(callback: types.CallbackQuery):
    payment_id = int(callback.data.split("_")[1])
    
    # Retrieve the pre-formatted report from cache
    report = REPORT_CACHE.get(payment_id)
    
    if not report:
        await callback.answer("⚠️ Report not found (expired).", show_alert=True)
        return

    # Reply to the message with the exact report format you provided
    await callback.message.reply(report, parse_mode="HTML")
    await callback.answer("✅ Full report displayed.")

@router.message(F.chat.type == "private", F.photo)
async def handle_unprompted_photo(message: types.Message, state: FSMContext, bot: Bot, db: Database):
    """
    Catches photos sent outside awaiting_proof.
    If the user is in the state of buying (completed onboarding & unpaid),
    it is treated as an active payment proof and forwarded to the payment group.
    """
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    lang = ((user.get('language') if user else 'AM') or 'AM').upper()

    # Real-time check: user has an active approved workout plan
    has_active_plan = await db.fetchval(
        "SELECT 1 FROM payments WHERE user_id = $1 AND status = 'approved' LIMIT 1",
        user_id
    )

    # User is in "state of buying" if they finished onboarding and have no approved plan
    is_buying_state = bool(user and user.get("onboarding_completed") and not has_active_plan)

    if is_buying_state:
        proof_file_id = message.photo[-1].file_id

        # Anti-replay / duplicate shield
        duplicate = await db.check_duplicate_proof(proof_file_id)
        if duplicate:
            dup_msg = (
                "⚠️ <b>ይህ ደረሰኝ ከዚህ ቀደም ተመዝግቧል!</b>\n\n"
                "ይህ የክፍያ ማረጋገጫ ፎቶ ቀደም ሲል በሲስተሙ ውስጥ ጥቅም ላይ ውሏል፤ ደግመው መጠቀም አይችሉም።\n\n"
                "እባክዎ ለአዲሱ ትዕዛዝ የተከፈለበትን ትክክለኛ እና አዲስ ደረሰኝ ይላኩ።"
            ) if lang == "AM" else (
                "⚠️ <b>DUPLICATE RECEIPT DETECTED</b>\n\n"
                "This transfer screenshot has already been submitted in our system and cannot be reused.\n\n"
                "If you made a new payment, please upload the distinct official transfer receipt for this order."
            )
            await message.answer(dup_msg, reply_markup=rb.main_menu(lang), parse_mode="HTML")
            return

        product_id = resolve_user_product_id(user)
        amount = resolve_user_price(user)

        payment_id = await db.create_payment(
            user_id=user_id,
            product_id=product_id,
            proof_id=proof_file_id,
            amount=amount
        )

        reassurance = (
            "✅ <b>የክፍያ ደረሰኝዎ ደርሶናል!</b>\n\n"
            "ወንድሜ/እህቴ የላኩት ደረሰኝ በቀጥታ ወደ ማረጋገጫ ሲስተም ገብቷል። "
            "ኮች ህላዌ እንዳረጋገጠው ወዲያውኑ የ8-ሳምንት እቅድዎ እዚህ ይላክልዎታል! 🔥"
        ) if lang == "AM" else (
            "✅ <b>RECEIPT RECEIVED</b>\n\n"
            "Your transfer receipt has been forwarded directly to Coach Hilawe for verification. "
            "Your plan will be unlocked right here the moment it is confirmed! 🔥"
        )
        await message.answer(reassurance, reply_markup=rb.main_menu(lang), parse_mode="HTML")

        # Forward stamped receipt to Payment Review Group
        asyncio.create_task(
            notify_admin_payment(
                bot=bot,
                message=message,
                data={"selected_product_id": product_id, "amount": amount, "language": lang},
                payment_id=payment_id,
                proof_id=proof_file_id,
                db=db
            )
        )

        # Alert Founder ID (1131741322) directly
        founder_alert = (
            f"📸 <b>ቀጥታ የተላከ ደረሰኝ (Direct Payment Proof)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User:</b> {html.escape(message.from_user.full_name)} (`{user_id}`)\n"
            f"🔗 <b>Username:</b> @{message.from_user.username or 'No Username'}\n"
            f"💰 <b>Expected:</b> <code>{amount} ETB</code> | PID: <code>#{payment_id}</code>\n"
            f"📡 ወደ ክፍያ ቻናል ተልኳል (Sent to Payment Channel)"
        )
        try:
            await bot.send_message(admin_id, founder_alert, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Failed to alert founder of direct payment photo: {e}")
        return

    # Not in buying state (unregistered or already paid member)
    caption = (
        f"📸 <b>ፎቶ ከደንበኛ (User Photo)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> {html.escape(message.from_user.full_name)} (`{user_id}`)\n"
        f"🔗 <b>Username:</b> @{message.from_user.username or 'No Username'}\n"
        f"📊 <b>Onboarding:</b> {'Completed' if user and user.get('onboarding_completed') else 'Not Started'}\n"
        f"💳 <b>Paid:</b> {'Yes' if has_active_plan else 'No'}"
    )
    try:
        await bot.send_photo(
            chat_id=admin_id,
            photo=message.photo[-1].file_id,
            caption=caption,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Failed to forward user photo to founder: {e}")

    if not user or not user.get("onboarding_completed"):
        await message.answer(
            "ሠላም! ፎቶህ/ሽ ደርሶኛል። ለአንተ/አንቺ የሚስማማውን የሰውነት መቀየሪያ እቅድ ለማግኘት "
            "እባክዎ /start ብለው የ2-ደቂቃ ፈጣን ምዘናውን ይጀምሩ። 💪",
            parse_mode="HTML"
        )


def build_contextual_query_keyboard(
    query: str,
    user: dict | None,
    has_active_plan: bool,
    product_id: int,
    price: float,
    bot_username: str
) -> types.InlineKeyboardMarkup | None:
    """
    Builds smart, context-aware inline action buttons based on user query intent.
    Eliminates repetitive generic buttons and attaches only relevant actions.
    """
    kb = InlineKeyboardBuilder()
    q = (query or "").lower()

    # 1. Unregistered / Incomplete Onboarding
    if not user or not user.get("onboarding_completed"):
        kb.button(text="🚀 የ2-ደቂቃ ምዘናውን ጀምር", url=f"https://t.me/{bot_username}?start=assess")
        kb.adjust(1)
        return kb.as_markup()

    # 2. Paid Members
    if has_active_plan:
        plan_keywords = ["እቅድ", "ፕላን", "ልምምድ", "ምግብ", "ስፖርት", "ወርክአውት", "ፕሮግራም", "plan", "workout", "meal"]
        help_keywords = ["ስልክ", "ሰው", "ድጋፍ", "ጥያቄ", "help", "support", "call"]
        
        if any(k in q for k in plan_keywords):
            kb.button(text="📦 የእኔን እቅድ ተመልከት", callback_data="view_current_plan")
        elif any(k in q for k in help_keywords):
            kb.button(text="💬 አሰልጣኝ ህላዌን አናግር", url=f"https://t.me/{settings.SUPPORT_BOT_USERNAME}")
        
        if kb.buttons:
            kb.adjust(1)
            return kb.as_markup()
        return None

    # 3. Hot Unpaid Leads (Context-Specific Routing)
    
    # Reason A: Settings / Profile Change Intent
    settings_keywords = ["ስህተት", "መቀየር", "ልቀይር", "መገለጫ", "ማስተካከያ", "ተሳስቻለሁ", "አስተካክል", "change", "profile", "settings"]
    if any(k in q for k in settings_keywords):
        kb.button(text="⚙️ መገለጫዬን አስተካክል", callback_data="open_settings")
        kb.adjust(1)
        return kb.as_markup()

    # Reason B: Direct Human Contact / Support Request
    contact_keywords = ["ስልክ", "ማናገር", "ደውል", "ደውሉልኝ", "ኮል", "ሰው ማናገር", "አድራሻ", "call", "support", "phone"]
    if any(k in q for k in contact_keywords):
        kb.button(text="💬 አሰልጣኝ ህላዌን አናግር", url=f"https://t.me/{settings.SUPPORT_BOT_USERNAME}")
        kb.button(text=f"💳 ክፍያ ጀምር ({int(price)} ብር)", callback_data=f"pay_{product_id}")
        kb.adjust(1)
        return kb.as_markup()

    # Reason C: Payment / Banking / Transfer / Account Inquiries
    payment_keywords = ["ባንክ", "ቴሌብር", "አካውንት", "መክፈል", "የት ልክፈል", "አከፋፈል", "cbe", "boa", "telebirr", "bank"]
    if any(k in q for k in payment_keywords):
        kb.button(text=f"💳 ክፍያ ጀምር ({int(price)} ብር)", callback_data=f"pay_{product_id}")
        if any(w in q for w in ["የለኝም", "ችግር", "አልችልም", "እንዴት"]):
            kb.button(text="💬 የክፍያ ድጋፍ አግኝ", url=f"https://t.me/{settings.SUPPORT_BOT_USERNAME}")
        kb.adjust(1)
        return kb.as_markup()

    # Reason D: Fitness Advice, Goals, Problem Inquiries (Hip dips, belly, skinny, fatloss, program)
    fitness_keywords = [
        "ሂፕ ዲፕ", "ቦርጭ", "ክብደት", "ጡንቻ", "ዳሌ", "ቅጥነት", "ውፍረት", "ስብ", 
        "ምግብ", "ፆም", "ፕሮቲን", "ውጤት", "ሳምንት", "ጂም", "ቤት", "ልምምድ", 
        "ምከር", "አማክረኝ", "ምን ላድርግ", "ምን ባደርግ", "ሆድ", "ወገብ"
    ]
    if any(k in q for k in fitness_keywords):
        kb.button(text=f"🔥 የ8-ሳምንት እቅዴን ጀምር ({int(price)} ብር)", callback_data=f"pay_{product_id}")
        kb.adjust(1)
        return kb.as_markup()

    # Reason E: Greetings / Introduction ("ማነህ", "ማን ነህ", etc.)
    intro_keywords = ["ማነህ", "ማን ነህ", "who are you", "ስለ አንተ"]
    if any(k in q for k in intro_keywords):
        kb.button(text=f"🎯 ለእኔ የተዘጋጀውን እቅድ እይ ({int(price)} ብር)", callback_data=f"pay_{product_id}")
        kb.adjust(1)
        return kb.as_markup()

    # Default fallback for unclassified sales questions: provide direct checkout
    kb.button(text=f"💳 ክፍያ ጀምር ({int(price)} ብር)", callback_data=f"pay_{product_id}")
    kb.adjust(1)
    return kb.as_markup()


@router.message(
    F.chat.type == "private",
    ~Command("start"),
    ~Command("admin"),
    ~Command("help"),
    ~Command("reset"),
    F.text
)
async def handle_user_query_message(message: types.Message, bot: Bot, db: Database):
    """
    Ultra-localized Coach Hilawe AI response for all unhandled client text.
    Provides instant answers in clean Fidel Amharic, dynamic sales button,
    and forwards executive summary to Founder ID (1131741322).
    """
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    # 1. Typing action for realistic feedback
    try:
        await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    except Exception:
        pass

    # 2. Resolve checkout details (product ID and dynamic price)
    product_id = resolve_user_product_id(user)
    price = resolve_user_price(user)

    # 3. Generate Coach Hilawe reply via AI service
    ai_reply = await generate_coach_reply(
        query=message.text,
        user=user,
        price=price
    )

    # 4. Check active approved workout plan status
    has_active_plan = await db.fetchval(
        "SELECT 1 FROM payments WHERE user_id = $1 AND status = 'approved' LIMIT 1",
        user_id
    )

    # 5. Build context-aware dynamic action buttons
    bot_user = await bot.get_me()
    bot_username = bot_user.username or "CoachHilaweBot"
    reply_markup = build_contextual_query_keyboard(
        query=message.text,
        user=user,
        has_active_plan=bool(has_active_plan),
        product_id=product_id,
        price=price,
        bot_username=bot_username
    )

    # 6. Send reply to user
    try:
        await message.answer(ai_reply, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        await message.answer(ai_reply, reply_markup=reply_markup)

    # 7. Forward summary card strictly to Founder ID (1131741322)
    user_status = (
        "✅ Paid Member" if has_active_plan else
        "🔥 Hot Unpaid Lead" if (user and user.get("onboarding_completed")) else
        "🆕 New Prospect"
    )
    user_goal = user.get("goal", "Not Specified") if user else "Not Specified"

    founder_card = (
        f"💬 <b>የደንበኛ ጥያቄ እና የኮች ምላሽ (Customer Query)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> {html.escape(message.from_user.full_name)} (`{user_id}`)\n"
        f"🔗 <b>Username:</b> @{message.from_user.username or 'No Username'}\n"
        f"📊 <b>Status:</b> {user_status} | 💰 <b>Price:</b> {int(price)} ETB\n"
        f"🎯 <b>Goal:</b> {html.escape(str(user_goal))}\n\n"
        f"❓ <b>ጥያቄ (Query):</b>\n<i>\"{html.escape(message.text)}\"</i>\n\n"
        f"🤖 <b>የኮች ምላሽ (Coach Reply):</b>\n<i>\"{html.escape(ai_reply)}\"</i>"
    )

    admin_kb = InlineKeyboardBuilder()
    if message.from_user.username:
        admin_kb.button(text="💬 Open User Chat", url=f"https://t.me/{message.from_user.username}")
    else:
        admin_kb.button(text="💬 Open User Chat", url=f"tg://user?id={user_id}")
    admin_kb.adjust(1)

    try:
        await bot.send_message(
            chat_id=admin_id,
            text=founder_card,
            reply_markup=admin_kb.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Failed to forward query summary to founder {admin_id}: {e}")