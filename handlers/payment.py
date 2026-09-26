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
REPORT_CACHE = {}

router = Router(name="payment")
logger = logging.getLogger(__name__)

admin_id = 1131741322

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
    await message.answer(text, reply_markup=types.ReplyKeyboardRemove())
    await message.answer("🏠 <b>DASHBOARD</b>", reply_markup=rb.main_menu(lang), parse_mode="HTML")


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

@router.message(
    F.chat.type == "private",
    ~Command("start"),
    ~Command("admin"),
    F.text
)
async def forward_random_signals(message: types.Message, bot: Bot, db: Database):
    user = await db.get_user(message.from_user.id)
    lang = (user.get('language') or 'EN').upper()
    
    user_info = (
        f"👤User: {message.from_user.full_name}\n"
        f"🆔ID:{message.from_user.id}\n"
        f"🔗Username: @{message.from_user.username or 'No Username'}"
    )
    
    await bot.send_message(admin_id, f"*📩 Random Signal:*\n\n{user_info}\n\n*Content:*")
    await message.forward(admin_id)

    if lang == "AM":
        reply_text = (
            "መልዕክትዎ ደርሶኛል! 🙏\n\n"
            "ተጨማሪ ጥያቄ ወይም እርዳታ ካስፈለገዎት "
            "ፈጣን ምላሽ ለማግኘት እዚ ላይ ያዋሩኝ፦ @CoachHilaweSupportBot 😊"
        )
    else:
        reply_text = (
            "I’ve received your message! 🙏\n\n"
            "If you have any specific questions or issues, "
            "please contact our support team here: @CoachHilaweSupportBot 😊"
        )

    await message.answer(reply_text)