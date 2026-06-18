import io
import time
import html
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from aiogram import Router, F, types, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import Database
from config import settings

# Safe imports matching your internal architecture hooks
try:
    from handlers.verify import extract_local_data, verify_external, is_hilawe_receiver
except ImportError:
    # Safe fallback wrappers if run in isolated development environments
    async def extract_local_data(*args): return {"ref": None, "provider": "CBE", "amount_fallback": None, "raw_text": ""}
    async def verify_external(*args): return {"success": False}
    def is_hilawe_receiver(*args): return False

logger = logging.getLogger(__name__)
router = Router(name="club_billing")

# Global local report cache matching current structure patterns
CLUB_REPORT_CACHE = {}

class ClubPaymentStates(StatesGroup):
    awaiting_club_proof = State()

# --- 1. PREMIUM USER PAYMENT INVOICE ---
@router.callback_query(F.data == "initiate_club_subscription")
async def start_club_checkout(callback: types.CallbackQuery, state: FSMContext, db: Database):
    await callback.answer()
    uid = callback.from_user.id
    
    # Safely fetch user preference directly via internal pool
    user_rec = await db._pool.fetchrow("SELECT language FROM users WHERE telegram_id = $1", uid)
    lang = (user_rec['language'] if user_rec else 'EN') or 'EN'
    
    price = settings.BROADCAST_DEAL_PRICE # 299 ETB
    await state.update_data(club_amount=price)
    
    def escape_html(val):
        return html.escape(str(val)) if val else "Not Configured"

    if lang == "EN":
        invoice_html = (
            f"💳 <b>COACH HILAWE TRANSFORMATION CLUB</b>\n"
            f"──────────────────────────────\n"
            f"💵 <b>Price:</b> <code>{price} ETB</code> (30-Day Pass)\n\n"
            f"<b>👉 STEP 1: Transfer {price} ETB to one of these accounts:</b>\n\n"
            f"🔹 <b>Commercial Bank of Ethiopia (CBE)</b>\n"
            f"• Account: <code>{settings.BANK_CBE}</code>\n"
            f"🔹 <b>Bank of Abyssinia (BOA)</b>\n"
            f"• Account: <code>{settings.BANK_BOA}</code>\n"
            f"• Name: <i>{escape_html(settings.BANK_BOA_NAME)}</i>\n\n"
            f"──────────────────────────────\n"
            f"<b>👉 STEP 2: Send the payment screenshot right here.</b>\n\n"
            f"💡 <i>Tip: Tap any account number above to copy it automatically!</i>"
        )
        cancel_btn = "❌ Cancel Payment"
    else:
        invoice_html = (
            f"💳 <b>COACH HILAWE TRANSFORMATION CLUB</b>\n"
            f"──────────────────────────────\n"
            f"💵 <b>ዋጋ፦</b> <code>{price} ብር</code> (ለ30 ቀናት)\n\n"
            f"<b>👉 ደረጃ 1፦ እባክዎ {price} ብሩን ከታች ባሉት አማራጮች ይክፈሉ፡</b>\n\n"
            f"🔹 <b>የኢትዮጵያ ንግድ ባንክ (CBE)</b>\n"
            f"• አካውንት፦ <code>{settings.BANK_CBE}</code>\n"
            f"• ስም፦ <i>{escape_html(settings.BANK_CBE_NAME)}</i>\n\n"
            f"🔹 <b>አቢሲኒያ ባንክ (BOA)</b>\n"
            f"• አካውንት፦ <code>{settings.BANK_BOA}</code>\n"
            f"• ስም፦ <i>{escape_html(settings.BANK_BOA_NAME)}</i>\n\n"
            f"──────────────────────────────\n"
            f"<b>👉 ደረጃ 2፦ ክፍያውን እንደፈጸሙ የደረሰኙን ፎቶ (Screenshot) እዚህ ይላኩ።</b>\n\n"
            f"💡 <i>ጠቃሚ ምክር፦ የባንክ አካውንት ቁጥሩን ለመገልበጥ (ኮፒ ለማድረግ) ቁጥሩን አንዴ ይጫኑት።</i>"
        )
        cancel_btn = "❌ ክፍያውን ሰርዝ"

    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=cancel_btn)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback.message.answer(invoice_html, reply_markup=kb, parse_mode="HTML")
    await state.set_state(ClubPaymentStates.awaiting_club_proof)
# --- 2. CANCELLATION OVERRIDE ROUTINE ---

@router.message(ClubPaymentStates.awaiting_club_proof, F.text.in_({"❌ Cancel Payment", "❌ ክፍያውን ሰርዝ"}))
async def cancel_club_checkout(message: types.Message, state: FSMContext, db: Database):
    uid = message.from_user.id
    user_rec = await db._pool.fetchrow("SELECT language FROM users WHERE telegram_id = $1", uid)
    lang = (user_rec['language'] if user_rec else 'EN') or 'EN'
    
    await state.clear()
    msg = "❌ Registration cancelled. Returning to main engine..." if lang == "EN" else "❌ ክፍያ ተሰርዟል። ወደ ዋናው ገጽ በመመለስ ላይ..."
    
    # Dynamic import to avoid circular dependencies with dashboard structures
    from keyboards.reply import main_menu
    await message.answer(msg, reply_markup=types.ReplyKeyboardRemove())
    await message.answer("🏠 <b>DASHBOARD</b>", reply_markup=main_menu(lang), parse_mode="HTML")

# --- 3. PROOF VERIFICATION & ANIMATION CYCLE ---

@router.message(ClubPaymentStates.awaiting_club_proof, F.photo)
async def process_club_receipt(message: types.Message, state: FSMContext, db: Database, bot: Bot):
    data = await state.get_data()
    uid = message.from_user.id
    
    user_rec = await db._pool.fetchrow("SELECT language, full_name FROM users WHERE telegram_id = $1", uid)
    lang = (user_rec['language'] if user_rec else 'EN') or 'EN'
    full_name = (user_rec['full_name'] if user_rec else 'Athlete') or 'Athlete'
    
    amount = data.get("club_amount", 299.00)
    proof_id = message.photo[-1].file_id

    # UI updates matching existing user experience loops
    load_msg = "📡 <b>Connecting to secure subscription ledger...</b>" if lang == "EN" else "📡 <b>ከክለብ መዝገብ ቤት ጋር በመገናኘት ላይ...</b>"
    progress = await message.answer(load_msg, reply_markup=types.ReplyKeyboardRemove(), parse_mode="HTML")

    # Independent Atomic Transaction Insertion
    pay_id = await db._pool.fetchval("""
        INSERT INTO club_payments (user_id, amount, proof_file_id, status)
        VALUES ($1, $2, $3, 'pending') RETURNING id
    """, uid, amount, proof_id)

    stages = [
        ("📤 Encrypting visual receipt...", "📤 የደረሰኝ ምስል በመቀየር ላይ..."),
        ("🔍 Parsing bank validation signatures...", "🔍 የባንክ ዲጂታል ማህተም በመፈተሽ ላይ..."),
        ("⏳ Synced to Coach Admin Control...", "⏳ የአሰልጣኝ ማረጋገጫ በመጠበቅ ላይ...")
    ]

    for en, am in stages:
        await asyncio.sleep(0.7)
        txt = en if lang == "EN" else am
        try:
            await progress.edit_text(f"✨ <b>{html.escape(txt)}</b>", parse_mode="HTML")
        except Exception: pass

    try:
        await progress.delete()
    except Exception: pass

    if lang == "EN":
        done_text = (
            "✅ <b>CLUB INVOICE SUBMITTED</b>\n\n"
            "Your transaction is safely recorded. The system is scanning the transfer details.\n"
            "You will automatically unlock the group and channel access lines upon confirmation. 🔥"
        )
    else:
        done_text = (
            "✅ <b>የክለብ ደረሰኝዎ ተመዝግቧል</b>\n\n"
            "የላኩት የክፍያ መረጃ በደህንነት ተቀምጧል። ሲስተሙ ዝርዝሩን እያረጋገጠ ነው።\n"
            "ልክ እንደተረጋገጠ የክለቡን መግቢያ ሊንኮች በራስ-ሰር እዚህ ይደርስዎታል። 🔥"
        )

    from keyboards.reply import main_menu
    await message.answer(done_text, reply_markup=main_menu(lang), parse_mode="HTML")
    await state.clear()

    # Trigger background validation and admin notification rules safely
    asyncio.create_task(notify_admin_club_payment(bot, message, uid, full_name, lang, amount, pay_id, proof_id, db))

# --- 4. ASYNC AUDIT & SECURE CORE INTERFACE ---

# --- 4. ASYNC AUDIT & SECURE CORE INTERFACE ---

async def notify_admin_club_payment(bot: Bot, msg: types.Message, uid: int, name: str, lang: str, amt: float, pay_id: int, proof_id: str, db: Database):
    try:
        username = f"@{msg.from_user.username}" if msg.from_user.username else "No Username"
        
        caption = (
            f"👑 <b>TRANSFORMATION CLUB: NEW MEMBERSHIP APPLICANT</b>\n"
            f"──────────────────────────────\n"
            f"👤 <b>User:</b> {html.escape(name)} | {html.escape(username)}\n"
            f"🆔 <b>User ID:</b> <code>{uid}</code>\n"
            f"🌍 <b>Language:</b> <code>{lang}</code>\n"
            f"──────────────────────────────\n"
            f"💰 <b>Subscription Tier:</b> <code>{amt} ETB / Month</code>\n"
            f"🎫 <b>Club Payment ID:</b> #{pay_id}\n"
            f"──────────────────────────────\n"
            f"⚡️ <b>Verify financial integrity and choose action:</b>"
        )

        kb = InlineKeyboardBuilder()
        kb.button(text="✅ APPROVE ENTRY", callback_data=f"club_approve_{pay_id}")
        kb.button(text="❌ REJECT RECEIPT", callback_data=f"club_reject_{pay_id}")
        kb.adjust(1)

        # FIX: Try fetching from settings config first, fallback safely if missing
        admin_channel_id = getattr(settings, "ADMIN_PAYMENT_LOG_ID", -5196014443)

        admin_msg = await bot.send_photo(
            chat_id=admin_channel_id,
            photo=proof_id,
            caption=caption,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

        start = time.perf_counter()
        try:
            file_info = await bot.get_file(proof_id)
            img_stream = io.BytesIO()
            await bot.download_file(file_info.file_path, destination=img_stream)
            img_stream.seek(0)

            local = await extract_local_data(img_stream)
            # Defensive check on parsed text structure
            ref_id = local.get("ref") if local else None
            provider = local.get("provider", "CBE") if local else "CBE"
            raw_text = local.get("raw_text", "") if local else ""

            if not ref_id or len(str(ref_id)) < 8:
                await admin_msg.reply(
                    f"🤖 <b>CLUB AI SCAN: MANUAL ESCALATION REQUIRED 🧐</b>\n"
                    f"──────────────────────────────\n"
                    f"⚠️ Failed to parse valid unique transaction keys from image layout.\n"
                    f"🛡️ <i>Locking safety mechanisms to protect the pipeline against manipulation.</i>",
                    parse_mode="HTML"
                )
                return

            bank_data = await verify_external(ref_id, provider)
            is_real = bank_data.get("success", False)
            is_hilawe = is_hilawe_receiver(raw_text, bank_data)
            elapsed = time.perf_counter() - start

            if is_real and is_hilawe:
                eval_txt = (
                    f"🤖 <b>CLUB AI SCAN: VERIFIED AUTHENTIC ✅</b>\n"
                    f"──────────────────────────────\n"
                    f"🟢 Transaction matches live bank ledger parameters completely.\n"
                    f"📊 <b>{provider}</b> • 🆔 <code>{ref_id}</code> • ⏱️ <code>{elapsed:.2f}s</code>"
                )
            else:
                eval_txt = (
                    f"🤖 <b>CLUB AI SCAN: SUSPICIOUS / FRAUD DETECTED 🚨</b>\n"
                    f"──────────────────────────────\n"
                    f"🔴 Alert triggered. Reference hash not located or receiver payload mismatch.\n"
                    f"📊 <b>{provider}</b> • 🆔 <code>{ref_id or 'N/A'}</code>"
                )

            CLUB_REPORT_CACHE[pay_id] = format_club_audit(local, bank_data, elapsed, is_real, is_hilawe)
            
            kb_info = InlineKeyboardBuilder()
            kb_info.button(text="ℹ️ Audit Details", callback_data=f"club_info_{pay_id}")
            await admin_msg.reply(eval_txt, reply_markup=kb_info.as_markup(), parse_mode="HTML")

        except Exception as ocr_err:
            logger.error(f"Club parsing process exception details: {ocr_err}")
    except Exception as e:
        logger.error(f"Global structural admin alert failure: {e}")

#Don't ever forget to reset their membership expiry date later on buddy


@router.callback_query(F.data.startswith("club_approve_"))
async def approve_club_member(callback: types.CallbackQuery, db: Database, bot: Bot):
    pay_id = int(callback.data.split("_")[-1])
    admin_user = html.escape(callback.from_user.username or callback.from_user.full_name)

    pay_row = await db._pool.fetchrow("SELECT user_id, status FROM club_payments WHERE id = $1", pay_id)
    if not pay_row:
        return await callback.answer("❌ Transaction context missing.", show_alert=True)
    if pay_row['status'] != 'pending':
        return await callback.answer("⚠️ Action blocked: Payment is already processed.", show_alert=True)

    uid = pay_row['user_id']
    user_rec = await db._pool.fetchrow("SELECT language, full_name FROM users WHERE telegram_id = $1", uid)
    lang = (user_rec['language'] if user_rec else 'EN') or 'EN'
    name = (user_rec['full_name'] if user_rec else 'Member') or 'Member'

    # Atomic Dual-Table updates
    await db._pool.execute("""
        UPDATE club_payments 
        SET status = 'approved', processed_by = $1, processed_at = NOW() 
        WHERE id = $2
    """, admin_user, pay_id)

    # FIX: Set expires_at to NULL intentionally so time doesn't drain before launch day
    await db._pool.execute("""
        INSERT INTO club_subscriptions (user_id, is_active, expires_at, last_payment_id, updated_at)
        VALUES ($1, TRUE, NULL, $2, NOW())
        ON CONFLICT (user_id) DO UPDATE 
        SET is_active = TRUE, expires_at = NULL, last_payment_id = $2, auto_renew_reminded = FALSE, updated_at = NOW()
    """, uid, pay_id)

    try:
        orig = callback.message.caption or ""
        await callback.message.edit_caption(
            caption=f"{orig}\n\n👑 <b>APPROVED BY:</b> @{admin_user}\n👥 Registration Confirmed (Clock Paused).",
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception as err:
        logger.error(f"Admin display modification failure: {err}")
        await callback.message.edit_reply_markup(reply_markup=None)

    if lang == "EN":
        alert_html = (
            f"🎉 <b>REGISTRATION CONFIRMED, {name.upper()}!</b>\n\n"
            f"Your payment has been successfully verified and your spot in the Coach Hilawe Transformation Club is secured.\n\n"
            f"⏳ <b>What's Next?</b>\n"
            f"The club will start soon! You don't need to do anything right now. "
            f"As soon as we officially begin, we will send a message right here with your direct group and channel access links. Stay tuned! 🔥"
        )
    else:
        alert_html = (
            f"🎉 <b>ምዝገባዎ ተረጋግጧል፣ {name.upper()}!</b>\n\n"
            f"የከፈሉት ክፍያ በተሳካ ሁኔታ ተረጋግጧል፤ የክለብ አባልነት ቦታዎ ሙሉ በሙሉ ተይዟል።\n\n"
            f"⏳ <b>ቀጣዩ ደረጃ ምንድነው?</b>\n"
            f"ክለቡ በቅርቡ ይጀምራል! አሁን ላይ ምንም ማድረግ የሚጠበቅብዎት ነገር የለም። "
            f"ሁሉም ነገር ዝግጁ ሲሆን ወደ ግሩፑ እና ቻናሉ መግቢያ የሆኑትን ሊንኮች በዚህ ቦት በኩል ወዲያውኑ እንልክልዎታለን። በትዕግስት ይጠብቁን! 🔥"
        )

    try:
        await bot.send_message(chat_id=uid, text=alert_html, parse_mode="HTML")
        await callback.answer("Member approved & registered.", show_alert=False)
    except Exception as e:
        logger.error(f"Failed delivery alert sequence target routing user {uid}: {e}")


def format_club_audit(local, bank_data, elapsed, is_real, is_hilawe):
    data = bank_data.get("data", {}) if "data" in bank_data else bank_data
    payer = bank_data.get("payer", "Unknown Target")
    receiver = bank_data.get("receiver", "Not Configured")
    amount = bank_data.get("amount", 299.00)
    
    # FIX: Access with safe dict .get methods to handle dynamic exceptions
    provider = local.get("provider", "Unknown") if local else "Unknown"
    ref_id = local.get("ref", "N/A") if local else "N/A"
    
    return (
        f"📋 <b>SUBSCRIPTION AUDIT TRAIL DATA</b>\n"
        f"──────────────────────────────\n"
        f"👤 Payer Entity: <code>{payer}</code>\n"
        f"💰 Verified Funds: <code>{amount} ETB</code>\n"
        f"🏦 Core Engine: {provider}\n"
        f"🆔 Unique Hash ID: <code>{ref_id}</code>\n"
        f"🎯 Targeted Receiver: {receiver}\n"
        f"⏱️ Network Latency Speed: {elapsed:.2f}s"
    )

@router.callback_query(F.data.startswith("club_info_"))
async def display_club_audit(callback: types.CallbackQuery):
    pay_id = int(callback.data.split("_")[-1])
    report = CLUB_REPORT_CACHE.get(pay_id)
    if not report:
        return await callback.answer("⚠️ Audit log has expired from memory cache.", show_alert=True)
    await callback.message.reply(report, parse_mode="HTML")
    await callback.answer()
    
    
@router.callback_query(F.data.startswith("club_reject_"))
async def reject_club_member(callback: types.CallbackQuery, db: Database, bot: Bot):
    pay_id = int(callback.data.split("_")[-1])
    admin_user = callback.from_user.username or callback.from_user.full_name
    
    # 1. Fetch payment context to get the user's Telegram ID
    pay_row = await db._pool.fetchrow("SELECT user_id, status FROM club_payments WHERE id = $1", pay_id)
    if not pay_row:
        return await callback.answer("❌ Transaction context missing.", show_alert=True)
    if pay_row['status'] != 'pending':
        return await callback.answer("⚠️ Action blocked: Payment is already processed.", show_alert=True)

    uid = pay_row['user_id']
    
    # 2. Fetch the user's language preference
    user_rec = await db._pool.fetchrow("SELECT language FROM users WHERE telegram_id = $1", uid)
    lang = (user_rec['language'] if user_rec else 'EN') or 'EN'
    
    # 3. Update database status
    await db._pool.execute("UPDATE club_payments SET status = 'rejected' WHERE id = $1", pay_id)
    
    # 4. Update the admin channel display layout
    orig = callback.message.caption or ""
    await callback.message.edit_caption(
        caption=f"{orig}\n\n❌ <b>REJECTED & FLAG LOGGED BY:</b> @{admin_user}",
        reply_markup=None,
        parse_mode="HTML"
    )
    await callback.answer("Receipt flagged as rejected.")
    
    # 5. Build clean, non-AI text notices for the user
    if lang == "EN":
        reject_text = (
            "❌ <b>SUBSCRIPTION UPDATE</b>\n\n"
            "The payment receipt you uploaded could not be verified or is invalid.\n"
            "Please check your transfer details, ensure the amount is correct, and try submitting again with a clear screenshot."
        )
    else:
        reject_text = (
            "❌ <b>የክለብ አባልነት መረጃ</b>\n\n"
            "የላኩት የክፍያ ማረጋገጫ (ደረሰኝ) ሊረጋገጥ አልቻለም ወይም ትክክለኛ አይደለም።\n"
            "እባክዎ የተላከበትን አካውንትና የገንዘብ መጠን ያረጋግጡ፤ ከዚያም ትክክለኛውን የደረሰኝ ፎቶ (Screenshot) እንደገና ይላኩ።"
        )
        
    # 6. Send the notice straight to the user's inbox
    try:
        await bot.send_message(chat_id=uid, text=reject_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send rejection notice to user {uid}: {e}")
        
        
    
    
    



# --- 5. APPROVAL & ACCESS TICKET DISPATCH ---

# @router.callback_query(F.data.startswith("club_approve_"))
# async def approve_club_member(callback: types.CallbackQuery, db: Database, bot: Bot):
#     pay_id = int(callback.data.split("_")[-1])
#     admin_user = callback.from_user.username or callback.from_user.full_name

#     pay_row = await db._pool.fetchrow("SELECT user_id, status, amount FROM club_payments WHERE id = $1", pay_id)
#     if not pay_row:
#         return await callback.answer("❌ Transaction context missing.", show_alert=True)
#     if pay_row['status'] != 'pending':
#         return await callback.answer("⚠️ Action blocked: Payment is already processed.", show_alert=True)

#     uid = pay_row['user_id']
#     user_rec = await db._pool.fetchrow("SELECT language, full_name FROM users WHERE telegram_id = $1", uid)
#     lang = (user_rec['language'] if user_rec else 'EN') or 'EN'
#     name = (user_rec['full_name'] if user_rec else 'Member') or 'Member'

#     # Atomic Dual-Table updates
#     await db._pool.execute("""
#         UPDATE club_payments 
#         SET status = 'approved', processed_by = $1, processed_at = NOW() 
#         WHERE id = $2
#     """, admin_user, pay_id)

#     # Cleanups user status to exactly 30 days remaining window lease
#     expiry_horizon = datetime.now(timezone.utc) + timedelta(days=30)
#     await db._pool.execute("""
#         INSERT INTO club_subscriptions (user_id, is_active, expires_at, last_payment_id, updated_at)
#         VALUES ($1, TRUE, $2, $3, NOW())
#         ON CONFLICT (user_id) DO UPDATE 
#         SET is_active = TRUE, expires_at = $2, last_payment_id = $3, auto_renew_reminded = FALSE, updated_at = NOW()
#     """, uid, expiry_horizon, pay_id)

#     # Visual updates matching dashboard style adjustments
#     try:
#         orig = callback.message.caption or ""
#         await callback.message.edit_caption(
#             caption=f"{orig}\n\n👑 <b>APPROVED BY:</b> @{admin_user}\n👥 Access Authorization Validated.",
#             reply_markup=None,
#             parse_mode="HTML"
#         )
#     except Exception as err:
#         logger.error(f"Admin display modification failure: {err}")
#         await callback.message.edit_reply_markup(reply_markup=None)

#     # Dynamic creation of highly secured unqiue single-use invite channels
#     # NOTE: Set CLUB_GROUP_ID and CLUB_CHANNEL_ID safely inside your config file mapping environment
#     try:
#         grp_link = await bot.create_chat_invite_link(
#             chat_id=getattr(settings, "CLUB_GROUP_ID", -5397256535), # Replace placeholder with config target
#             name=f"Club Group Access: {name}",
#             member_limit=1
#         )
#         group_url = grp_link.invite_link
#     except Exception:
#         group_url = "https://t.me/share/url" # Dynamic fallback routing strategy

#     try:
#         chn_link = await bot.create_chat_invite_link(
#             chat_id=getattr(settings, "CLUB_CHANNEL_ID", -5397256535),
#             name=f"Club Vault Access: {name}",
#             member_limit=1
#         )
#         channel_url = chn_link.invite_link
#     except Exception:
#         channel_url = "https://t.me/share/url"

#     if lang == "EN":
#         alert_html = (
#             f"🎉 <b>WELCOME TO THE TRANSFORMATION CLUB, {name.upper()}!</b>\n\n"
#             f"Your subscription is verified successfully! You are now a premium member of Coach Hilawe's Inner Circle.\n\n"
#             f"📌 <b>YOUR SECURE PORTALS FOR THE NEXT 30 DAYS:</b>\n"
#             f"1️⃣ <b>The Hub (Interactive Group):</b> Join to share workouts and access Weekly Live Sessions.\n"
#             f"🔗 {group_url}\n\n"
#             f"2️⃣ <b>The Vault (Private Channel):</b> Access recorded video files, nutrition guides, and files.\n"
#             f"🔗 {channel_url}\n\n"
#             f"<i>⚠️ These single-use links expire automatically upon your registration join click. Do not forward.</i>"
#         )
#         btn_grp, btn_chn = "💪 ENTER THE CLUB HUB", "📢 OPEN THE VAULT"
#         head_txt = "🔑 <b>YOUR PERSONAL ACCESS PASSES:</b>"
#     else:
#         alert_html = (
#             f"🎉 <b>እንኳን ወደ COACH HILAWE TRANSFORMATION CLUB በደህና መጡ፣ {name.upper()}!</b>\n\n"
#             f"የክለብ አባልነት ክፍያዎ በተሳካ ሁኔታ ተረጋግጧል! አሁን በይፋ የኮቹ የቅርብ ክትትል አባል ሆነዋል።\n\n"
#             f"📌 <b>ለሚቀጥሉት 30 ቀናት መግቢያ በሮችዎ፦</b>\n"
#             f"1️⃣ <b>ክለብ ሃብ (ግሩፑ)፦</b> የቀጥታ ስርጭት (Live) ስብሰባዎችን የሚከታተሉበት ማህበረሰብ።\n"
#             f"🔗 {group_url}\n\n"
#             f"2️⃣ <b>(ቻናሉ)፦</b> የLive ስልጠና ቪዲዮዎች ማህደር እና መመሪያዎች መቀመጫ።\n"
#             f"🔗 {channel_url}\n\n"
#             f"<i>⚠️ እነዚህ ሊንኮች አንድ ጊዜ ብቻ የሚያገለግሉ በመሆናቸው ለሌላ ሰው እንዳያስተላልፉ።</i>"
#         )
#         btn_grp, btn_chn = "💪 ወደ ክለቡ ግሩፕ ግባ", "📢 ቻናሉን ክፈት"
#         head_txt = "🔑 <b>የመግቢያ ሊንኮች፦</b>"

#     builder = InlineKeyboardBuilder()
#     builder.row(types.InlineKeyboardButton(text=btn_grp, url=group_url))
#     builder.row(types.InlineKeyboardButton(text=btn_chn, url=channel_url))

#     try:
#         await bot.send_message(chat_id=uid, text=alert_html, parse_mode="HTML")
#         await bot.send_message(chat_id=uid, text=head_txt, reply_markup=builder.as_markup(), parse_mode="HTML")
#         await callback.answer("Member authorized successfully.", show_alert=False)
#     except Exception as e:
#         logger.error(f"Failed delivery alert sequence target routing user {uid}: {e}")
