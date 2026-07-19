import asyncio
import logging
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import math
from database.db import Database
from config import settings

logger = logging.getLogger(__name__)
router = Router(name="admin_club_promo")

SCREENSHOT_FILE_IDS = [
    "AgACAgQAAxkB...YOUR_FILE_ID_1...", # Screenshot 1 (Main discussion chat)
    "AgACAgQAAxkB...YOUR_FILE_ID_2...", # Screenshot 2 (Meal confirmation)
    "AgACAgQAAxkB...YOUR_FILE_ID_3...", # Screenshot 3 (Local food variety)
    "AgACAgQAAxkB...YOUR_FILE_ID_4..."  # Screenshot 4 (Vault archive preview)
]


def get_promo_card(lang: str, has_bought: bool = False) -> tuple[str, types.InlineKeyboardMarkup]:
    """
    Generates an ultra-short, high-converting direct response broadcast message.
    Emphasizes community accountability and weekly live interactive Q&A sessions.
    """
    builder = InlineKeyboardBuilder()
    lang = lang.upper() if lang.upper() in ["AM", "EN"] else "EN"
    
    # --- STATE 1: COLD LEADS (NEVER PURCHASED ANYTHING) ---
    if not has_bought:
        if lang == "AM":
            text = (
                f"<b>🚨 የመጀመሪያው ዙር ሊዘጋ ጥቂት ቦታዎች ብቻ ቀሩ! 🚨</b>\n\n"
                f"ልክ ከላይ ባሉት ምስሎች ላይ እንደምታዩት፣ <b>ሂላዌ ትራንስፎርሜሽን ክለብ</b> አባላት በየቀኑ አብረው የሚለፉበት፣ የዕለት ተዕለት ምግባቸውንና እንቅስቃሴያቸውን እያጋሩ እርስ በርስ የሚበረታቱበት ንቁ ማህበረሰብ (Community) ነው፦\n\n"
                f"👥 <b>የጠንካሮች ስብስብ፦</b> ወንዶችም ሴቶችም በጋራ በመሆን ሆድና ቦርጭን ለማጥፋት፣ ክብደትን ለማስተካከልና ጡንቻን ለመገንባት በየቀኑ የምንነቃቃበት ልዩ ግሩፕ።\n"
                f"📹 **የቀጥታ የቪዲዮ ስብሰባ (Live Sessions)፦** በየሳምንቱ ከኮች ሂላዌ ጋር ፊት ለፊት በቪዲዮ በመገናኘት፣ ማንኛውንም አይነት የፊትነስና የአመጋገብ ጥያቄዎቻችሁን በቀጥታ የምታቀርቡበትና ምላሽ የምታገኙበት መድረክ።\n\n"
                f"ይህንን ሁሉንም ነገር የምታገኙት <b>በወር 299 ብር ብቻ</b> ነው! ሰዎች በፍጥነት እየገቡ ስለሆነ ይህ ዋጋ የሚቆየው ለጥቂት ሰዓታት ብቻ ነው።\n\n"
                f"ቦታው ሳይሞላ አሁኑኑ ማህበረሰባችንን ተቀላቀሉ፦ 👇"
            )
            btn_text = "🎯 ውስን ቦታውን አሁኑኑ ያዙ (299 ብር)"
        else:
            text = (
                f"<b>🚨 FIRST ROUND CLOSING: ONLY A FEW SPOTS LEFT! 🚨</b>\n\n"
                f"As you can see in the screenshots above, the <b>Hilawe Transformation Club</b> is an active group space where members push each other daily, sharing meals and workouts for ultimate consistency:\n\n"
                f"👥 <b>The Tribe:</b> Men and women running together to burn stubborn fat, manage weight, and build clean shape.\n"
                f"📹 <b>Weekly Live Audio/Video Q&As:</b> Get face-to-face with Coach Hilawe once a week to ask all your training and nutrition questions directly.\n\n"
                f"Access to this community is just <b>299 ETB/month</b>! Slots are filling fast, and this price will only remain open for a few hours.\n\n"
                f"Secure your spot and join the family now: 👇"
            )
            btn_text = "🎯 Claim Your Spot Now (299 ETB)"

    # --- STATE 2: EXISTING BUYERS (OWN A PROGRAM / ACCELERATION STEP) ---
    else:
        if lang == "AM":
            text = (
                f"<b>🚨 ለክለባችን አባላት የተደረገ ልዩ ጥሪ! 🚨</b>\n\n"
                f"የስፖርትና የአመጋገብ መመሪያችንን ቀድመው ይዘዋል፤ አሁን ደግሞ ያንን እውቀት ይበልጥ ወደ ተግባርና ወደ እውነተኛ ውጤት የሚቀይሩበት ጊዜ ነው!\n\n"
                f"<b>ሂላዌ ትራንስፎርሜሽን ክለብ</b> መመሪያውን በተሻለ ሁኔታ እንድትተገብሩ የሚያግዝ ማህበረሰብ ነው፦\n\n"
                f"🤝 <b>የጋራ መደጋገፍ፦</b> በምስሎቹ ላይ እንደሚታየው በየቀኑ የእርስ በርስ ምግቦችን እያየን የምንማርበትና የምንበረታታበት መድረክ።\n"
                f"🔥 <b>ቀጥታ ውይይት ከኮች ጋር፦</b> በየሳምንቱ በሚደረገው <b>Live ቪዲዮ</b> ላይ በመገኘት ማንኛውንም የሚያሻሽሏቸውን ጥያቄዎች ለኮች ሂላዌ በቀጥታ ጠይቀው ምላሽ የሚያገኙበት።\n\n"
                f"የቀደመ እቅድዎን ይበልጥ ለማስቀጠል ክፍያው <b>በወር 299 ብር ብቻ</b> ነው። ቦታዎች በጣም ውስን ስለሆኑ አሁኑኑ ያሻሽሉ👇"
            )
            btn_text = "🔥 የቪአይፒ ክለብ ቦታዎን አሁን ያዙ (299 ብር)"
        else:
            text = (
                f"<b>🚨 EXCLUSIVE CLUB UPGRADE NOTICE! 🚨</b>\n\n"
                f"You already have our training blueprint—now it's time to supercharge your execution layer with real group support!\n\n"
                f"The <b>Hilawe Transformation Club</b> is built to complement your current program perfectly:\n\n"
                f"🤝 <b>Daily Group Fire:</b> Share everyday meals and build clean habits alongside motivated men and women.\n"
                f"🔥 <b>Live Q&A Sessions:</b> Jump on our weekly **Live Video Meetings** and ask Coach Hilawe all your burning fitness and nutrition questions directly.\n\n"
                f"Take your progress to the next level for just <b>299 ETB/month</b>. Grab your upgrade before the last remaining seats fill up completely: 👇"
            )
            btn_text = "🔥 Upgrade to Live Club Tracking (299 ETB)"

    builder.button(text=btn_text, callback_data="initiate_club_subscription")
    return text, builder.as_markup()

# --- 2. ADMIN CONTROL GATEWAY CONTROL ---
@router.message(Command("club_broadcast"))
async def admin_broadcast_dashboard(message: types.Message):
    """
    Secures the broadcast interface behind your primary configured Admin Account.
    """
    if message.from_user.id != settings.ADMIN_IDS[0]:
        return

    admin_panel = (
        "🛠️ <b>TRANSFORMATION CLUB BROADCAST GATEWAY</b>\n"
        "──────────────────────────────────────────\n"
        "Choose an operational vector below. Running a test lets you check structural rendering "
        "and button formatting before sending to users."
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="🧪 Test Card (Admin Only)", callback_data="promo_test_run")
    kb.button(text="🚀 Live Broadcast (All Non-Club Users)", callback_data="promo_launch_live")
    kb.adjust(1)

    await message.answer(admin_panel, reply_markup=kb.as_markup(), parse_mode="HTML")


# --- 3. THE ISOLATED SAFETY TEST HARNESS ---
# --- 3. THE ISOLATED SAFETY TEST HARNESS ---
@router.callback_query(F.data == "promo_test_run")
async def execute_test_harness(callback: types.CallbackQuery, bot: Bot):
    """
    Safely delivers copies of all localized and tier iterations directly 
    into your chat alongside the 4 social proof screenshots.
    """
    if callback.from_user.id != settings.ADMIN_IDS[0]:
        return await callback.answer("⚠️ Access Denied.", show_alert=True)

    await callback.answer("Sending all structural preview variants...")
    admin_chat_id = callback.message.chat.id
    
    # Common Media Album structure for layout validation
    preview_album = [
        types.InputMediaPhoto(media=SCREENSHOT_FILE_IDS[0]),
        types.InputMediaPhoto(media=SCREENSHOT_FILE_IDS[1]),
        types.InputMediaPhoto(media=SCREENSHOT_FILE_IDS[2]),
        types.InputMediaPhoto(media=SCREENSHOT_FILE_IDS[3]),
    ]

    # 1. Render Amharic - Cold Lead Variant
    await callback.message.answer("📝 <b>[PREVIEW - AMHARIC - COLD LEAD]</b>", parse_mode="HTML")
    await bot.send_media_group(chat_id=admin_chat_id, media=preview_album)
    am_cold_txt, am_cold_kb = get_promo_card("AM", has_bought=False)
    await bot.send_message(chat_id=admin_chat_id, text=am_cold_txt, reply_markup=am_cold_kb, parse_mode="HTML")
    
    # 2. Render Amharic - VIP Upgrade Variant
    await callback.message.answer("📝 <b>[PREVIEW - AMHARIC - VIP UPGRADE]</b>", parse_mode="HTML")
    await bot.send_media_group(chat_id=admin_chat_id, media=preview_album)
    am_vip_txt, am_vip_kb = get_promo_card("AM", has_bought=True)
    await bot.send_message(chat_id=admin_chat_id, text=am_vip_txt, reply_markup=am_vip_kb, parse_mode="HTML")
    
    
# --- PHASE 1: BROADCAST PREVIEW & DOUBLE-CHECK ---
@router.callback_query(F.data == "promo_launch_live")
async def preview_live_broadcast(callback: types.CallbackQuery, db: Database):
    if callback.from_user.id != settings.ADMIN_IDS[0]:
        return await callback.answer("⚠️ Access Denied.", show_alert=True)

    # Completely opened to all users, filtering out active club subscribers
    count_query = """
        SELECT COUNT(1) 
        FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM club_subscriptions sub 
            WHERE sub.user_id = u.telegram_id AND sub.is_active = TRUE
        )
    """
    try:
        total_targets = await db._pool.fetchval(count_query)
    except Exception as sql_err:
        logger.error(f"Failed to count broad audience targets: {sql_err}")
        return await callback.message.answer(f"❌ <b>Database Error:</b>\n<code>{sql_err}</code>", parse_mode="HTML")

    if not total_targets or total_targets == 0:
        return await callback.message.edit_text(
            "🤷‍♂️ <b>Broadcast Aborted:</b> 0 outstanding target users found outside the club.", 
            parse_mode="HTML"
        )

    estimated_seconds = math.ceil(total_targets / 25)
    est_minutes = estimated_seconds // 60
    est_secs_remainder = estimated_seconds % 60
    time_str = f"{est_minutes}m {est_secs_remainder}s" if est_minutes > 0 else f"{estimated_seconds}s"

    preview_html = (
        f"📢 <b>BROADCAST PIPELINE PREVIEW</b>\n"
        f"──────────────────────────────────────────\n"
        f"📊 <b>Target Audience:</b> <code>{total_targets} users</code> (All non-club members)\n"
        f"🛡️ <b>Exclusion Rule:</b> Active Club Subscribers omitted\n"
        f"⚡ <b>Engine Strategy:</b> Dynamic Personalization (Cold vs VIP Tiers)\n"
        f"⏱️ <b>Estimated Duration:</b> ~<code>{time_str}</code>\n"
        f"📉 <b>Neon DB Footprint:</b> Optimized connection lease (&lt; 150ms)\n"
        f"──────────────────────────────────────────\n"
        f"⚠️ <b>Are you sure you want to fire this personalized broadcast live to ALL users right now?</b>"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="🔥 CONFIRM & LAUNCH LIVE", callback_data="promo_execute_confirmed")
    kb.button(text="❌ CANCEL BROADCAST", callback_data="promo_cancel_broadcast")
    kb.adjust(1)

    await callback.message.edit_text(preview_html, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


# --- PHASE 2: HIGH-SPEED BATCHED EXECUTION ---
# --- PHASE 2: HIGH-SPEED BATCHED EXECUTION ---
@router.callback_query(F.data == "promo_execute_confirmed")
async def execute_live_broadcast(callback: types.CallbackQuery, db: Database, bot: Bot):
    if callback.from_user.id != settings.ADMIN_IDS[0]:
        return await callback.answer("⚠️ Access Denied.", show_alert=True)

    await callback.message.edit_text("🛰️ <i>Stream target identities and state variations from database...</i>", parse_mode="HTML")

    # Pulls all users while retaining the active club subscription exclusion safety rail
    query = """
        SELECT u.telegram_id, COALESCE(u.language, 'EN') as language, u.has_paid
        FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM club_subscriptions sub 
            WHERE sub.user_id = u.telegram_id AND sub.is_active = TRUE
        )
    """
    try:
        targets = await db._pool.fetch(query)
    except Exception as sql_err:
        logger.error(f"Failed to query global targets: {sql_err}")
        return await callback.message.answer(f"❌ <b>Database Error:</b>\n<code>{sql_err}</code>", parse_mode="HTML")

    total_count = len(targets)
    if not targets:
        return await callback.message.edit_text("🤷‍♂️ 0 targets found after applying exclusion logic. Broadcast dropped.", parse_mode="HTML")

    await callback.message.edit_text(f"🚀 <b>Dispatching live to {total_count} personalized pipelines...</b>\nMonitoring performance counters.", parse_mode="HTML")

    success_tracks = 0
    failure_tracks = 0
    BATCH_SIZE = 15 
    
    async def send_safe_message(target_id, text, markup):
        nonlocal success_tracks, failure_tracks
        try:
            # 1. Build and dispatch the 4 screenshots as a combined album
            media_album = [
                types.InputMediaPhoto(media=SCREENSHOT_FILE_IDS[0]),
                types.InputMediaPhoto(media=SCREENSHOT_FILE_IDS[1]),
                types.InputMediaPhoto(media=SCREENSHOT_FILE_IDS[2]),
                types.InputMediaPhoto(media=SCREENSHOT_FILE_IDS[3]),
            ]
            await bot.send_media_group(chat_id=target_id, media=media_album)
            
            # 2. Instantly deliver the highly persuasive caption with the action button locked below
            await bot.send_message(
                chat_id=target_id, 
                text=text, 
                reply_markup=markup, 
                parse_mode="HTML"
            )
            success_tracks += 1
            
        except Exception as api_err:
            logger.warning(f"Delivery block on user {target_id}: {api_err}")
            failure_tracks += 1

    # Chunk loop protecting Neon CPU cycles and complying with Telegram rate ceilings
    for i in range(0, total_count, BATCH_SIZE):
        batch = targets[i:i + BATCH_SIZE]
        
        # Stagger task creation with a 0.05-second window to prevent 429 Flood burst crashes
        for record in batch:
            uid = record['telegram_id']
            lang = record['language'] or 'EN'
            has_paid_product = record['has_paid'] or False
            
            # Generate the specific personalized card iteration
            msg_text, msg_kb = get_promo_card(lang, has_bought=has_paid_product)
            
            # Execute sequentially per batch with a tiny microscopic delay to satisfy rate caps
            await send_safe_message(uid, msg_text, msg_kb)
            await asyncio.sleep(0.05)
        
        # Safe foundational baseline buffer time between batch waves
        await asyncio.sleep(1.0)

    summary_log = (
        f"🏁 <b>BROADCAST PIPELINE COMPLETE</b>\n"
        f"──────────────────────────────────────────\n"
        f"✅ Successfully Delivered: <code>{success_tracks}</code>\n"
        f"❌ Failed / Blocked: <code>{failure_tracks}</code>\n"
        f"📊 Target Engagement: <code>{total_count} total unique entries</code>"
    )
    
    await callback.message.edit_text(summary_log, parse_mode="HTML")
    await bot.send_message(chat_id=settings.ADMIN_IDS[0], text="System Log: Broadcast pipeline run completed cleanly.", parse_mode="HTML")
    

@router.callback_query(F.data == "promo_cancel_broadcast")
async def cancel_broadcast_action(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ <b>Broadcast Pipeline Aborted.</b> No messages were sent.", parse_mode="HTML")
    await callback.answer()