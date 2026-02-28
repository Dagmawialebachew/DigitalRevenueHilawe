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
@router.callback_query(F.data.startswith("pay_"))
async def initiate_payment(callback: types.CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    product_id = int(callback.data.split("_")[1])
    data = await state.get_data()
    lang = data.get("language", "EN")
    
    product = await db._pool.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
    if not product:
        return await callback.answer("⚠️ System Error: Plan not found.")

    await state.update_data(selected_product_id=product_id, amount=product['price'])
    
    instruction = (
        f"🏛 *OFFICIAL INVOICE*\n"
        f"————————————————————\n"
        f"📦 *Program:* {product['title']}\n"
        f"💰 *Price:* `{product['price']} ETB`\n\n"
        f"📥 *Transfer Details:*\n"
        f"`{settings.BANK_DETAILS}`\n"
        f"————————————————————\n"
        f"📸 *Final Step:* Send the screenshot of your transfer below.\n\n"
        f"💡 *Use the button below if you need to go back.*"
    ) if lang == "EN" else (
        f"🏛 *ይፋዊ የክፍያ መመሪያ*\n"
        f"————————————————————\n"
        f"📦 *እቅድ፦* {product['title']}\n"
        f"💰 *የአሰልጣኝ ክፍያ፦* `{product['price']} ብር`\n\n"
        f"📥 *የባንክ አካውንት ዝርዝር፦*\n"
        f"`{settings.BANK_DETAILS}`\n"
        f"————————————————————\n"
        f"📸 *የመጨረሻ ደረጃ፦* የከፈሉበትን ደረሰኝ (Screenshot) ይላኩ።\n\n"
        f"💡 *ለመመለስ ከታች ያለውን ቁልፍ ይጠቀሙ።*"
    )

    await bot.send_chat_action(callback.message.chat.id, ChatAction.TYPING)
    await asyncio.sleep(0.5)
    
    # Send instructions with the CANCEL Reply Keyboard
    await callback.message.answer(instruction, reply_markup=rb.cancel_payment_kb(lang))
    await state.set_state(PaymentStates.awaiting_proof)
    await callback.answer()


@router.message(F.text.in_({"❌ Cancel Payment", "❌ ክፍያውን ሰርዝ"}))
async def cancel_payment(message: types.Message, state: FSMContext, lang: str = "EN"):
    await state.clear()
    text = "❌ Payment cancelled. Returning to Dashboard..." if lang == "EN" else "❌ ክፍያ ተሰርዟል። ወደ ዋናው ገጽ በመመለስ ላይ..."
    await message.answer(text, reply_markup=types.ReplyKeyboardRemove()) # Remove the cancel button
    # Here you can trigger your main menu handler
    await message.answer("🏠 *DASHBOARD*", reply_markup=kb.main_menu(lang))
    
@router.message(PaymentStates.awaiting_proof, F.photo)
async def handle_payment_proof(message: types.Message, state: FSMContext, db: Database, bot: Bot):
    data = await state.get_data()
    lang = data.get("language", "EN")
    user_id = message.from_user.id
    product_id = data.get('selected_product_id')
    amount = data.get('amount')
    proof_file_id = message.photo[-1].file_id 

    # 1. IMMEDIATE FEEDBACK & REMOVE CANCEL KEYBOARD
    # We use a fresh message to remove the reply keyboard immediately
    progress_msg = await message.answer(
        "📡 *Connecting to secure server...*" if lang == "EN" else "📡 *ከሴኩዩር ሰርቨር ጋር በመገናኘት ላይ...*",
        reply_markup=types.ReplyKeyboardRemove()
    )

    # 2. SAVE TO DATABASE
    payment_id = await db.create_payment(
        user_id=user_id,
        product_id=product_id,
        proof_id=proof_file_id,
        amount=amount
    )

    # 🚀 3. BACKGROUND ADMIN NOTIFICATION
    

    stages = [
        ("📤 Syncing receipt...", "📤 ደረሰኝዎን በማመሳሰል ላይ..."),
        ("🔍 Analyzing details...", "🔍 የክፍያ ዝርዝሮችን በመፈተሽ ላይ..."),
        ("⏳ Awaiting Coach Confirmation...", "⏳ የአሰልጣኝ ማረጋገጫ በመጠበቅ ላይ...")
    ]
    
    for en, am in stages:
        await asyncio.sleep(0.8)
        text = en if lang == "EN" else am
        try:
            await progress_msg.edit_text(f"✨ *{text}*")
        except Exception:
            # If editing fails (e.g. user deleted the message), just keep going
            pass

    # 5. THE "SAFE" REVEAL
    # Instead of editing the progress message, we delete it and send a fresh one
    try:
        await progress_msg.delete()
    except Exception:
        pass

    final_text = (
        "✅ *RECEIPT LOGGED*\n\n"
        "I've received your transfer. Stay ready. "
        "Your product will be delivered here the moment I verify it. 🔥"
    ) if lang == "EN" else (
        "✅ *ደረሰኙ ተመዝግቧል*\n\n"
        "የላኩትን ደረሰኝ ተቀብያለሁ። ለለውጥ ዝግጁ ይሁኑ፤ "
        "ልክ እንደተረጋገጠ እቅድዎን እዚህ እልክልዎታለሁ። 🔥"
    )

    # Send fresh message WITH the main menu keyboard
    await message.answer(
        final_text, 
        reply_markup=rb.main_menu(lang),
        parse_mode="Markdown"
    )
    asyncio.create_task(
        notify_admin_payment(bot, message, data, payment_id, proof_file_id, db)
    )

    # 6. Final State Clear
    await state.clear()
    
async def notify_admin_payment(bot: Bot, message: types.Message, data: dict, payment_id: int, proof_id: str, db: Database):
    """The Founder Alert: Sends the receipt + data + action buttons to Admins."""
    try:
        # Fetch the product name
        product = await db._pool.fetchrow("SELECT title FROM products WHERE id = $1", data['selected_product_id'])
        
        # Get Language from state data
        lang_code = data.get("language", "EN")
        lang_display = "🇺🇸 English" if lang_code == "EN" else "🇪🇹 አማርኛ (Amharic)"
        
        username = f"@{message.from_user.username}" if message.from_user.username else "No Username"
        
        admin_caption = (
            f"💸 *MONEY IN: NEW PAYMENT*\n"            
            f"————————————————————\n"
            f"👤 *Athlete:* {message.from_user.full_name} | {username}\n"
            f"🆔 *User ID:* `{message.from_user.id}`\n"
            f"🌍 *Language:* `{lang_display}`\n" # <--- Added Language Tag
            f"————————————————————\n"
            f"📦 *Plan:* {product['title']}\n"
            f"💰 *Amount:* `{data['amount']} ETB`\n"
            f"🎫 *Payment ID:* #{payment_id}\n"
            f"————————————————————\n"
            f"⚡️ *Verify receipt and choose action:* "
        )
        
        kb_builder = InlineKeyboardBuilder()
        # We pass the payment_id. The admin handler will look up the user's 
        # language from the DB when they click these buttons.
        kb_builder.button(text="✅ APPROVE & SEND PDF", callback_data=f"approve_{payment_id}")
        kb_builder.button(text="❌ REJECT / FAKE", callback_data=f"reject_{payment_id}")
        kb_builder.adjust(1)

        await bot.send_photo(
            chat_id=settings.ADMIN_PAYMENT_LOG_ID,
            photo=proof_id,
            caption=admin_caption,
            reply_markup=kb_builder.as_markup(),
            parse_mode="Markdown"
        )

    except Exception as e:
        logging.error(f"Global admin notification error: {e}")