import asyncio
from datetime import datetime
import logging
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import ReplyKeyboardRemove

from config import settings
from database.db import Database
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards import inline as akb
from testimonial.testimonial_questions import run_testimonial_cycle  # Updated to use your new hybrid keyboard file

router = Router(name="admin")

class AdminStates(StatesGroup):
    # Product Creation Steps
    asking_title = State()
    asking_lang = State()
    asking_gender = State()
    asking_level = State()
    asking_freq = State()
    asking_price = State()
    asking_pdf = State()
    
    # Broadcast Step
    awaiting_broadcast = State()
    awaiting_rejection_reason = State() # New state for rejection
    confirm_broadcast = State()   # Admin sees preview and clicks "Send"
    confirm_rejection = State() # Add this


# --- [ SECTION 1: MAIN DASHBOARD & NAVIGATION ] ---
from aiogram.exceptions import TelegramBadRequest

@router.message(Command("admin"), F.from_user.id.in_(settings.ADMIN_IDS))
@router.message(F.text == "📊 Business Stats", F.from_user.id.in_(settings.ADMIN_IDS))
@router.message(F.text == "💎 Back to Dashboard", F.from_user.id.in_(settings.ADMIN_IDS))
@router.callback_query(F.data == "refresh_admin_stats")
async def admin_dashboard(event: types.Message | types.CallbackQuery, db: Database, state: FSMContext):
    await state.clear()
    await event.answer("📋 Admin Menu", reply_markup=akb.admin_main_menu())
    stats = await db.get_admin_stats_bot()
    
    # 1. Prepare Data
    pending_val = stats['pending_count']
    status_emoji = "🚨" if pending_val > 0 else "✅"
    status_text = "ACTION REQUIRED" if pending_val > 0 else "Operational"

    dashboard_text = (
        "👑 *FOUNDERS COMMAND CENTER*\n"
        "————————————————————\n"
        f"👥 *Total Users:* `{stats['users']}`\n"
        f"💳 *Successful Sales:* `{stats['sales']}`\n"
        f"💰 *Total Revenue:* `{stats['revenue'] or 0} ETB`\n"
        "————————————————————\n"
        f"🕒 *Pending Approvals:* `{pending_val}`\n"
        "————————————————————\n"
        f"Status: {status_emoji} *{status_text}*\n"
        f"⏱ _Last Update: {datetime.now().strftime('%H:%M:%S')}_" # Forces content change
    )

    # 2. Build Inline Buttons (Always attached)
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Refresh Stats", callback_data="refresh_admin_stats")
    builder.adjust(1)
    
    inline_kb = builder.as_markup()

    # 3. Handle Update (Try-Except prevents the "Message Not Modified" crash)
    if isinstance(event, types.Message):
        # Fresh message (Triggered by text button or command)
        await event.answer(dashboard_text, reply_markup=inline_kb)
    else:
        # Edit existing message (Triggered by Refresh inline button)
        try:
            await event.message.edit_text(dashboard_text, reply_markup=inline_kb)
            await event.answer("Stats Updated! ⚡️")
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                # Simply ignore the error or show a "No new data" alert
                await event.answer("Dashboard is already up to date!")
            else:
                raise e # Re-raise if it's a different Bad Request error
# --- [ SECTION 2: STEP-BY-STEP PRODUCT CREATION ] ---

@router.message(F.text == "📦 Add New Product", F.from_user.id.in_(settings.ADMIN_IDS))
async def prod_step_1(message: types.Message, state: FSMContext):
    """Starts the sequential creation flow."""
    await state.set_state(AdminStates.asking_title)
    await message.answer(
        "🏷 *Step 1/7: Product Title*\n"
        "Enter the name of the training Product:", 
        reply_markup=akb.cancel_admin()
    )

@router.message(AdminStates.asking_title, F.text)
async def prod_step_2(message: types.Message, state: FSMContext):
    if message.text.startswith("❌"): return # Handle cancel click
    await state.update_data(title=message.text)
    await state.set_state(AdminStates.asking_lang)
    await message.answer("🌍 *Step 2/7: Target Language*", reply_markup=akb.lang_choice())

@router.callback_query(AdminStates.asking_lang, F.data.startswith("set_lang_"))
async def prod_step_3(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[-1]
    await state.update_data(lang=lang)
    await state.set_state(AdminStates.asking_gender)
    await callback.message.edit_text("🚻 *Step 3/7: Biological Targeting*", reply_markup=akb.gender_choice())

@router.callback_query(AdminStates.asking_gender, F.data.startswith("set_gen_"))
async def prod_step_4(callback: types.CallbackQuery, state: FSMContext):
    gender = callback.data.split("_")[-1]
    await state.update_data(gender=gender)
    await state.set_state(AdminStates.asking_level)
    await callback.message.edit_text("⚖️ *Step 4/7: Required Experience Level*", reply_markup=akb.level_choice())

@router.callback_query(AdminStates.asking_level, F.data.startswith("set_lvl_"))
async def prod_step_5(callback: types.CallbackQuery, state: FSMContext):
    level = callback.data.split("_")[-1]
    await state.update_data(level=level)
    await state.set_state(AdminStates.asking_freq)
    await callback.message.edit_text("📅 *Step 5/7: Training Frequency*", reply_markup=akb.freq_choice())

@router.callback_query(AdminStates.asking_freq, F.data.startswith("set_frq_"))
async def prod_step_6(callback: types.CallbackQuery, state: FSMContext):
    freq = int(callback.data.split("_")[-1])
    await state.update_data(freq=freq)
    await state.set_state(AdminStates.asking_price)
    await callback.message.edit_text("💰 *Step 6/7: Financial Valuation (ETB)*\nEnter the price as a pure number:")

@router.message(AdminStates.asking_price, F.text)
async def prod_step_7(message: types.Message, state: FSMContext):
    if not message.text.replace('.', '', 1).isdigit():
        return await message.answer("❌ *Error:* Please enter a numeric price (e.g. 1500).")
    
    await state.update_data(price=float(message.text))
    await state.set_state(AdminStates.asking_pdf)
    await message.answer("📄 *Step 7/7: Upload Product*\nPlease send the PDF file for this program:")

@router.message(AdminStates.asking_pdf, F.document)
async def prod_finalize(message: types.Message, state: FSMContext, db: Database):
    if message.document.mime_type != 'application/pdf':
        return await message.answer("❌ *Invalid Format.* Only PDF files are accepted.")
    
    data = await state.get_data()
    try:
        await db.add_product(
            title=data['title'], lang=data['lang'], gender=data['gender'],
            level=data['level'], freq=data['freq'], price=data['price'],
            file_id=message.document.file_id
        )
        await message.answer(
            f"✅ *Product Active: {data['title']}*\n"
            "The system has been updated and the product is live.",
            reply_markup=akb.admin_main_menu()
        )
        await state.clear()
    except Exception as e:
        await message.answer(f"⚠️ *Database Error:* `{str(e)}`")

# --- [ SECTION 3: BROADCAST ENGINE (SAFE LAUNCH) ] ---

# @router.message(F.text == "📢 Global Broadcast", F.from_user.id.in_(settings.ADMIN_IDS))
# async def start_broadcast(message: types.Message, state: FSMContext):
#     await state.set_state(AdminStates.awaiting_broadcast)
#     await message.answer(
#         "📢 *DRAFTING MODE*\n"
#         "Send your message exactly as you want it to appear.\n\n"
#         "💡 *Tip: You can use *bold*, __italic__, and even attach images/videos. "
#         "The bot will preserve all formatting.*",
#         reply_markup=akb.cancel_admin()
#     )

# @router.message(AdminStates.awaiting_broadcast)
# async def preview_broadcast(message: types.Message, state: FSMContext):
#     if message.text == "❌ Abort Operation":
#         await state.clear()
#         return await message.answer("Broadcast cancelled.", reply_markup=akb.admin_main_menu())

#     # We store the message ID and Chat ID to copy it later
#     await state.update_data(msg_to_copy=message.message_id, chat_from=message.chat.id)
    
#     # Show the Admin a Preview
#     await message.answer("👀 *BROADCAST PREVIEW:*")
    
#     # Copy the message back to the admin so they see the final result
#     await message.copy_to(message.chat.id)
    
    
#     confirm_kb = InlineKeyboardBuilder()
#     confirm_kb.button(text="🚀 YES, LAUNCH NOW", callback_data="confirm_launch")
#     confirm_kb.button(text="✍️ Edit Draft", callback_data="broadcast_push") # Goes back
#     confirm_kb.adjust(1)

#     await message.answer(
#         "⚠️ *FINAL CONFIRMATION*\n"
#         "Are you sure you want to send this to ALL registered users?",
#         reply_markup=confirm_kb.as_markup()
#     )
#     await state.set_state(AdminStates.confirm_broadcast)

# @router.callback_query(AdminStates.confirm_broadcast, F.data == "confirm_launch")
# async def execute_broadcast(callback: types.CallbackQuery, db: Database, bot: Bot, state: FSMContext):
#     data = await state.get_data()
#     msg_id = data['msg_to_copy']
#     from_chat = data['chat_from']

#     users = await db._pool.fetch("SELECT telegram_id FROM users")
#     await callback.message.edit_text(f"🚀 *Launch Initiated...*\nTarget: `{len(users)}` athletes.")
    
#     success, fail = 0, 0
#     for user in users:
#         try:
#             # copy_to automatically handles bold/italic/media
#             await bot.copy_message(
#                 chat_id=user['telegram_id'],
#                 from_chat_id=from_chat,
#                 message_id=msg_id
#             )
#             success += 1
#             await asyncio.sleep(0.05) # Crucial: Rate limiting
#         except (TelegramForbiddenError, Exception):
#             fail += 1
#         except TelegramRetryAfter as e:
#             await asyncio.sleep(e.retry_after)
#             await bot.copy_message(chat_id=user['telegram_id'], from_chat_id=from_chat, message_id=msg_id)
#             success += 1

#     await bot.send_message(
#         from_chat,
#         f"🏁 *MISSION COMPLETE*\n\n✅ Reached: `{success}`\n❌ Blocked: `{fail}`",
#         reply_markup=akb.admin_main_menu()
#     )
#     await state.clear()

# --- [ SECTION 4: FINANCIAL AUDIT QUEUE ] ---

PAY_PER_PAGE = 6

from .verify import get_verifier_menu # Import the menu builder we made

@router.message(F.text == "🤖 AI Verifier", F.from_user.id.in_(settings.ADMIN_IDS))
async def open_verifier_tools(message: types.Message):
    """
    Opens the testing suite with 'Upload Screenshot' and 'Test Batch'
    """
    await message.answer(
        "🛠 **TRANSACTION ARCHITECT: TEST SUITE**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Use these tools to stress-test OCR and Bank API logic "
        "without affecting real user records.",
        reply_markup=get_verifier_menu()
    )
    
    
@router.message(F.text == "⏳ Pending Payments", F.from_user.id.in_(settings.ADMIN_IDS))
@router.callback_query(F.data.startswith("paypage_"), F.from_user.id.in_(settings.ADMIN_IDS))
async def view_payment_ledger(event: types.Message | types.CallbackQuery, db: Database):
    """
    Handles both the Reply Button (Message) and the Inline Pagination (Callback).
    """
    page = 0
    if isinstance(event, types.CallbackQuery):
        page = int(event.data.split("_")[1])
    
    offset = page * PAY_PER_PAGE
    pending_count = await db.count_pending_payments()
    payments = await db.get_pending_payments(limit=PAY_PER_PAGE, offset=offset)
    total_pages = (pending_count + PAY_PER_PAGE - 1) // PAY_PER_PAGE

    header = (
        "💳 *FINANCIAL AUDIT QUEUE*\n"
        "————————————————————\n"
        f"Total Pending: `{pending_count}`\n"
        "Select a record to audit receipt:"
    )

    markup = akb.payment_ledger_markup(payments, page, total_pages)

    if isinstance(event, types.Message):
        if pending_count == 0:
            return await event.answer("✅ *Treasury Clear.* No pending receipts.")
        await event.answer(header, reply_markup=markup)
    else:
        await event.message.edit_text(header, reply_markup=markup)
@router.callback_query(F.data.startswith("view_pay_"), F.from_user.id.in_(settings.ADMIN_IDS))
async def inspect_single_payment(callback: types.CallbackQuery, db: Database, bot: Bot):
    payment_id = int(callback.data.split("_")[-1])
    
    # 1. Look at your SELECT statement. 
    # If your column in the DB is actually 'proof_file_id', use that.
    pay = await db._pool.fetchrow("""
        SELECT p.*, u.username, u.full_name, u.language, pr.title 
        FROM payments p
        JOIN users u ON p.user_id = u.telegram_id
        JOIN products pr ON p.product_id = pr.id
        WHERE p.id = $1
    """, payment_id)

    if not pay:
        return await callback.answer("Transaction not found.")

    # 2. DEBUG PRINT (Optional: Run this once to see what keys actually exist)
    # print(f"DEBUG: Database keys available: {pay.keys()}")

    lang_display = "🇺🇸 English" if pay['language'] == "EN" else "🇪🇹 አማርኛ (Amharic)"

    ledger_detail = (
    f"📑 <b>TRANSACTION AUDIT: #{pay['id']}</b>\n"
    f"———————————————\n"
    f"👤 <b>Athlete:</b> {pay['full_name']} (@{pay['username']})\n"
    f"🌍 <b>Language:</b> {lang_display}\n"
    f"📦 <b>Plan:</b> {pay['title']}\n"
    f"💰 <b>Amount:</b> {pay['amount']} ETB\n"
    f"📅 <b>Date:</b> {pay['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
    f"———————————————"
)

    await callback.message.delete()

    # 3. FIX THE KEY HERE: 
    # Change pay['proof_id'] to pay['proof_file_id'] (or whatever your DB column is)
    await bot.send_photo(
    chat_id=callback.from_user.id,
    photo=pay['proof_file_id'],
    caption=ledger_detail,
    reply_markup=akb.admin_approval_markup(payment_id),
    parse_mode="HTML"
)
    
import html # Ensure this is imported

@router.callback_query(F.data.startswith("approve_"), F.from_user.id.in_(settings.ADMIN_IDS))
async def approve_payment(callback: types.CallbackQuery, db: Database, bot: Bot):
    payment_id = int(callback.data.split("_")[1])
    info = await db.approve_payment(payment_id)
    
    if not info:
        return await callback.answer("Error: Payment not found.")

    # Get the admin's name who clicked the button
    admin_name = html.escape(callback.from_user.full_name)

    # 1. Message for the User (Athlete)
    msg = (
        "🔥 <b>ACCESS GRANTED</b>\n\nYour payment is verified. Your personalized Product is attached below. Let's work."
        if info['language'] == "EN" else
        "🔥 <b>ፈቃድ ተሰጥቷል</b>\n\nክፍያዎ ተረጋግጧል። የእርስዎ ልዩ የልምምድ እቅድ ከታች ተያይዟል። ስራ እንጀምር።"
    )

    # 2. Try sending document to the user
    try:
        await bot.send_document(
            chat_id=info['user_id'], 
            document=info['telegram_file_id'], 
            caption=msg,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Delivery failed: {e}")
        return await callback.answer("❌ Could not send. User might have blocked the bot.")

    # 3. Update the Admin Group message
    try:
        # Keep the old caption but add the approval info
        # We escape the old caption to ensure it doesn't break HTML parsing
        old_caption = callback.message.caption or ""
        
        new_caption = (
            f"{old_caption}\n\n"
            f"✅ <b>APPROVED & DELIVERED</b>\n"
            f"👤 <b>By Admin:</b> {admin_name}"
        )

        await callback.message.edit_caption(
            caption=new_caption,
            reply_markup=None, # Removes the buttons so they can't be clicked twice
            parse_mode="HTML"
        )
        await callback.answer("Success: User notified & file sent.")
        
    except Exception as e:
        logging.error(f"Admin UI update error: {e}")
        # If the caption edit fails, at least give the admin a popup confirmation
        await callback.answer(f"✅ Approved by {callback.from_user.first_name}")
        

@router.callback_query(F.data == "admin_home", F.from_user.id.in_(settings.ADMIN_IDS))
async def callback_admin_home(callback: types.CallbackQuery, state: FSMContext, db: Database):
    """Fallback for inline buttons trying to return home."""
    await state.clear()
    await callback.message.delete()
    # Trigger the main message again
    await admin_dashboard(callback.message, db, state)


# 2. Add the Reject Trigger
@router.callback_query(F.data.startswith("reject_"), F.from_user.id.in_(settings.ADMIN_IDS))
async def start_rejection(callback: types.CallbackQuery, state: FSMContext):
    payment_id = int(callback.data.split("_")[1])
    await state.update_data(reject_pay_id=payment_id)
    await state.set_state(AdminStates.awaiting_rejection_reason)
    
    await callback.message.answer(
        "🚫 *REJECTION Product*\n"
        "Please enter the reason for rejection (this will be sent to the user):",
        reply_markup=akb.cancel_admin()
    )
    await callback.answer()

# 3. Process the Rejection Reason
# 3. Process the Rejection Reason
@router.message(AdminStates.awaiting_rejection_reason, F.text)
async def execute_rejection(message: types.Message, state: FSMContext, db: Database, bot: Bot):
    if message.text == "❌ Abort Operation":
        await state.clear()
        return await message.answer("Rejection cancelled.", reply_markup=akb.admin_main_menu())

    data = await state.get_data()
    payment_id = data['reject_pay_id']
    admin_reason = message.text

    # 1. Fetch User and Payment info
    info = await db._pool.fetchrow("""
        SELECT p.user_id, u.language, p.amount FROM payments p 
        JOIN users u ON p.user_id = u.telegram_id 
        WHERE p.id = $1
    """, payment_id)

    if not info:
        return await message.answer("❌ Error: Payment record not found.")

    # 2. Update DB: Set status to 'rejected'
    await db._pool.execute("UPDATE payments SET status = 'rejected' WHERE id = $1", payment_id)

    # 3. Localized Reason Logic
    # If the admin writes a custom reason, we keep it, but we wrap it in a localized template
    lang = info['language']
    
    if lang == "EN":
        deny_msg = (
            f"❌ *PAYMENT DECLINED*\n"
            f"————————————————————\n"
            f"I could not verify your transfer of `{info['amount']} ETB`.\n\n"
            f"🚩 *REASON:* {admin_reason}\n"
            f"————————————————————\n"
            f"💡 *Next Step:* Please go to 'Unlock Plan' and upload a clear, valid screenshot of your bank or Telebirr receipt."
        )
    else:
        deny_msg = (
            f"❌ *ክፍያው አልተቀበለም*\n"
            f"————————————————————\n"
            f"የላኩትን የ`{info['amount']} ብር` ክፍያ ማረጋገጥ አልቻልኩም።\n\n"
            f"🚩 *ምክንያት፦* {admin_reason}\n"
            f"————————————————————\n"
            f"💡 *መፍትሄ፦* እባክዎ 'እቅዴን ክፈት' ውስጥ በመግባት ትክክለኛውን የባንክ ወይም የቴሌብር ደረሰኝ በፎቶ መልኩ በግልጽ ይላኩ።"
        )

    # 4. Notify User
    try:
        await bot.send_message(chat_id=info['user_id'], text=deny_msg, parse_mode="Markdown")
        await message.answer(
            f"✅ *USER NOTIFIED ({lang})*\nReason: `{admin_reason}`", 
            reply_markup=akb.admin_main_menu()
        )
    except Exception:
        await message.answer("⚠️ Status updated in DB, but user has blocked the bot.")
    
    await state.clear()
    


# STEP 1: Show the Preview
@router.message(AdminStates.awaiting_rejection_reason, F.text)
async def preview_rejection(message: types.Message, state: FSMContext, db: Database):
    if message.text == "❌ Abort Operation":
        await state.clear()
        return await message.answer("Rejection cancelled.", reply_markup=akb.admin_main_menu())

    admin_reason = message.text
    data = await state.get_data()
    payment_id = data['reject_pay_id']

    # Fetch user info to prepare the specific language preview
    info = await db._pool.fetchrow("""
        SELECT u.language, p.amount FROM payments p 
        JOIN users u ON p.user_id = u.telegram_id 
        WHERE p.id = $1
    """, payment_id)

    # Generate the draft message
    lang = info['language']
    draft = (
        f"❌ *PAYMENT DECLINED*\n"
        f"🚩 *REASON:* {admin_reason}\n"
    ) if lang == "EN" else (
        f"❌ *ክፍያው አልተቀበለም*\n"
        f"🚩 *ምክንያት፦* {admin_reason}\n"
    )

    await state.update_data(final_reason=admin_reason, draft_text=draft)
    await state.set_state(AdminStates.confirm_rejection)

    await message.answer(
        f"🔍 *PREVIEW FOR USER ({lang}):*\n\n{draft}\n\n"
        f"**Are you sure you want to send this rejection?**",
        reply_markup=akb.rejection_confirm_kb(),
        parse_mode="Markdown"
    )

# STEP 2: Final Execution
@router.message(AdminStates.confirm_rejection)
async def final_execute_rejection(message: types.Message, state: FSMContext, db: Database, bot: Bot):
    if message.text == "🔄 Edit Reason":
        await state.set_state(AdminStates.awaiting_rejection_reason)
        return await message.answer("Please type the new reason:", reply_markup=types.ReplyKeyboardRemove())
    
    if message.text == "❌ Abort Operation":
        await state.clear()
        return await message.answer("Rejection cancelled.", reply_markup=akb.admin_main_menu())

    if message.text == "✅ Confirm & Send":
        data = await state.get_data()
        payment_id = data['reject_pay_id']
        admin_reason = data['final_reason']

        # 1. Fetch data again for notification
        info = await db._pool.fetchrow("""
            SELECT p.user_id, u.language, p.amount FROM payments p 
            JOIN users u ON p.user_id = u.telegram_id 
            WHERE p.id = $1
        """, payment_id)

        # 2. Update Database
        await db._pool.execute("UPDATE payments SET status = 'rejected' WHERE id = $1", payment_id)

        # 3. Construct Final Message
        lang = info['language']
        if lang == "EN":
            deny_msg = (
                f"❌ *PAYMENT DECLINED*\n"
                f"————————————————————\n"
                f"I could not verify your transfer of `{info['amount']} ETB`.\n\n"
                f"🚩 *REASON:* {admin_reason}\n"
                f"————————————————————\n"
                f"💡 *Next Step:* Please go to 'Unlock Plan' and upload a clear receipt."
            )
        else:
            deny_msg = (
                f"❌ *ክፍያው አልተቀበለም*\n"
                f"————————————————————\n"
                f"የላኩትን የ`{info['amount']} ብር` ክፍያ ማረጋገጥ አልቻልኩም።\n\n"
                f"🚩 *ምክንያት፦* {admin_reason}\n"
                f"————————————————————\n"
                f"💡 *መፍትሄ፦* እባክዎ በትክክለኛ ደረሰኝ ድጋሚ ይሞክሩ።"
            )

        # 4. Notify User & Clear State
        try:
            await bot.send_message(chat_id=info['user_id'], text=deny_msg, parse_mode="Markdown")
            await message.answer(f"✅ User notified. Status: Rejected.", reply_markup=akb.admin_main_menu())
        except Exception:
            await message.answer("⚠️ User blocked the bot, but DB updated.")
        
        await state.clear()

PROD_PER_PAGE = 8

@router.message(F.text == "🛠 Manage Products", F.from_user.id.in_(settings.ADMIN_IDS))
@router.callback_query(F.data == "manage_refresh")
@router.callback_query(F.data.startswith("prodpage_"))
async def list_products_manage(event: types.Message | types.CallbackQuery, db: Database):
    page = 0
    if isinstance(event, types.CallbackQuery) and event.data.startswith("prodpage_"):
        page = int(event.data.split("_")[1])
    
    offset = page * PROD_PER_PAGE
    # You'll need a count_products method in DB similar to count_payments
    count = await db._pool.fetchval("SELECT count(*) FROM products")
    products = await db.get_all_products(limit=PROD_PER_PAGE, offset=offset)
    total_pages = (count + PROD_PER_PAGE - 1) // PROD_PER_PAGE

    text = "🛠 *Product MANAGEMENT*\nClick a product to modify its status or visibility."
    markup = akb.product_manage_list(products, page, total_pages)

    if isinstance(event, types.Message):
        await event.answer(text, reply_markup=markup)
    else:
        await event.message.edit_text(text, reply_markup=markup)

@router.callback_query(F.data.startswith("manage_view_"))
async def view_product_settings(callback: types.CallbackQuery, db: Database):
    prod_id = int(callback.data.split("_")[2])
    p = await db._pool.fetchrow("SELECT * FROM products WHERE id = $1", prod_id)
    
    status_text = "🟢 *ACTIVE* (Visible to Users)" if p['is_active'] else "🔴 *INACTIVE* (Hidden)"
    
    detail = (
        f"📦 *PRODUCT MASTER: {p['title']}*\n"
        f"————————————————————\n"
        f"🌍 *Lang:* {p['language']}\n"
        f"💰 *Price:* `{p['price']} ETB`\n"
        f"🚻 *Target:* {p['gender']} | {p['level']}\n"
        f"📊 *Status:* {status_text}\n"
        f"————————————————————\n"
        "Modify the deployment status below:"
    )
    
    await callback.message.edit_text(detail, reply_markup=akb.product_detail_settings(prod_id, p['is_active']))

@router.callback_query(F.data.startswith("toggle_prod_"))
async def handle_toggle(callback: types.CallbackQuery, db: Database):
    prod_id = int(callback.data.split("_")[2])
    await db.toggle_product_status(prod_id)
    await callback.answer("Status Updated ✅")
    # Refresh the view
    await view_product_settings(callback, db)

@router.callback_query(F.data.startswith("confirm_del_"))
async def delete_warning(callback: types.CallbackQuery):
    prod_id = int(callback.data.split("_")[2])
    # A tiny safety check so you don't delete by accident
    builder = InlineKeyboardBuilder()
    builder.button(text="⚠️ YES, DELETE IT", callback_data=f"force_del_{prod_id}")
    builder.button(text="❌ CANCEL", callback_data=f"manage_view_{prod_id}")
    await callback.message.edit_text("❗ *CRITICAL WARNING*\nDeleting this will remove the Product forever. Proceed?", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("force_del_"))
async def execute_delete(callback: types.CallbackQuery, db: Database):
    prod_id = int(callback.data.split("_")[2])
    await db.delete_product(prod_id)
    await callback.answer("Deleted 🗑️")
    await list_products_manage(callback, db)
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


from datetime import datetime, timezone
import random
from datetime import datetime, timezone
import random
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
from datetime import datetime, timezone
from datetime import datetime

def get_rotating_content(lang: str):
    now = datetime.now()
    # Unique index for every hour to ensure 3-hour rotations never repeat
    time_seed = (now.timetuple().tm_yday * 24) + now.hour
    
    # --- AMHARIC: Focus on Preparation for Fasika ---
    testimonials_am = [
        {"name": "ዮናስ ኤ.", "text": "“ጾሙ ሊያልቅ ጥቂት ቀናት ሲቀሩት ነው የተቀላቀልኩት፤ ገና ከትንሳኤ ማግስት ዝግጁ ሆኜ እንድጀምር ረድቶኛል።”"},
        {"name": "መአዛ ኤፍ.", "text": "“ከጾም በኋላ ሰውነቴ እንዳይዝለፈለፍና ክብደት እንዳይጨምር ትክክለኛውን እቅድ አስቀድሜ በመያዜ ተረጋግቻለሁ።”"},
        {"name": "አቤል ዋለ.", "text": "“ለፋሲካ በዓል ራሴን ያዘጋጀሁበት ምርጥ ስጦታ ነው። አሁን በዓሉን ያለምንም ስጋት ለማክበር ተዘጋጅቻለሁ።”"},
        {"name": "ሄለን አ.", "text": "“ሁልጊዜ ከጾም በኋላ ጂም ለመጀመር እቸገር ነበር፤ ዘንድሮ ግን ገና ሳይፈታ ፕሮግራሜን በመያዜ ትልቅ መነሳሳት ፈጥሮብኛል።”"},
        {"name": "ታሪኩ ቢ.", "text": "“በበዓል ሰሞን የሚወሰደውን ካሎሪ ወደ ጡንቻ ለመቀየር የሚያስችለኝን ስልት አስቀድሜ አግኝቻለሁ።”"},
        {"name": "ሊዲያ አስ.", "text": "“አዲስ ልብስ ብቻ ሳይሆን አዲስ ቁመና ለራሴ ሰጥቻለሁ። ጾሙ ሲያልቅ በውጤት ለመጀመር ዝግጁ ነኝ።”"},
        {"name": "አብርሃም ደ.", "text": "“በጾም ወቅት ያጣሁትን ጡንቻ ለመመለስ ፕሮፌሽናል እቅድ ያስፈልገኝ ነበር፤ ይህ ፕሮግራም ትክክለኛው ምርጫ ነው።”"},
        {"name": "ሩት ቴ.", "text": "“ፋሲካን በደስታ አክብሬ ሰኞን በከፍተኛ ጉልበት የምጀምርበትን መንገድ ስላገኘሁ በጣም ደስተኛ ነኝ።”"},
        {"name": "ቶማስ በየ.", "text": "“የትንሳኤ ስጦታዬን አስቀድሜ ገዝቻለሁ። ዋጋው ከጥቅሙ አንጻር በጣም አነስተኛ ነው።”"},
        {"name": "ተስፋዬ ኤል.", "text": "“ጂም ከመሄዴ በፊት እቤት ውስጥ ሆኜ ራሴን የማዘጋጅበት ግልጽ መመሪያ አግኝቻለሁ።”"},
        {"name": "ቤተልሔም በ.", "text": "“ለጤናዬ የወሰንኩት ቁርጥ ውሳኔ ነው። ከበዓል በኋላ አዲስ ሰው ሆኜ እመለሳለሁ።”"},
        {"name": "ኤደን ሽመ.", "text": "“ይሄ ስልጠና ብቻ ሳይሆን የአኗኗር ዘይቤዬን የሚቀይር ድንቅ የትንሳኤ ስጦታ ነው።”"}
    ]
    
    recent_buyers_am = [
            "ብሩክ አ.", "ሄለን ገ.", "ዮናስ መ.", "ሰላማዊት ት.", "ኤልያስ ወ.", 
            "ረድኤት ሰ.", "ዳዊት ከ.", "ማርታ በ.", "ሄኖክ ደ.", "ቃልኪዳን ፍ.", 
            "አማኑኤል ለ.", "ትዕግስት ዘ."
        ]

    # --- ENGLISH: Focus on "Hit the ground running" ---
    testimonials_en = [
        {"name": "Elias M.", "text": "“I secured my plan during Holy Week. Having the strategy ready before the feast made the transition so much easier.”"},
        {"name": "Sara A.", "text": "“The best decision I made was joining now. I don't have to worry about the post-holiday weight gain.”"},
        {"name": "Dawit T.", "text": "“Joining before Easter gave me the mindset shift I needed. Ready to hit the ground running on Monday!”"},
        {"name": "Marta G.", "text": "“I didn't want to waste a single day after Fasika. Getting my meal plan ready now was a total game changer.”"},
        {"name": "Brook W.", "text": "“Reclaiming the muscle I lost during Lent is my priority. This program is the perfect roadmap.”"},
        {"name": "Tigist S.", "text": "“Invested in myself before the holiday started. Peace of mind is the best Easter gift!”"},
        {"name": "Nathan B.", "text": "“Professional, structured, and perfect for the post-fast recovery phase.”"},
        {"name": "Selam D.", "text": "“I feel more confident knowing I have a solid plan for the week after Easter.”"},
        {"name": "Henok L.", "text": "“Top tier coaching. I'm starting my transformation the second the fast ends.”"},
        {"name": "Rediet K.", "text": "“Don't wait for Monday to plan. Plan now so you can execute on Monday.”"},
        {"name": "Amanuel Z.", "text": "“The price is unbeatable for the value provided. Best Holy Week deal in Ethiopia.”"},
        {"name": "Hana P.", "text": "“Transformed my mindset before the holiday. Ready for a healthy and strong Easter!”"}
    ]
    
    recent_buyers_en = [
            "Brook A.", "Helen G.", "Yonas M.", "Selamawit T.", "Elias W.", 
            "Rediet S.", "Dawit K.", "Marta B.", "Henok D.", "Kalkidan F.", 
            "Amanuel L.", "Tigist Z."
        ]
    # Selection logic with offsets to prevent matching names
    idx = time_seed % 12
    buyer_idx = (time_seed + 5) % 12

    if lang.upper() == "AM":
        testi = testimonials_am[idx]
        buyer_name = recent_buyers_am[buyer_idx]
        activity = f"🔥 በቅርብ ጊዜ የተመዘገቡ፦ <b>{buyer_name}... ✅</b>"
    else:
        testi = testimonials_en[idx]
        buyer_name = recent_buyers_en[buyer_idx]
        activity = f"🔥 Recently joined: <b>{buyer_name}... ✅</b>"

    return testi, activity

def build_deal_message(lang: str, expires_at: datetime, product_id: int):
    # Moderate urgency for a 1-day window
    spots_left = random.choice([8, 9, 11]) 
    price = 399 
    original_price = 1000
    
    testimonial, recent_activity = get_rotating_content(lang)

    if lang.upper() == "AM":
        header = f"<b>🏆 የብዙዎች ምርጫ የሆነው የ399 ብር እቅድ በድጋሚ ለጥቂት ሰአታት!</b>"
        body = (
            f"<b>ለውጥ የሚጀምረው በውሳኔ ነው!</b>\n\n"
            f"ጤናማና ጠንካራ አካል ለመገንባት የሚያስፈልገው ፍላጎት ብቻ ሳይሆን ትክክለኛ እቅድ ነው። የእርስዎን የ8-ሳምንት የለውጥ ፕሮግራም ዛሬ በ<b>{price} ብር</b> ብቻ ማግኘት ይችላሉ።\n\n"
            f"<b>ምን እውቀት ያገኛሉ?</b>\n"
            f"📘 <b>ሳይንሳዊ አመጋገብ፦</b> ሰውነትዎ የሚፈልገውን ምግብ መለየት።\n"
            f"🏃‍♂️ <b>ተግባራዊ ስልጠና፦</b> ውጤት የሚያመጡ ትክክለኛ እንቅስቃሴዎች።\n"
            f"📈 <b>ክትትል፦</b> እድገትዎን በየቀኑ የሚለኩበት ስልት።\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"💡 <b>ጠቃሚ ምክር፦</b>\n"
            f"🎤 <b>ለእናንተ ያዘጋጀሁትን አጭር መልዕክት ከላይ ያዳምጡ!</b>\n\n"
            f"ቅናሹ ለ1ቀን ብቻ የሚቆይ ይሆናል።\n"
            f"🔥 {recent_activity}\n"
            f"⚠️ የቀሩት ቦታዎች፦ <b>{spots_left}</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>በቅናሽ ዋጋ ለመመዝገብ ከታች ያለውን ቁልፍ ይጫኑ፦</b>"
        )
        button_text = f"✅ አሁኑኑ ጀምር"
    else:
        header = f"<b>🎁 The community's choice: 399 ETB access again for a few hours!</b>"
        body = (
            f"<b>Success is built on a solid system.</b>\n\n"
            f"Don't leave your fitness to chance. Join thousands of others who have secured their professional 8-week program for only <b>{price} ETB</b>. Tomorrow, the rate returns to {original_price} ETB.\n\n"
            f"<b>What You Will Learn:</b>\n"
            f"📘 <b>Nutrition Science:</b> Master what your body needs.\n"
            f"🏃‍♂️ <b>Efficient Training:</b> Moves that actually drive results.\n"
            f"📈 <b>Sustainability:</b> How to keep your results for life.\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"💡 <b>Expert Tip:</b>\n"
            f"🎤 <b>Listen to Coach Hilawe’s quick audio note above!</b>\n\n"
            f"Invest in your health today before the discount expires.\n"
            f"🔥 {recent_activity}\n"
            f"⚠️ Status: <b>{spots_left} slots available</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>Secure your 399 ETB access here:</b>"
        )
        button_text = "✅ GET STARTED"

    text = f"{header}\n\n{body}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=button_text, callback_data=f"pay_{product_id}")]
    ])
    
    return text, kb

import os
from datetime import datetime, timedelta

from aiogram import types, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
# RIGHT for aiogram v3.x
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError

from config import settings
from app_context import db  # or import your Database instance the same way other handlers do
from aiogram.fsm.context import FSMContext
from aiogram import Router

# Configurable defaults (env or fallback)

# --- Helper: target selection keyboard ---
def broadcast_target_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🧪 Test (Admins only)", callback_data="broadcast_target:test")
    kb.button(text="🎯 Unpaid only", callback_data="broadcast_target:unpaid")
    kb.button(text="✅ Paid only", callback_data="broadcast_target:paid")
    kb.button(text="📣 All users", callback_data="broadcast_target:all")
    kb.adjust(2)
    return kb.as_markup()

# --- Step 1: Admin starts drafting a broadcast ---

@router.message(F.text == "📢 Global Broadcast", F.from_user.id.in_(settings.ADMIN_IDS))
async def start_broadcast(message: types.Message, state: FSMContext):
    await message.answer(
        "Choose target group for this broadcast:",
        reply_markup=broadcast_target_kb()
    )
    await state.set_state(AdminStates.confirm_broadcast)
# @router.message(F.text == "📢 Global Broadcast", F.from_user.id.in_(settings.ADMIN_IDS))
# async def start_broadcast(message: types.Message, state: FSMContext):
#     await state.set_state(AdminStates.awaiting_broadcast)
#     await message.answer(
#         "📢 *DRAFTING MODE*\n"
#         "Send your message exactly as you want it to appear.\n\n"
#         "💡 *Tip: You can use *bold*, __italic__, and even attach images/videos. "
#         "The bot will preserve all formatting.*",
#         reply_markup=akb.cancel_admin()
#     )

# # --- Step 2: Admin sends draft; show preview and confirm ---
# @router.message(AdminStates.awaiting_broadcast)
# async def preview_broadcast(message: types.Message, state: FSMContext):
#     if message.text == "❌ Abort Operation":
#         await state.clear()
#         return await message.answer("Broadcast cancelled.", reply_markup=akb.admin_main_menu())

#     await state.update_data(msg_to_copy=message.message_id, chat_from=message.chat.id)

#     await message.answer("👀 *BROADCAST PREVIEW:*")
#     await message.copy_to(message.chat.id)

#     # Now show target selection instead of cancel
#     await message.answer(
#         "Choose target group for this broadcast:",
#         reply_markup=broadcast_target_kb()
#     )
#     await state.set_state(AdminStates.confirm_broadcast)

# --- Cancel handler ---
@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Broadcast cancelled.", reply_markup=akb.admin_main_menu())

# --- Admin selected a target; show final confirmation with estimated count ---
@router.callback_query(AdminStates.confirm_broadcast, F.data.startswith("broadcast_target:"))
async def confirm_broadcast_target(callback: types.CallbackQuery, state: FSMContext):
    target = callback.data.split(":", 1)[1]  # test | unpaid | paid | all

    # Estimate target count
    try:
        if target == "test":
            targets = [{'telegram_id': aid, 'language': 'EN'} for aid in settings.ADMIN_IDS]
            filter_sql = None

        # Inside execute_broadcast_run, update the "unpaid" block:

        elif target == "unpaid":
            # We JOIN with products to get the ID that matches the user's onboarding stats
            rows = await db._pool.fetch("""
                SELECT u.telegram_id, u.language, p_match.id as matched_product_id
                FROM users u
                LEFT JOIN products p_match ON 
                    u.language = p_match.language AND 
                    u.gender = p_match.gender AND 
                    u.level = p_match.level AND 
                    u.frequency = p_match.frequency
                WHERE NOT EXISTS (
                    SELECT 1 FROM payments p 
                    WHERE p.user_id = u.telegram_id AND p.status = 'approved'
                ) AND p_match.is_active = TRUE
            """)
            targets = [dict(r) for r in rows]
            filter_sql = "NOT EXISTS (SELECT 1 FROM payments p WHERE p.user_id = users.telegram_id AND p.status = 'approved')"

        elif target == "paid":
            # Users WITH at least one approved payment
            rows = await db._pool.fetch("""
                SELECT u.telegram_id, u.language
                FROM users u
                WHERE EXISTS (
                    SELECT 1 FROM payments p
                    WHERE p.user_id = u.telegram_id
                    AND p.status = 'approved'
                )
            """)
            targets = [dict(r) for r in rows]
            filter_sql = "EXISTS (SELECT 1 FROM payments p WHERE p.user_id = users.telegram_id AND p.status = 'approved')"

        else:  # all users
            rows = await db._pool.fetch("SELECT telegram_id, language FROM users")
            targets = [dict(r) for r in rows]
            filter_sql = "TRUE"

    except Exception:
        total = 0
    total = len(targets) # Add this line
    confirm_kb = InlineKeyboardBuilder()
    confirm_kb.button(text="🚀 Launch Now", callback_data=f"confirm_launch:{target}")
    confirm_kb.button(text="❌ Cancel", callback_data="cancel_broadcast")
    confirm_kb.adjust(2)

    await callback.message.answer(
        f"⚠️ *FINAL CONFIRMATION*\nTarget: `{total}` users.\nMode: `{target}`\nDo you want to proceed?",
        reply_markup=confirm_kb.as_markup()
    )

# --- Core executor: updates DB (deal_expires_at/deal_price) and broadcasts by copying admin draft ---


# Core executor (no draft required)
async def execute_broadcast_run(bot: Bot, db, admin_id: int, target: str, test_mode: bool = False):
    """
    Send localized template messages to the selected target group.
    - bot: aiogram Bot instance
    - db: your Database object with _pool (asyncpg)
    - admin_id: admin who launched the broadcast (for summary)
    - target: 'test' | 'unpaid' | 'paid' | 'all'
    - test_mode: if True, only send to settings.ADMIN_IDS and DO NOT update DB deals
    """
    BATCH_SLEEP = float(getattr(settings, "BROADCAST_BATCH_SLEEP", 0.06))
    DEAL_PRICE = float(getattr(settings, "BROADCAST_DEAL_PRICE", 399))
    DEAL_DURATION_HOURS = int(getattr(settings, "BROADCAST_DURATION_HOURS", 90))
    from datetime import datetime, timezone

    
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=DEAL_DURATION_HOURS)
    
    targets = []
    filter_sql = ""
    

        # Build target list and SQL filter
    if target == "test":
            # 1. Grab a sample product ID to use for the test
            sample_product = await db._pool.fetchval("SELECT id FROM products WHERE is_active = TRUE LIMIT 1")
            
            if not sample_product:
                logging.error("Broadcast Test Failed: No active products found in DB.")
                return {"error": "No products available"}

            # 2. Get admins and just force the sample product ID
            rows = await db._pool.fetch("""
                SELECT telegram_id, language, $2::INT as matched_product_id
                FROM users
                WHERE telegram_id = ANY($1::BIGINT[])
            """, settings.ADMIN_IDS, sample_product)
            
            targets = [dict(r) for r in rows]
            filter_sql = f"telegram_id = ANY(ARRAY{settings.ADMIN_IDS}::BIGINT[])"

    # Inside execute_broadcast_run, update the "unpaid" block:

    elif target == "unpaid":
        # We JOIN with products to get the ID that matches the user's onboarding stats
        rows = await db._pool.fetch("""
            SELECT u.telegram_id, u.language, p_match.id as matched_product_id
            FROM users u
            LEFT JOIN products p_match ON 
                u.language = p_match.language AND 
                u.gender = p_match.gender AND 
                u.level = p_match.level AND 
                u.frequency = p_match.frequency
            WHERE NOT EXISTS (
                SELECT 1 FROM payments p 
                WHERE p.user_id = u.telegram_id AND p.status = 'approved'
            ) AND p_match.is_active = TRUE
        """)
        targets = [dict(r) for r in rows]
        filter_sql = "NOT EXISTS (SELECT 1 FROM payments p WHERE p.user_id = users.telegram_id AND p.status = 'approved')"

    elif target == "paid":
        # Users WITH at least one approved payment
        rows = await db._pool.fetch("""
            SELECT u.telegram_id, u.language
            FROM users u
            WHERE EXISTS (
                SELECT 1 FROM payments p
                WHERE p.user_id = u.telegram_id
                AND p.status = 'approved'
            )
        """)
        targets = [dict(r) for r in rows]
        filter_sql = "EXISTS (SELECT 1 FROM payments p WHERE p.user_id = users.telegram_id AND p.status = 'approved')"

    else:  # all users
        rows = await db._pool.fetch("SELECT telegram_id, language FROM users")
        targets = [dict(r) for r in rows]
        filter_sql = "TRUE"


    total = len(targets)
    from datetime import datetime, timezone

    expires_at = datetime.now(timezone.utc) + timedelta(hours=DEAL_DURATION_HOURS)

    # Persist broadcast run (best-effort)
    broadcast_id = None
    try:
        row = await db._pool.fetchrow(
            "INSERT INTO broadcasts (name, target_filter, language, expires_at, total_target, admin_id) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
            f"1-day deal {datetime.utcnow().isoformat()}",
            target,
            None,
            expires_at,
            total,
            admin_id
        )
        if row:
            broadcast_id = row['id']
    except Exception as e:
        logging.warning("Failed to create broadcasts row: %s", e)

    # Update users with deal info (skip in test mode)
    print('here is filters_sql', filter_sql)
    if filter_sql:
        try:
            await db._pool.execute(
                "UPDATE users SET deal_expires_at = $1, deal_price = $2 WHERE " + filter_sql,
                expires_at,
                DEAL_PRICE
            )
        except Exception as e:
            logging.warning("Failed to update users with deal info: %s", e)

    sent = 0
    failed = 0
    print('here are targets', targets)
    deleted_count = 0  # Track removed users

    for user in targets:
        uid = user.get('telegram_id')
        lang = user.get('language') or 'EN'
        
        # Try to get the ID from the database row first
        p_id = user.get('matched_product_id')
        
        # If it's missing (backfill didn't catch it or new user), find it manually
        if not p_id:
            # We fetch user details to perform a match
            u_detail = await db._pool.fetchrow(
                "SELECT language, level, frequency, gender FROM users WHERE telegram_id = $1", 
                uid
            )
            if u_detail:
                # Find matching product
                matched = await db._pool.fetchrow("""
                    SELECT id FROM products 
                    WHERE language = $1 AND gender = $2 AND level = $3 AND frequency = $4
                    AND is_active = TRUE LIMIT 1
                """, u_detail['language'], u_detail['gender'], u_detail['level'], u_detail['frequency'])
                
                if matched:
                    p_id = matched['id']
                else:
                    logging.warning(f"No matching product for user {uid} stats.")
                    continue
            else:
                continue

        try:
                text, kb = build_deal_message(lang, expires_at, p_id)
                
                # USE YOUR IMAGE FILE ID HERE
                # If you don't have the file_id yet, you can use a URL or local path
                EID_IMAGE = "AgACAgQAAxkBAAJUpmnaGaRTgE7YEUuuv1APRgr6oQSKAALiDGsb_NbRUkqWa0dpKBy-AQADAgADeQADOwQ" 
                VOICE_FILE_ID = "AwACAgQAAxkBAAKMUGnsWpYTz4-F53S7znEbifGIgEqOAAIuHQACPshhUzSMsnnk6RpxOwQ" # main
                # VOICE_FILE_ID = "CQACAgQAAxkBAAIGvWnkeNgyytPGvMAxQOBdbqZ4WAIzAALpGwACzAgoU3N3WvzGKmx3OwQ" #demo

                # sent_msg = await bot.send_photo(
                #     chat_id=uid,
                #     photo=EID_IMAGE,
                #     caption=text,
                #     reply_markup=kb,
                #     parse_mode="HTML"
                # )
                await bot.send_voice(
                    chat_id=uid,
                    voice=VOICE_FILE_ID,
                    caption="🎤 መልዕክት ከኮች ህላዌ (Listen to this first)" # Static caption
                )

                # 2. Send the Deal Message as a separate Text Message
                # This message is EDITABLE by your reminder_worker
                sent_msg = await bot.send_message(
                    chat_id=uid,
                    text=text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                
                # 2. SAVE for future editing (countdown updates)
                await db._pool.execute("""
                    UPDATE users SET 
                        last_broadcast_msg_id = $1, 
                        matched_product_id = $2 
                    WHERE telegram_id = $3
                """, sent_msg.message_id, p_id, uid)
                
                sent += 1
                await asyncio.sleep(BATCH_SLEEP)
            
        except Exception as e:
            failed += 1
            error_str = str(e).lower()
            if "blocked" in error_str or "chat not found" in error_str or "deactivated" in error_str:
                try:
                    # SILENT DELETE: Wipe the user so we don't waste resources next time
                    await db._pool.execute("DELETE FROM users WHERE telegram_id = $1", uid)
                    deleted_count += 1
                    logging.info(f"User {uid} removed from DB (Reason: Bot Blocked/Deactivated)")
                except Exception as db_e:
                    logging.error(f"Failed to delete dead user {uid} from DB: {db_e}")
            else:
                logging.error(f"Transient failure for {uid}: {e}")
            
            
    # Update broadcast stats if we created a row
    if broadcast_id:
        try:
            await db._pool.execute(
                "UPDATE broadcasts SET sent_count = $1, failed_count = $2 WHERE id = $3",
                sent, failed, broadcast_id
            )
        except Exception as e:
            logging.warning("Failed to update broadcast stats: %s", e)

    # Notify admin with summary (best-effort)
    try:
        summary = (
            f"🏁 *BROADCAST COMPLETE*\n\n"
            f"✅ Sent: `{sent}`\n"
            f"❌ Failed: `{failed}`\n"
            f"🗑 Removed from DB: `{deleted_count}`\n\n"
            f"Broadcast id: `{broadcast_id}`"
        )
        await bot.send_message(admin_id, summary, parse_mode="Markdown")
    except Exception:
        pass

    return {"broadcast_id": broadcast_id, "sent": sent, "failed": failed, "deleted": deleted_count}


# Confirm-launch callback (no draft checks)
@router.callback_query(F.data.startswith("confirm_launch:"))
async def on_confirm_launch(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    target = callback.data.split(":", 1)[1]
    admin_id = callback.from_user.id

    await callback.message.edit_text(f"🚀 Launch Initiated... Target mode: `{target}`")
    test_mode = (target == "test")

    asyncio.create_task(execute_broadcast_run(bot, db, admin_id, target, test_mode=test_mode))
    await state.clear()

# --- Optional: quick dry-run command (returns counts without sending) ---
@router.message(F.text == "/broadcast_dryrun", F.from_user.id.in_(settings.ADMIN_IDS))
async def broadcast_dryrun(message: types.Message):
    # returns counts for unpaid/paid/all
    try:
        # Use the SAME logic as your broadcast executor
        unpaid = await db._pool.fetchrow("""
            SELECT COUNT(*) AS cnt FROM users u 
            WHERE NOT EXISTS (SELECT 1 FROM payments p WHERE p.user_id = u.telegram_id AND p.status = 'approved')
        """)
        paid = await db._pool.fetchrow("""
            SELECT COUNT(*) AS cnt FROM users u 
            WHERE EXISTS (SELECT 1 FROM payments p WHERE p.user_id = u.telegram_id AND p.status = 'approved')
        """)
        total = await db._pool.fetchrow("SELECT COUNT(*) AS cnt FROM users")
        await message.answer(
            f"Dry run counts:\n• Unpaid: `{unpaid['cnt']}`\n• Paid: `{paid['cnt']}`\n• Total: `{total['cnt']}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"Failed to fetch counts: {e}")
        
        
@router.message(Command("test_feedback"), F.from_user.id.in_(settings.ADMIN_IDS))
async def cmd_test_feedback(message: types.Message, db, bot: Bot, state: FSMContext):
    args = message.text.split()
    if len(args) < 2: 
        return await message.answer("Usage: /test_feedback 1")
    
    try:
        q_id = int(args[1])
        
        # Pull storage directly from the state object's internal reference
        storage = state.storage 

        from testimonial.testimonial_questions import run_testimonial_cycle
        count = await run_testimonial_cycle(bot, db, storage, q_id, test_mode=True)
        
        await message.answer(f"✅ Test mode active. Sent to {count} admins.")
        
    except Exception as e:
        logging.error(f"Test feedback error: {e}")
        # Send as plain text to avoid the "can't parse entities" HTML error
        await message.answer(f"❌ Error: {str(e)}", parse_mode=None)