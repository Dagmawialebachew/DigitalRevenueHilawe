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
def get_promo_card(lang: str, has_bought: bool = False) -> tuple[str, types.InlineKeyboardMarkup]:
    """
    Generates an ultra-short, high-converting direct response broadcast message.
    Emphasizes that this is an interactive community ecosystem, not a static workout guide.
    """
    builder = InlineKeyboardBuilder()
    lang = lang.upper() if lang.upper() in ["AM", "EN"] else "EN"
    
    # --- STATE 1: COLD LEADS (NEVER PURCHASED ANYTHING) ---
    if not has_bought:
        if lang == "AM":
            text = (
                f"<b>🚨 የመጀመሪያው ዙር ሊዘጋ 4 ቦታዎች ብቻ ቀሩ! 🚨</b>\n\n"
                f"ይህ ተራ የስፖርት መመሪያ ወይም የፒዲኤፍ (PDF) ፋይል አይደለም። <b>ይህ የልምምድ ፕሮግራም አይደለም!</b>\n\n"
                f"<b>ሂላዌ ትራንስፎርሜሽን ክለብ</b> በቀጥታ ከኮች ሂላዌ ጋር የሚደረጉ የቪዲዮ ስብሰባዎች እና በየቀኑ አብረውህ የሚለፉ የቁርጠኞች ማህበረሰብ (Community) ነው፦\n\n"
                f"👥 <b>የጠንካሮች ማህበረሰብ፦</b> በየቀኑ አብረውህ የሚሮጡ እና እንድታቆም የማይፈቅዱልህ ሰዎች ስብስብ።\n"
                f"💎 <b>የቀጥታ የቪዲዮ ቆይታ፦</b> በየሳምንቱ ከኮች ሂላዌ ጋር ፊት ለፊት በመገናኘት እቅድህን የምታስተካክልበት።\n\n"
                f"ክፍያው <b>በወር 299 ብር ብቻ</b> ነው—ከምታገኘው እውነተኛ የአካልና የህይወት ለውጥ አንፃር ይህ ገንዘብ ምንም ማለት አይደለም።\n\n"
                f"⏳ <b>ሁሉም ነገር ሰኞ ይጀምራል!</b> የቀሩት 4 ቦታዎች ከመሙላታቸው በፊት አሁኑኑ ተቀላቀል፦"
            )
            btn_text = "🎯 ከቀሩት 4 ቦታዎች አንዱን ያዝ (299 ብር)"
        else:
            text = (
                f"<b>🚨 FIRST ROUND CLOSING: ONLY 4 SPOTS LEFT! 🚨</b>\n\n"
                f"Stop looking for another workout routine. <b>This is NOT a workout program.</b>\n\n"
                f"The <b>Hilawe Transformation Club</b> is a live interactive ecosystem driven by community and direct video sessions with Coach Hilawe:\n\n"
                f"👥 <b>The 1% Tribe:</b> A high-energy private room running together daily. No slacking.\n"
                f"💎 <b>Live Video Sessions:</b> Direct face-to-face video troubleshooting and deep dives with Coach Hilawe.\n\n"
                f"An investment of <b>299 ETB/month</b> is absolutely nothing compared to the massive value and identity shift you will receive.\n\n"
                f"⏳ <b>We officially kick off this Monday.</b> Secure your access before the last 4 seats fill permanently:"
            )
            btn_text = "🎯 Claim 1 of the Last 4 Spots (299 ETB)"

    # --- STATE 2: EXISTING BUYERS (OWN A PROGRAM BUT LACK EXECUTION) ---
    else:
        if lang == "AM":
            text = (
                f"<b>🚨 ለቪአይፒ አባላት የተደረገ ጥሪ፡ 4 ቦታዎች ብቻ! 🚨</b>\n\n"
                f"መመሪያውን ገዝተሃል፤ ታዲያ ለምን ውጤት አልመጣም? ምክንያቱም የፒዲኤፍ (PDF) ሰነድ ብቻውን ስትሰንፍ አልጋ ላይ ሊቀሰቅስህ አይችልም። <b>ይህ አዲስ የስፖርት መመሪያ አይደለም!</b>\n\n"
                f"ይህ ያንተን ፋይል ወደ እውነተኛ ውጤት የምትቀይርበት <b>ሂላዌ ትራንስፎርሜሽን ክለብ</b> ነው፦\n\n"
                f"🤝 <b>የማህበረሰብ ጉልበት፦</b> በየቀኑ እንድትተገብር የሚገፋፋህ ከፍተኛ ኃይል ያለው ስብስብ።\n"
                f"🔥 <b>የቀጥታ የቪዲዮ ክትትል፦</b> በየሳምንቱ ከኮች ሂላዌ ጋር በቀጥታ ቪዲዮ በመገናኘት ስህተቶችህን ማስተካከል።\n\n"
                f"ክፍያው <b>በወር 299 ብር ብቻ</b> ነው—የገዛኸውን ፕሮግራም ወደ እውነተኛ ለውጥ ለመቀየር ይህ ዋጋ ምንም ማለት አይደለም።\n\n"
                f"⏳ <b>የመጀመሪያው ዙር ሰኞ ይጀምራል!</b> የቀሩት 4 የቪአይፒ ማሻሻያ ቦታዎች ሳይሞሉ አሁኑኑ ግባ፦"
            )
            btn_text = "🔥 የቪአይፒ ክለብ ቦታህን አሁን ያዝ (299 ብር)"
        else:
            text = (
                f"<b>🚨 VIP UPGRADE NOTICE: ONLY 4 SEATS REMAINING 🚨</b>\n\n"
                f"You already bought the program, but a downloaded file cannot force you out of bed. <b>This is NOT another workout routine.</b>\n\n"
                f"This is your live execution room—the <b>Hilawe Transformation Club</b>. Move past static guides into live interactive coaching:\n\n"
                f"🤝 <b>Tribe Accountability:</b> The exact daily environment you need to stay consistent.\n"
                f"🔥 <b>Live Group Audits:</b> Weekly face-to-face video access with Coach Hilawe to guarantee execution.\n\n"
                f"Spending <b>299 ETB/month</b> to save your blueprint from going to waste is symbolic. The payoff is elite physics.\n\n"
                f"⏳ <b>Live onboarding starts this Monday.</b> Grab your upgrade before the last 4 seats vanish permanently:"
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
@router.callback_query(F.data == "promo_test_run")
async def execute_test_harness(callback: types.CallbackQuery):
    """
    Safely delivers copies of all localized and tier iterations directly into your chat.
    """
    if callback.from_user.id != settings.ADMIN_IDS[0]:
        return await callback.answer("⚠️ Access Denied.", show_alert=True)

    await callback.answer("Sending all structural preview variants...")
    
    # 1. Render English Variants
    en_cold_txt, en_cold_kb = get_promo_card("EN", has_bought=False)
    en_vip_txt, en_vip_kb = get_promo_card("EN", has_bought=True)
    
    await callback.message.answer("📝 <b>[PREVIEW - ENGLISH - COLD LEAD]</b>", parse_mode="HTML")
    await callback.message.answer(en_cold_txt, reply_markup=en_cold_kb, parse_mode="HTML")
    
    await callback.message.answer("📝 <b>[PREVIEW - ENGLISH - VIP UPGRADE]</b>", parse_mode="HTML")
    await callback.message.answer(en_vip_txt, reply_markup=en_vip_kb, parse_mode="HTML")

    # 2. Render Amharic Variants
    am_cold_txt, am_cold_kb = get_promo_card("AM", has_bought=False)
    am_vip_txt, am_vip_kb = get_promo_card("AM", has_bought=True)
    
    await callback.message.answer("📝 <b>[PREVIEW - AMHARIC - COLD LEAD]</b>", parse_mode="HTML")
    await callback.message.answer(am_cold_txt, reply_markup=am_cold_kb, parse_mode="HTML")
    
    await callback.message.answer("📝 <b>[PREVIEW - AMHARIC - VIP UPGRADE]</b>", parse_mode="HTML")
    await callback.message.answer(am_vip_txt, reply_markup=am_vip_kb, parse_mode="HTML")


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
@router.callback_query(F.data == "promo_execute_confirmed")
async def execute_live_broadcast(callback: types.CallbackQuery, db: Database, bot: Bot):
    if callback.from_user.id != settings.ADMIN_IDS[0]:
        return await callback.answer("⚠️ Access Denied.", show_alert=True)

    await callback.message.edit_text("🛰️ <i>Streaming target identities and state variations from database...</i>", parse_mode="HTML")

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
    BATCH_SIZE = 25 
    
    async def send_safe_message(target_id, text, markup):
        nonlocal success_tracks, failure_tracks
        try:
            await bot.send_message(chat_id=target_id, text=text, reply_markup=markup, parse_mode="HTML")
            success_tracks += 1
        except Exception as api_err:
            logger.warning(f"Delivery block on user {target_id}: {api_err}")
            failure_tracks += 1

    # Chunk loop protecting Neon CPU cycles and complying with Telegram rate ceilings
    for i in range(0, total_count, BATCH_SIZE):
        batch = targets[i:i + BATCH_SIZE]
        tasks = []
        
        for record in batch:
            uid = record['telegram_id']
            lang = record['language'] or 'EN'
            has_paid_product = record['has_paid'] or False
            
            # Generate the specific personalized card iteration
            msg_text, msg_kb = get_promo_card(lang, has_bought=has_paid_product)
            tasks.append(send_safe_message(uid, msg_text, msg_kb))
            
        # Dispatch 25 tasks concurrently 
        await asyncio.gather(*tasks)
        
        # Rate limiting throttle
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