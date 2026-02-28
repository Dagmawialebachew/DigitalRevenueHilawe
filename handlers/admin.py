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
from keyboards import inline as akb  # Updated to use your new hybrid keyboard file

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
    stats = await db.get_admin_stats()
    
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

@router.message(F.text == "📢 Global Broadcast", F.from_user.id.in_(settings.ADMIN_IDS))
async def start_broadcast(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.awaiting_broadcast)
    await message.answer(
        "📢 *DRAFTING MODE*\n"
        "Send your message exactly as you want it to appear.\n\n"
        "💡 *Tip: You can use *bold*, __italic__, and even attach images/videos. "
        "The bot will preserve all formatting.*",
        reply_markup=akb.cancel_admin()
    )

@router.message(AdminStates.awaiting_broadcast)
async def preview_broadcast(message: types.Message, state: FSMContext):
    if message.text == "❌ Abort Operation":
        await state.clear()
        return await message.answer("Broadcast cancelled.", reply_markup=akb.admin_main_menu())

    # We store the message ID and Chat ID to copy it later
    await state.update_data(msg_to_copy=message.message_id, chat_from=message.chat.id)
    
    # Show the Admin a Preview
    await message.answer("👀 *BROADCAST PREVIEW:*")
    
    # Copy the message back to the admin so they see the final result
    await message.copy_to(message.chat.id)
    
    
    confirm_kb = InlineKeyboardBuilder()
    confirm_kb.button(text="🚀 YES, LAUNCH NOW", callback_data="confirm_launch")
    confirm_kb.button(text="✍️ Edit Draft", callback_data="broadcast_push") # Goes back
    confirm_kb.adjust(1)

    await message.answer(
        "⚠️ *FINAL CONFIRMATION*\n"
        "Are you sure you want to send this to ALL registered users?",
        reply_markup=confirm_kb.as_markup()
    )
    await state.set_state(AdminStates.confirm_broadcast)

@router.callback_query(AdminStates.confirm_broadcast, F.data == "confirm_launch")
async def execute_broadcast(callback: types.CallbackQuery, db: Database, bot: Bot, state: FSMContext):
    data = await state.get_data()
    msg_id = data['msg_to_copy']
    from_chat = data['chat_from']

    users = await db._pool.fetch("SELECT telegram_id FROM users")
    await callback.message.edit_text(f"🚀 *Launch Initiated...*\nTarget: `{len(users)}` athletes.")
    
    success, fail = 0, 0
    for user in users:
        try:
            # copy_to automatically handles bold/italic/media
            await bot.copy_message(
                chat_id=user['telegram_id'],
                from_chat_id=from_chat,
                message_id=msg_id
            )
            success += 1
            await asyncio.sleep(0.05) # Crucial: Rate limiting
        except (TelegramForbiddenError, Exception):
            fail += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            await bot.copy_message(chat_id=user['telegram_id'], from_chat_id=from_chat, message_id=msg_id)
            success += 1

    await bot.send_message(
        from_chat,
        f"🏁 *MISSION COMPLETE*\n\n✅ Reached: `{success}`\n❌ Blocked: `{fail}`",
        reply_markup=akb.admin_main_menu()
    )
    await state.clear()
# --- [ SECTION 4: FINANCIAL AUDIT QUEUE ] ---

PAY_PER_PAGE = 6

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
        f"📑 *TRANSACTION AUDIT: #{pay['id']}*\n"
        f"————————————————————\n"
        f"👤 *Athlete:* {pay['full_name']} (@{pay['username']})\n"
        f"🌍 *Language:* `{lang_display}`\n"
        f"📦 *Plan:* {pay['title']}\n"
        f"💰 *Amount:* `{pay['amount']} ETB`\n"
        f"📅 *Date:* {pay['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
        f"————————————————————"
    )

    await callback.message.delete()

    # 3. FIX THE KEY HERE: 
    # Change pay['proof_id'] to pay['proof_file_id'] (or whatever your DB column is)
    await bot.send_photo(
        chat_id=callback.from_user.id,
        photo=pay['proof_file_id'], # <--- UPDATED THIS
        caption=ledger_detail,
        reply_markup=akb.admin_approval_markup(payment_id),
        parse_mode="Markdown"
    )
@router.callback_query(F.data.startswith("approve_"), F.from_user.id.in_(settings.ADMIN_IDS))
async def approve_payment(callback: types.CallbackQuery, db: Database, bot: Bot):
    payment_id = int(callback.data.split("_")[1])
    info = await db.approve_payment(payment_id)
    
    if not info:
        return await callback.answer("Error during verification.")

    msg = (
        "🔥 *ACCESS GRANTED*\n\nYour payment is verified. Your personalized Product is attached below. Let's work."
        if info['language'] == "EN" else
        "🔥 *ፈቃድ ተሰጥቷል*\n\nክፍያዎ ተረጋግጧል። የእርስዎ ልዩ የልምምድ እቅድ ከታች ተያይዟል። ስራ እንጀምር።"
    )

    try:
        await bot.send_document(chat_id=info['user_id'], document=info['telegram_file_id'], caption=msg)
        await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n✅ *APPROVED & DELIVERED*", reply_markup=None)
    except Exception:
        await callback.answer("User blocked the bot. Payment approved but document not sent.")

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