import asyncio
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatAction
from database.db import Database
from keyboards import inline as kb
from keyboards import reply as rb
from utils.localization import get_text
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import settings
import logging
router = Router(name="payment")
logger = logging.getLogger(__name__)
class PaymentStates(StatesGroup):
    awaiting_proof = State()
import html


@router.callback_query(F.data.startswith("pay_"))
async def initiate_payment(callback: types.CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    import html
    from datetime import datetime
    
    await callback.answer() # Stop the spinner immediately
    
    product_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    user_data = await db.get_user(user_id)
    lang = user_data.get("language", "EN") if user_data else "EN"

    product = await db._pool.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
    if not product:
        return await callback.message.answer("⚠️ System Error: Plan not found.")

    # --- Price Logic with Expiry Check ---
    from datetime import datetime, timezone
    
    display_price = product['price']
    now = datetime.now(timezone.utc)
    
    deal_price = user_data.get("deal_price")
    deal_expiry = user_data.get("deal_expires_at")

    # SAFETY CHECK: Ensure deal_expiry is timezone-aware
    if deal_expiry and deal_expiry.tzinfo is None:
        deal_expiry = deal_expiry.replace(tzinfo=timezone.utc)

    # Now this comparison is bulletproof
    if deal_price and deal_expiry and now < deal_expiry:
        display_price = deal_price
        print(f"✅ Deal Active! Using price: {display_price}")
    else:
        print(f"❌ Deal Expired or Not Found. Using original: {display_price}")

    await state.update_data(selected_product_id=product_id, amount=display_price)

    # Helper to safe-escape settings
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
            f"📱 <b>Telebirr</b>\n<code>{settings.BANK_TELEBIRR}</code>\n👤 {safe_html(settings.BANK_TELEBIRR_NAME)}\n"
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
            f"📱 <b>ቴሌብር</b>\n<code>{settings.BANK_TELEBIRR}</code>\n👤 {safe_html(settings.BANK_TELEBIRR_NAME)}\n"
            "————————————————————\n"
            "📸 <b>የመጨረሻ ደረጃ፦</b> የከፈሉበትን ደረሰኝ (Screenshot) ይላኩ።\n\n"
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
    await message.answer(text, reply_markup=types.ReplyKeyboardRemove())  # Remove the cancel button
    await message.answer("🏠 <b>DASHBOARD</b>", reply_markup=rb.main_menu(lang), parse_mode="HTML")

@router.message(PaymentStates.awaiting_proof, F.photo)
async def handle_payment_proof(message: types.Message, state: FSMContext, db: Database, bot: Bot):
    # Keep state data for product/amount but fetch language from DB
    data = await state.get_data()
    user_id = message.from_user.id
    user_record = await db.get_user(user_id)
    lang = user_record.get("language", "EN") if user_record else "EN"

    product_id = data.get('selected_product_id')
    amount = data.get('amount')
    proof_file_id = message.photo[-1].file_id

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
            # Use HTML and escape the stage text to avoid entity issues
            await progress_msg.edit_text(f"✨ <b>{html.escape(stage_text)}</b>", parse_mode="HTML")
        except Exception:
            # If editing fails (e.g. message deleted), continue silently
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

    # 5. Send fresh message WITH the main menu keyboard (HTML parse mode)
    await message.answer(final_text, reply_markup=rb.main_menu(lang), parse_mode="HTML")

    # 6. Fire-and-forget admin notification (background)
    asyncio.create_task(
        notify_admin_payment(bot, message, data, payment_id, proof_file_id, db)
    )

    # 7. Final State Clear
    await state.clear()

import html  # Make sure this is imported at the top of your file

async def notify_admin_payment(bot: Bot, message: types.Message, data: dict, payment_id: int, proof_id: str, db: Database):
    """The Founder Alert: Sends the receipt + data + action buttons to Admins."""
    try:
        # Fetch the product name
        product = await db._pool.fetchrow("SELECT title FROM products WHERE id = $1", data['selected_product_id'])
        
        # Get Language from state data
        lang_code = data.get("language", "EN")
        lang_display = "🇺🇸 English" if lang_code == "EN" else "🇪🇹 አማርኛ (Amharic)"
        
        # Safely escape user-generated strings to prevent parsing errors
        full_name = html.escape(message.from_user.full_name)
        username = html.escape(f"@{message.from_user.username}") if message.from_user.username else "No Username"
        product_title = html.escape(product['title'])
        
        # Build caption using HTML (much more reliable)
        admin_caption = (
            f"💸 <b>MONEY IN: NEW PAYMENT</b>\n"            
            f"────────────────────\n"
            f"👤 <b>Athlete:</b> {full_name} | {username}\n"
            f"🆔 <b>User ID:</b> <code>{message.from_user.id}</code>\n"
            f"🌍 <b>Language:</b> <code>{lang_display}</code>\n"
            f"────────────────────\n"
            f"📦 <b>Plan:</b> {product_title}\n"
            f"💰 <b>Amount:</b> <code>{data['amount']} ETB</code>\n"
            f"🎫 <b>Payment ID:</b> #{payment_id}\n"
            f"────────────────────\n"
            f"⚡️ <b>Verify receipt and choose action:</b>"
        )
        
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text="✅ APPROVE & SEND PDF", callback_data=f"approve_{payment_id}")
        kb_builder.button(text="❌ REJECT / FAKE", callback_data=f"reject_{payment_id}")
        kb_builder.adjust(1)

        await bot.send_photo(
            chat_id=settings.ADMIN_PAYMENT_LOG_ID,
            photo=proof_id,
            caption=admin_caption,
            reply_markup=kb_builder.as_markup(),
            parse_mode="HTML"  # Changed from Markdown to HTML
        )

    except Exception as e:
        logging.error(f"Global admin notification error: {e}")
    


admin_id = 1131741322
from aiogram import Router, F, types, Bot
@router.message()
async def forward_random_signals(message: types.Message, bot: Bot, db: Database):
    """
    Forwards random text to Admin and gives the user the Support Bot link.
    """
    # 1. Get user data to check language
    user = await db.get_user(message.from_user.id)
    lang = (user.get('language') or 'EN').upper()
    
    
    # 2. Admin Notification logic
    user_info = (
        f"👤User: {message.from_user.full_name}\n"
        f"🆔ID:{message.from_user.id}\n"
        f"🔗Username: @{message.from_user.username or 'No Username'}"
    )
    
    await bot.send_message(admin_id, f"*📩 Random Signal:*\n\n{user_info}\n\n*Content:*")
    await message.forward(admin_id)

    # 3. Personalized Response based on Language
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
