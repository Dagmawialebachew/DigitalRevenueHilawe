import asyncio
from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatAction
import logging
from database.db import Database
from keyboards import inline as kb
from keyboards import reply as rkb
from utils.localization import get_level_prompt, get_text
from config import settings
router = Router(name="onboarding")

class OnboardingStepping(StatesGroup):
    language = State()
    gender = State()
    goal = State()       # Trainer Question 1
    level = State()      # Trainer Question 2
    obstacle = State()   # Trainer Question 3
    frequency = State()

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, bot: Bot, db: Database):
    await state.clear()
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    if user_data and user_data.get("onboarding_completed"):    # --- EXISTING USER FLOW ---
        await state.clear()
        lang = user_data.get('language', 'EN')
        user_id = message.from_user.id
        
        # Logic for Profile Card
        gender_icon = "👨" if user_data['gender'] == "MALE" else "👩"
        freq = user_data['frequency']
        full_name = message.from_user.full_name
        
        # --- BILINGUAL PROFILE CARD ---
        if lang == "AM":
            profile_card = (
                f"🛡️ *የአባልነት መታወቂያ*\n"
                f"————————————————————\n"
                f"👤 *ስም:* `{full_name.upper()}`\n"
                f"📊 *ደረጃ:* `{user_data['level'].upper()}`\n"
                f"🆔 *መለያ:* `HE-{user_id % 10000:04d}`\n"
                f"————————————————————\n"
                f"🧬 *ጾታ:* {gender_icon} | በሳምንት {freq} ቀን\n"
                f"🎯 *አላማ:* {user_data['goal'].replace('_', ' ')}\n"
                f"🌍 *ቋንቋ:* አማርኛ\n"
                f"————————————————————\n"
                f"እንኳን ደህና መጡ ሻምፒዮን። ለዛሬው ስልጠና ዝግጁ ነዎት?"
            )
        else:
            profile_card = (
                f"🛡️ *PROFILE CARD*\n"
                f"————————————————————\n"
                f"👤 *NAME:* `{full_name.upper()}`\n"
                f"📊 *LEVEL:* `{user_data['level'].upper()}`\n"
                f"🆔 *ID:* `HE-{user_id % 10000:04d}`\n"
                f"————————————————————\n"
                f"🧬 *BIO:* {gender_icon} | {freq}x Weekly\n"
                f"🎯 *TARGET:* {user_data['goal'].replace('_', ' ')}\n"
                f"🌍 *LANG:* English\n"
                f"————————————————————\n"
                f"Welcome back, Champion. Ready for today's session?"
            )
            
        # Send Profile Card with the Main Menu (Reply Keyboard)
        return await message.answer(
            profile_card, 
            reply_markup=rkb.main_menu(lang),
            parse_mode="Markdown"
        )

    #--- NEW USER FLOW (Onboarding) ---
    await state.clear()
    
    # Precise delay to mimic Hilawe sizing up the client
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await asyncio.sleep(1.5)
    
    welcome_text = (
        "I’ve spent years coaching over *300,000 people* on social media, but today, "
        "it’s just you and me. I am *Coach Hilawe*. 🤝\n\n"
        "You’re here because you’re done with average results. You want a science-based "
        "transformation blueprint designed for your specific body type and goals. 🏆\n\n"
        "🏁 *Step 1:* Choose your language to begin. \n"
        "*(Note: Your personalized 8-week program will be prepared in the language you select below.)*\n\n"
        "——————————————————\n\n"
        "በማህበራዊ ገጾች ከ *300,000 በላይ* ሰዎችን በማሰልጠን አመታትን አሳልፌያለሁ፤ ዛሬ ግን ትኩረቴ በእርስዎ ላይ ብቻ ነው። "
        "እኔ *አሰልጣኝ ህላዌ* ነኝ። 🤝\n\n"
        "እዚህ የተገኙት ተራ ለውጥ ፈልገው አይደለም፤ የሺዎችን ህይወት የለወጥኩበትን ሳይንሳዊ ዘዴ ተጠቅመው ማንነትዎን ለመቀየር ነው። 🏆\n\n"
        "🏁 *ምዕራፍ 1፦* ለመጀመር ቋንቋ ይምረጡ።\n"
        "*(ማሳሰቢያ፦ የእርስዎ የ8-ሳምንት ፕሮግራም የሚዘጋጀው እዚህ በሚመርጡት ቋንቋ ይሆናል።)*"
    )
    from keyboards import inline as kb
    await message.answer_photo(
    photo=settings.DESIGN_PHOTO_ID,
    caption=welcome_text,
    reply_markup=kb.language_markup(),
    parse_mode="Markdown"
)
    await state.set_state(OnboardingStepping.language)


@router.callback_query(OnboardingStepping.language)
async def process_language(callback: types.CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    lang = callback.data.replace("lang_", "")
    await state.update_data(language=lang)
    await db.create_or_update_user(callback.from_user.id, language=lang)
    
    # 1. Delete the welcome photo to clear the screen for the text animation
    await callback.message.delete()
    
    # 2. Start the loading sequence in a new text message
    # We create the message first so we can edit it in the loop
    loading_msg = await callback.message.answer("✨")
    
    stages = (
        ["Initializing...", "Setting up...", "Ready!"] 
        if lang == "EN" else 
        ["በማዘጋጀት ላይ...", "በማስተካከል ላይ...", "ተዘጋጅቷል!"]
    )
    
    # 3. ULTRA-PREMIUM ANIMATION (Loop through the new message)
    for stage in stages:
        await asyncio.sleep(0.5)
        # Use the handle of the new message we just sent
        await loading_msg.edit_text(f"✨ *{stage}*", parse_mode="Markdown")

    # Brief pause for dramatic effect
    await asyncio.sleep(0.3)
    
    # 4. Move to the actual assessment (Gender Selection)
    text = get_text(lang, "ask_gender")
    await loading_msg.edit_text(text, reply_markup=kb.gender_markup(lang))
    await state.set_state(OnboardingStepping.gender)
    
    
@router.callback_query(OnboardingStepping.gender)
async def process_gender(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data['language']
    await state.update_data(gender=callback.data.replace("gender_", ""))
    
    await callback.message.edit_text(get_text(lang, "ask_goal"), reply_markup=kb.goal_markup(lang))
    await state.set_state(OnboardingStepping.goal)

@router.callback_query(OnboardingStepping.goal)
async def process_goal(callback: types.CallbackQuery, state: FSMContext, db: Database):
    # Extract the goal from callback data (e.g., "goal_FATLOSS" -> "FATLOSS")
    selected_goal = callback.data.replace("goal_", "")
    
    # Save it to state so process_frequency can find it later
    await state.update_data(goal=selected_goal)
    
    data = await state.get_data()
    lang = data['language']
    gender = data.get('gender')

    # Build gender-aware prompt text
    prompt_text = get_level_prompt(lang, gender)

    await callback.message.edit_text(
        prompt_text,
        reply_markup=kb.level_markup(lang, gender),
        parse_mode="HTML"
    )
    await state.set_state(OnboardingStepping.level)

@router.callback_query(OnboardingStepping.level)
async def process_level(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data['language']
    await state.update_data(level=callback.data.replace("level_", ""))
    
    await callback.message.edit_text(get_text(lang, "ask_obstacle"), reply_markup=kb.obstacle_markup(lang))
    await state.set_state(OnboardingStepping.obstacle)

@router.callback_query(OnboardingStepping.obstacle)
async def process_obstacle(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data['language']
    await state.update_data(obstacle=callback.data.replace("obs_", ""))
    
    await callback.message.edit_text(get_text(lang, "ask_freq"), reply_markup=kb.freq_markup(lang))
    await state.set_state(OnboardingStepping.frequency)
    
@router.callback_query(OnboardingStepping.frequency)
async def process_frequency(callback: types.CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    freq = int(callback.data.replace("freq_", ""))
    await state.update_data(frequency=freq)

    data = await state.get_data()
    lang = data['language']
    user_id = callback.from_user.id
    full_name = callback.from_user.full_name
    
    # 1. DATABASE REGISTRATION
    await db.create_or_update_user(
        telegram_id=user_id,
        full_name=full_name,
        username=callback.from_user.username,
        language=lang,
        gender=data['gender'],
        level=data['level'],
        frequency=freq,
        goal=data.get('goal'),
        obstacle=data.get('obstacle'),
        onboarding_completed=True
    )

    # 2. CALIBRATION ANIMATION
    OBSTACLE_MAP = {
    "EN": {
        "DIET": "Nutrition & Diet",
        "CONSISTENCY": "Consistency",
        "NOPLAN": "Lack of Structure"
    },
    "AM": {
        "DIET": "የአመጋገብ ስርዓት",
        "CONSISTENCY": "ተነሳሽነት",
        "NOPLAN": "የተዋቀረ እቅድ"
    }
}
    raw_obs = data.get('obstacle', 'CONSISTENCY')
    
    # Get phrased obstacle: "የአመጋገብ ስርዓት" instead of "DIET"
    obs_phrased = OBSTACLE_MAP[lang].get(raw_obs, raw_obs)

    analysis_steps = [
        # STEP 1: Mirroring the Obstacle (Barnum Effect)
        (f"🎯 Aligning with your goal and bypassing <b>{obs_phrased}</b>...", 
         f"🎯 ግብዎን እና የ<b>{obs_phrased}</b> ችግርዎን መሰረት በማድረግ ፕሮግራሙን በማስተካከል ላይ..."),
        
        (f"📅 Designing your {freq}-day training split...", 
         f"📅 የ{freq} ቀን የልምምድ ክፍፍልዎን በማዘጋጀት ላይ..."),
        
        # STEP 3: Reinforcing the Mirror
        (f"⚖️ Scaling intensity to overcome <b>{obs_phrased}</b> at {data['level']} level...", 
         f"⚖️ የ<b>{obs_phrased}</b> ችግርን ለመቅረፍ እና ለ{data['level']} ብቃት የሚመጥን ጥንካሬ በማመጣጠን ላይ..."),
        
        ("✅ Assessment complete. Generating your profile...", 
         "✅ ግምገማው ተጠናቋል። መገለጫዎን በማውጣት ላይ...")
    ]
    
    for en, am in analysis_steps:
        step_text = en if lang == "EN" else am
        await asyncio.sleep(0.9) # Slightly slower for "High-End" feel
        try:
            await callback.message.edit_text(step_text, parse_mode="HTML")
        except Exception:
            import re
            clean_text = re.sub('<[^<]+?>', '', step_text)
            await callback.message.edit_text(clean_text, parse_mode=None)
    # 3. MATCH THE PRODUCT
    product = await db.match_product(lang, data['level'], freq)
    if not product:
        await callback.message.edit_text(get_text(lang, "no_product_found"))
        return

    # 4. SEND THE PROFILE CARD (Edit existing message)
    # 4. SEND THE PROFILE CARD (Edit existing message)
    gender_icon = "👨" if data['gender'] == "MALE" else "👩"
    
    # We use the phrased obstacle from our mapping for a natural look
    obs_phrased = OBSTACLE_MAP[lang].get(data.get('obstacle', 'CONSISTENCY'), "Consistency")

    if lang == "EN":
        profile_card = (
            f"💳 <b>PROFILE CARD</b>\n"
            "————————————————————\n"
            f"👤 <b>NAME:</b> {full_name.upper()}\n"
            f"📊 <b>LEVEL:</b> {data['level'].upper()}\n"
            f"🆔 <b>ID:</b> HE-{user_id % 10000:04d}\n"
            "————————————————————\n"
            f"⚠️ <b>VULNERABILITY:</b> Struggles with {obs_phrased}\n"
            f"📈 <b>SUCCESS PROBABILITY:</b> 94.7%\n"
            f"🧬 <b>GENDER:</b> {gender_icon} | {freq}x Weekly\n"
            f"🎯 <b>GOAL:</b> {data['goal'].replace('_', ' ')}\n"
            "————————————————————"
        )
    else:  # Amharic
        profile_card = (
            f"💳 <b>የአባልነት መገለጫ</b>\n"
            "————————————————————\n"
            f"👤 <b>ስም:</b> {full_name.upper()}\n"
            f"📊 <b>ደረጃ:</b> {data['level'].upper()}\n"
            f"🆔 <b>መለያ:</b> HE-{user_id % 10000:04d}\n"
            "————————————————————\n"
            f"⚠️ <b>ዋነኛ ተጋላጭነት:</b> {obs_phrased}\n"
            f"📈 <b>የስኬት እድል:</b> 94.7%\n"
            f"🧬 <b>ጾታ:</b> {gender_icon} | {freq} ጊዜ በሳምንት\n"            
            f"🎯 <b>ግብ:</b> {data['goal'].replace('_', ' ')}\n"
            "————————————————————"
        )

    await callback.message.edit_text(profile_card, parse_mode="HTML")

    # --- THE DRAMATIC PAUSE ---
    # We wait 2 seconds while showing the typing indicator
    await bot.send_chat_action(callback.message.chat.id, ChatAction.TYPING)
    await asyncio.sleep(2.5)

    # 5. SEND THE PITCH (As a NEW message)
    title = product['title']
    price = product['price']
    complete_label = get_text(lang, "analysis_complete")
    
    # Extract phrased obstacle for the Barnum effect in the pitch
    obs_phrased = OBSTACLE_MAP[lang].get(data.get('obstacle', 'CONSISTENCY'), "Consistency")

    if lang == "EN":
        actual_price = int(float(price) / 0.55)
        pitch = (
            f"🎯 <b>{complete_label}</b>\n\n"
            f"Most people fail because of <b>{obs_phrased}</b>. They guess, they wait, and they quit. "
            f"I made the <b>{title}</b> to solve this exact problem for you. 🏆\n\n"
            "<b>Your program includes:</b>\n"
            "✅ <b>8-Week Plan</b> - No more guessing what to do.\n"
            "✅ <b>Smart Nutrition</b> - The right food for fast results.\n"
            "✅ <b>Progress Tracker</b> - See your body change every week.\n"
            "✅ <b>Video Guides</b> - Learn the perfect form for every move.\n\n"
           "🌟 <b>HOLY WEEK SPECIAL OFFER</b>\n"
    f"<s>1,000 ETB</s> ➡️ <code>599 ETB</code>\n"
    "💎 You have a limited-time <b>40% Holy Week Discount</b> for Tinsae.\n\n"
            f"🔥 <b>Live Update:</b> Over 813 people bought this program this week. "
            f"Only <b>12 slots</b> are left for the {data['level'].upper()} group.\n\n"
            "⚠️ <b>Warning:</b> This is a one-time offer."
            "It is available only for 24hr!\n"
            "<b>Are you ready to start, or will you stay exactly where you are?</b>"
        )

    elif lang == "AM":
        actual_price = int(float(price) / 0.55)
        pitch = (
            f"🎯 <b>{complete_label}</b>\n\n"
            f"አብዛኛው ሰው ውጤት የማይመጣው በ<b>{obs_phrased}</b> ምክንያት ነው። "
            f"ይህን <b>{title}</b> ያዘጋጀሁት ይህንኑ ችግርዎን በቀጥታ እንዲፈታ ነው። 🏆\n\n"
            "<b>እቅዱ የሚያካትተው፦</b>\n"
            "✅ <b>የ8-ሳምንት የለውጥ ጉዞ</b> - ግራ መጋባትን የሚያስቀር።\n"
            "✅ <b>ሳይንሳዊ የአመጋገብ ስርአት</b> - ለፈጣን ለውጥ የሚረዳ።\n"
            "✅ <b>የሂደት መቆጣጠሪያ</b> - ለውጥዎን በየሳምንቱ የሚከታተሉበት።\n"
            "✅ <b>የቪዲዮ መመሪያ</b> - ለእያንዳንዱ እንቅስቃሴ ትክክለኛ አሰራር።\n\n"
             "🌟 <b>የትንሳኤ በዓል ልዩ ስጦታ</b>\n"
        f"<s>1,000 ብር</s> ➡️ <code>599 ብር</code>\n"
        "💎 ለትንሳኤ በዓል ብቻ የተዘጋጀ ልዩ <b>40% የቅዱስ ሳምንት ቅናሽ</b> ተግብረናል።\n\n"
            f"🔥 <b>ወቅታዊ መረጃ፦</b> እስካሁን ከ813 በላይ ሰዎች ገዝተዋል። "
            f"ለ{data['level']} ደረጃ የቀሩት <b>12 ቦታዎች</b> ብቻ ናቸው።\n\n"
            "⚠️ <b>ማሳሰቢያ፦</b> ይህ ቅናሽ ለ1ቀን ብቻ የሚቆይ ይሆናል።"
            "<b>አሁን ለመጀመር ዝግጁ ነዎት ወይስ ባሉበት መቀጠል ይመርጣሉ?</b>"
        )

    # Send the final pitch
    await callback.message.answer(
        pitch, 
        reply_markup=kb.payment_markup(lang, product['id']), 
        parse_mode="HTML"
    )

    asyncio.create_task(notify_admin_new_lead(bot, data, full_name, user_id, username=callback.from_user.username))
    import datetime

# Update the DB: user saw the pitch at this exact moment
    await db.execute(
        "UPDATE users SET last_pitch_at = $1 WHERE telegram_id = $2",
        datetime.datetime.now(),
        user_id
    )
    await state.clear()
    
def build_pitch(user, product):
    # Force uppercase to avoid "en" vs "EN" mismatch
    lang = user.get('language', 'EN').upper()
    level = user.get('level', 'BEGINNER')
    title = product.get('title', 'Training Plan')
    price = product.get('price', 0)
    
    # Safely get the obstacle or fallback
    obs_raw = user.get('obstacle', 'CONSISTENCY')
    
    # Barnum Effect Mapping
    obs_map = {
        "EN": {"DIET": "Nutrition", "CONSISTENCY": "Consistency", "NOPLAN": "Structure"},
        "AM": {"DIET": "የአመጋገብ ስርዓት", "CONSISTENCY": "ተነሳሽነት", "NOPLAN": "የተዋቀረ እቅድ"}
    }
    
    # Get the phrased obstacle based on language
    obs_phrased = obs_map.get(lang, obs_map["EN"]).get(obs_raw, "Consistency")
    
    # Math: Price calculation
    try:
        actual_price = int(float(price) / 0.55)
    except:
        actual_price = 0

    complete_label = "Analysis Complete" # Or use your get_text(lang, "analysis_complete")

    if lang == "AM":
        return (
            f"🎯 <b>{complete_label}</b>\n\n"
            f"አብዛኛው ሰው ውጤት የማይመጣው በ<b>{obs_phrased}</b> ምክንያት ነው። "
            f"ይህን <b>{title}</b> ያዘጋጀሁት ይህንኑ ችግርዎን በቀጥታ እንዲፈታ ነው። 🏆\n\n"
            "<b>እቅዱ የሚያካትተው፦</b>\n"
            "✅ <b>የ8-ሳምንት የለውጥ ጉዞ</b> - ግራ መጋባትን የሚያስቀር።\n"
            "✅ <b>ሳይንሳዊ የአመጋገብ ስርአት</b> - ለፈጣን ለውጥ የሚረዳ።\n"
            "✅ <b>የሂደት መቆጣጠሪያ</b> - ለውጥዎን በየሳምንቱ የሚከታተሉበት።\n"
            "✅ <b>የቪዲዮ መመሪያ</b> - ለእያንዳንዱ እንቅስቃሴ ትክክለኛ አሰራር።\n"
            "🔥 እስካሁን ይህን እቅድ የገዙ ፡ <b>813+</b>\n\n"
          "🌟 <b>የትንሳኤ በዓል ልዩ ስጦታ</b>\n"
        f"<s>1,000 ብር</s> ➡️ <code>599 ብር</code>\n"
        "💎 ለትንሳኤ በዓል ብቻ የተዘጋጀ ልዩ <b>40% የቅዱስ ሳምንት ቅናሽ</b> ተግብረናል።\n\n"
        "<b>አሁን ለመጀመር ዝግጁ ነዎት ወይስ ባሉበት መቀጠል ይመርጣሉ?</b>"
        )
    
    # Default to English (solves the NoneType error)
    return (
        f"🎯 <b>{complete_label}</b>\n\n"
        f"Most people fail because of <b>{obs_phrased}</b>. They guess, they wait, and they quit. "
        f"I made the <b>{title}</b> to solve this exact problem for you. 🏆\n\n"
        "<b>Your program includes:</b>\n"
        "✅ <b>8-Week Plan</b> - No more guessing what to do.\n"
        "✅ <b>Smart Nutrition</b> - The right food for fast results.\n"
        "✅ <b>Progress Tracker</b> - See your body change every week.\n"
        "✅ <b>Video Guides</b> - Learn the perfect form for every move.\n"
        "🔥 People who bought this program: <b> 813+ </b>\n\n"
        "🌟 <b>HOLY WEEK SPECIAL OFFER</b>\n"
    f"<s>1,000 ETB</s> ➡️ <code>599 ETB</code>\n"
    "💎 You have a limited-time <b>40% Holy Week Discount</b> for Tinsae.\n\n"
    "<b>Are you ready to start, or will you stay exactly where you are?</b>"
    )

@router.callback_query(F.data == "re_pitch_trigger")
async def re_pitch_trigger(callback: types.CallbackQuery, db: Database):
    user = await db.get_user(callback.from_user.id)
    product = await db.match_product(user['language'], user['level'], user['frequency'])
    if not product:
        return await callback.message.answer("No product found for your profile.")

    pitch_text = build_pitch(user, product)
    await callback.message.answer(
        pitch_text,
        reply_markup=kb.payment_markup(user['language'], product['id']),
        parse_mode="HTML"
    )





import html

async def notify_admin_new_lead(bot: Bot, user_data: dict, full_name: str, user_id: int, username: str = None):
    """Notify admins of a new registered lead."""
    try:
        safe_name = html.escape(full_name)
        safe_username = f"@{html.escape(username)}" if username else "No Username"

        admin_msg = (
            f"⚡️ <b>NEW USER REGISTERED</b>\n"
            "————————————————————\n"
            f"👤 <b>Name:</b> {safe_name}\n"
            f"🔗 <b>Username:</b> {safe_username}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"🌍 <b>Lang:</b> {html.escape(user_data.get('language','N/A'))}\n"
            f"🎯 <b>Goal:</b> {html.escape(user_data.get('goal','N/A'))}\n"
            f"📊 <b>Level:</b> {html.escape(user_data.get('level','N/A'))}\n"
            f"📅 <b>Freq:</b> {user_data.get('frequency','N/A')}x/week\n"
            "————————————————————\n"
            "🔥 <b>The empire is growing...</b>"
        )

        try:
                await bot.send_message(
                    chat_id=settings.ADMIN_NEW_USER_LOG_ID,
                    text=admin_msg,
                    parse_mode="HTML"
                )
        except Exception as e:
                logging.exception(f"Failed to notify admin {settings.ADMIN_NEW_USER_LOG_ID}: {e}")

    except Exception as e:
        logging.exception(f"Failed to process new lead notification: {e}")



