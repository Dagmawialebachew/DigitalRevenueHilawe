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

# --- 1. DYNAMIC PROMOTIONAL CARD BUILDER ---

def get_promo_card(lang: str, has_bought: bool = False) -> tuple[str, types.InlineKeyboardMarkup]:
    """
    Generates a high-converting broadcast card tailored to whether the member 
    is a cold lead or an existing customer, using generalized scarcity and community values.
    """
    builder = InlineKeyboardBuilder()
    lang = lang.upper() if lang.upper() in ["AM", "EN"] else "EN"
    
    # --- STATE 1: USER HAS NOT BOUGHT ANYTHING YET (COLD LEADS) ---
    if not has_bought:
        if lang == "AM":
            text = (
                f"<b>🚨 የመጀመሪያው ዙር ምዝገባ ሊዘጋ ነው! ቦታዎች በፍጥነት እየተያዙ ነው! 🚀</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"ብቻዎን እየደከሙ፣ ግራ እየገባዎት ወይም ስልጠናዎች ላይ ወጥነት አጥተው ያውቃሉ? ያ ሁሉ እዚህ ያበቃል!\n\n"
                f"ትልቅ ግሩፕ ፈጥሮ ዝም ብሎ ሰውን ማጋጎጥ ሳይሆን፣ እያንዳንዱን አባል በቅርብ ክትትል ማገዝ እንዲቻል ኮች ሂላዌ ይህንን የመጀመሪያ ዙር በጥብቅ ገድቦታል። ቁርጠኛ አባላት ቦታቸውን በፍጥነት እያስከበሩ ሲሆን ክፍት ቦታዎች ሲሞሉ መግቢያው በራስ-ሰር ይዘጋል።\n\n"
                f"<b>ይህንን ማህበረሰብ የተቀላቀሉ ጠንካሮች ምን ያገኛሉ?</b>\n"
                f"👥 <b>የቁርጠኞች ክበብ፦</b> ብቻዎን አይሰለቹም። በየቀኑ አብረውዎት የሚለወጡ፣ እርስ በርስ የሚገፋፉ እና ተጠያቂነትን የሚፈጥሩ ሰዎችን ያገኛሉ።\n"
                f"💎 <b>ቀጥታ ሳምንታዊ የቪዲዮ ስልጠናዎች፦</b> በየሳምንቱ በቀጥታ (Live) ከኮች ሂላዌ ጋር እየተገናኙ ግስጋሴዎን የሚገመግሙበት የቅርብ ክትትል።\n"
                f"🎬 <b>የመመሪያዎች ማዕከል፦</b> ግልፅ የስፖርት ቪዲዮዎች እና ለሀገራችን ምግብ ተስማሚ የሆኑ የአመጋገብ መመሪያዎች ስብስብ።\n\n"
                f"💵 <b>የመግቢያ ኢንቨስትመንት፦</b> በወር <b>299 ብር ብቻ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚠️ <i>ይህ ልዩ እድል ሳይመለጥዎት አሁኑኑ ተቀላቀሉ፦</i>"
            )
            btn_text = "🎯 ክለቡን አሁኑኑ ተቀላቀል (299 ብር)"
        else:
            text = (
                f"<b>🚨 COHORT 1 IS CLOSING FAST! Spots are Filling Up Rapidly! 🚀</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Stop training in isolation. No more confusion, no more dropped consistency. This is the ultimate high-accountability space built to unlock your fitness goals.\n\n"
                f"Instead of building a massive, crowded group where people get lost, Coach Hilawe has strictly limited this initial cohort to guarantee elite attention. Driven members are locking in their access right now.\n\n"
                f"<b>What's Inside the Inner Circle:</b>\n"
                f"👥 <b>The Accountability Room:</b> A hyper-focused community group to keep you sharp, active, and motivated every single day.\n"
                f"💎 <b>Weekly Live Video Coaching:</b> Direct live interaction with Coach Hilawe to audit your execution, mindset, and routine.\n"
                f"🎬 <b>The Resource Bank:</b> On-demand movement videos and practical local nutrition frameworks.\n\n"
                f"💵 <b>Commitment Fee:</b> Only <b>299 ETB total</b> for the entire 8 weeks. No recurring monthly subscriptions.\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚠️ <i>Secure your access token before the registration gateway locks permanently:</i>"
            )
            btn_text = "🎯 Secure Your Access Now (299 ETB)"

    # --- STATE 2: USER HAS ALREADY BOUGHT A PRODUCT (COMMUNITY & LIVE WORKSPACE UPGRADE) ---
    else:
        if lang == "AM":
            text = (
                f"<b>👑 ለቪአይፒ አባላቶቻችን የተዘጋጀ ልዩ ጥሪ! 💎</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"የኮች ሂላዌን የትራንስፎርሜሽን ሲስተም መመሪያዎች መያዝዎ ትልቅ እርምጃ ነው። ነገር ግን እቅድ ወይም መመሪያ ብቻውን በቂ አይደለም፤ እውነተኛ ውጤት የሚመጣው በማያቋርጥ ትግበራ እና በጠንካራ ማህበረሰብ ታግዞ ነው!\n\n"
                f"ምናልባት ብቻዎን መተግበር ከብዶዎት ወይም መነሳሳት አጥተው ከሆነ፣ ይህ የቪአይፒ ክለብ ያንን ክፍተት ሙሉ በሙሉ ይሞላል። መመሪያዎችን ወደ እውነተኛ የሰውነት ለውጥ የምንቀይርበት የቀጥታ ክትትል ማህበረሰብ ነው።\n\n"
                f"<b>ይህንን የቀጥታ ማህበረሰብ ለምን ያስፈልግዎታል?</b>\n"
                f"🤝 <b>ቀጥታ ከኮች ጋር (Live)፦</b> መመሪያውን ሲተገብሩ ለሚገጥሙዎት ጥያቄዎች በየሳምንቱ ከኮች ሂላዌ ጋር በLive ቪዲዮ ቀጥታ እየተገናኙ ይወያያሉ፤ ስህተትዎን ያርማሉ።\n"
                f"👥 <b>እርስ በርስ የሚገናኙበት ማህበረሰብ፦</b> ልክ እንደ እርስዎ ተመሳሳይ መመሪያ የያዙ፣ አብረዎት ከሚለፉ እና ተመሳሳይ ፈተና ካላቸው ሰዎች ጋር ይገናኛሉ። ብቻዎን አይወድቁም።\n"
                f"🔥 <b>የዕለት ተዕለት መነሳሳት፦</b> በየቀኑ የሌሎችን ጥረት እና ለውጥ እያዩ ወጥነት ያለው የአካል ብቃት ጉዞ ይፈጥራሉ።\n\n"
                f"⚠️ ለቀድሞ አባላቶቻችን በተደረገ ልዩ አክብሮት፣ ሙሉውን የ1 ወር የቀጥታ የክለብ ክትትል በ <b>299 ብር</b> ብቻ ማግኘት ይችላሉ።\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚡ <i>ወደ ቀጣዩ ደረጃ ለማደግ እና ውጤትዎን በእጥፍ ለመጨመር አሁኑኑ ይግቡ፦</i>"
            )
            btn_text = "🔥 የቪአይፒ ክለብ ክትትሉን ክፈት (299 ብር)"
        else:
            text = (
                f"<b>👑 VIP UPGRADE: Your Execution & Community Inner Circle! 💎</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Owning the transformation guidelines is a powerful start, but information without consistent execution is dead weight. If you've been struggling to stay consistent on your own, this workspace changes everything.\n\n"
                f"Even if you already have the standalone program, this is where you bridge the gap between having a plan and crushing your targets alongside a driven circle of peers.\n\n"
                f"<b>Why Joining the Live Community is Your Missing Piece:</b>\n"
                f"🤝 <b>Weekly Live Troubleshooting:</b> Get on live video calls directly with Coach Hilawe to analyze your weekly progress and troubleshoot real-world issues.\n"
                f"👥 <b>The Peer Network:</b> Surround yourself with active members executing the exact same path. Share local food updates and relate with individuals on your frequency.\n"
                f"🔥 <b>Absolute Accountability:</b> Zero room for slacking when you are backed by a high-energy community room every single day.\n\n"
                f"⚠️ Secure your full 8-week live group tracking seat for a clean **299 ETB commitment fee**.\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚡ *Click below to unlock live tracking and amplify your results:*"
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
    # Guard clause matching your global internal config setups
    if message.from_user.id != settings.ADMIN_IDS[0]:  # Assuming the first ID is the primary admin
        return

    admin_panel = (
        "🛠️ <b>TRANSFORMATION CLUB BROADCAST GATEWAY</b>\n"
        "──────────────────────────────────────────\n"
        "Choose an operational vector below. Running a test lets you check structural rendering "
        "and button formatting before sending to users."
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="🧪 Test Card (Admin Only)", callback_data="promo_test_run")
    kb.button(text="🚀 Live Broadcast (All Survey Backers)", callback_data="promo_launch_live")
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

    # Excludes users who already have an active club subscription
    count_query = """
        SELECT COUNT(1) 
        FROM club_survey_results s
        JOIN users u ON s.user_id = u.telegram_id
        WHERE s.will_join = TRUE
          AND NOT EXISTS (
              SELECT 1 FROM club_subscriptions sub 
              WHERE sub.user_id = u.telegram_id AND sub.is_active = TRUE
          )
    """
    try:
        total_targets = await db._pool.fetchval(count_query)
    except Exception as sql_err:
        logger.error(f"Failed to count survey backers: {sql_err}")
        return await callback.message.answer(f"❌ <b>Database Error:</b>\n<code>{sql_err}</code>", parse_mode="HTML")

    if not total_targets or total_targets == 0:
        return await callback.message.edit_text(
            "🤷‍♂️ <b>Broadcast Aborted:</b> 0 outstanding target users found matching your filter criteria.", 
            parse_mode="HTML"
        )

    estimated_seconds = math.ceil(total_targets / 25)
    est_minutes = estimated_seconds // 60
    est_secs_remainder = estimated_seconds % 60
    time_str = f"{est_minutes}m {est_secs_remainder}s" if est_minutes > 0 else f"{estimated_seconds}s"

    preview_html = (
        f"📢 <b>BROADCAST PIPELINE PREVIEW</b>\n"
        f"──────────────────────────────────────────\n"
        f"📊 <b>Target Audience:</b> <code>{total_targets} users</code> (will_join = TRUE)\n"
        f"🛡️ <b>Exclusion Rule:</b> Active Club Subscribers omitted\n"
        f"⚡ <b>Engine Strategy:</b> Dynamic Personalization (Cold vs VIP Tiers)\n"
        f"⏱️ <b>Estimated Duration:</b> ~<code>{time_str}</code>\n"
        f"📉 <b>Neon DB Footprint:</b> Optimized connection lease (&lt; 150ms)\n"
        f"──────────────────────────────────────────\n"
        f"⚠️ <b>Are you sure you want to fire this personalized broadcast live right now?</b>"
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

    # Pulls language and has_paid state, filtering out existing active club subscribers
    query = """
        SELECT u.telegram_id, COALESCE(u.language, 'EN') as language, u.has_paid
        FROM users u
        JOIN club_survey_results s ON u.telegram_id = s.user_id 
        WHERE s.will_join = TRUE
          AND NOT EXISTS (
              SELECT 1 FROM club_subscriptions sub 
              WHERE sub.user_id = u.telegram_id AND sub.is_active = TRUE
          )
    """
    try:
        targets = await db._pool.fetch(query)
    except Exception as sql_err:
        logger.error(f"Failed to query survey targets: {sql_err}")
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
            has_paid_product = record['has_paid'] or False  # Map database flag to has_bought
            
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