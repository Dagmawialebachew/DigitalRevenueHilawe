import asyncio
from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatAction
from database.db import Database
from keyboards import inline as kb
from keyboards import reply as rkb
from utils.localization import get_text
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
    # user_data = await db.get_user(user_id)
    # print('User Data:', user_data)  # Debugging line to check what we get from the database
    # if user_data:
    #     # --- EXISTING USER FLOW ---
    #     await state.clear()
    #     lang = user_data['language']
        
    #     # Logic for Profile Card
    #     gender_icon = "👨" if user_data['gender'] == "MALE" else "👩"
    #     freq = user_data['frequency']
    #     full_name = message.from_user.full_name
        
    #     profile_card = (
    #         f"🛡️ *ELITE PROFILE CARD*\n"
    #         f"————————————————————\n"
    #         f"👤 *NAME:* `{full_name.upper()}`\n"
    #         f"📊 *LEVEL:* `{user_data['level'].upper()}`\n"
    #         f"🆔 *ID:* `HE-{user_id % 10000:04d}`\n"
    #         f"————————————————————\n"
    #         f"🧬 *BIO:* {gender_icon} | {freq}x Weekly\n"
    #         f"🎯 *TARGET:* {user_data['goal'].replace('_', ' ')}\n"
    #         f"🌍 *LANG:* {lang}\n"
    #         f"————————————————————\n"
    #         f"Welcome back, Champion. Ready for today's session?" if lang == "EN" else
    #         f"እንኳን ደህና መጡ ሻምፒዮን። ለዛሬው ስልጠና ዝግጁ ነዎት?"
    #     )
        
    #     # Send Profile Card with the Main Menu (Reply Keyboard)
    #     return await message.answer(
    #         profile_card, 
    #         reply_markup=rkb.main_menu(lang),
    #         parse_mode="Markdown"
    #     )

    # --- NEW USER FLOW (Onboarding) ---
    await state.clear()
    
    # Precise delay to mimic Hilawe sizing up the client
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await asyncio.sleep(1.5)
    
    welcome_text = (
        "I’ve spent years coaching over *300,000 people* on social media, but today, "
        "it’s just you and me. I am *Coach Hilawe*. 🤝\n\n"
        "You’re here because you’re done with average results. You want the exact "
        "program I use to transform lives. Let’s stop talking and start building.\n"
        "🏁 *Step 1:* Choose your language to begin your assessment.\n\n"
        "------\n\n"
        "በተለያዩ ማህበራዊ ገጾች ከ *300,000 በላይ* ሰዎችን በማሰልጠን አመታትን አሳልፌያለሁ፤ ዛሬ ግን ትኩረቴ በእርስዎ ላይ ብቻ ነው። "
        "እኔ *አሰልጣኝ ህላዌ* ነኝ። 🤝\n\n"
        "እዚህ የተገኙት ተራ ለውጥ ስለፈለጉ አይደለም፤ የብዙዎችን ህይወት የለወጥኩበትን ትክክለኛ ዘዴ ለመጠቀም ፈልገው ነው። "
        "ለውጥህ የማይቀር ነው። ለስራው ዝግጁ ነህ?\n\n"
        "🏁 *ምዕራፍ 1፦* ግምገማውን ለመጀመር ቋንቋ ይምረጡ።"
    )
    
    await message.answer(welcome_text, reply_markup=kb.language_markup())
    await state.set_state(OnboardingStepping.language)
@router.callback_query(OnboardingStepping.language)
async def process_language(callback: types.CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    lang = callback.data.replace("lang_", "")
    await state.update_data(language=lang)
    await db.create_or_update_user(callback.from_user.id, language=lang)
    
    # --- ULTRA-PREMIUM ANIMATION ---
    # We replace the language buttons with a loading sequence
    stages = ["Initializing...", "Setting up...", "Ready!"] if lang == "EN" else ["በማዘጋጀት ላይ...", "በማስተካከል ላይ...", "ተዘጋጅቷል!"]
    
    for stage in stages:
        await asyncio.sleep(0.4)
        await callback.message.edit_text(f"✨ *{stage}*")

    # Brief pause for dramatic effect
    await asyncio.sleep(0.3)
    
    # Move to the actual assessment
    text = get_text(lang, "ask_gender")
    await callback.message.edit_text(text, reply_markup=kb.gender_markup(lang))
    await state.set_state(OnboardingStepping.gender)
    
@router.callback_query(OnboardingStepping.gender)
async def process_gender(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data['language']
    await state.update_data(gender=callback.data.replace("gender_", ""))
    
    await callback.message.edit_text(get_text(lang, "ask_goal"), reply_markup=kb.goal_markup(lang))
    await state.set_state(OnboardingStepping.goal)

@router.callback_query(OnboardingStepping.goal)
async def process_goal(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data['language']
    await state.update_data(goal=callback.data.replace("goal_", ""))
    
    await callback.message.edit_text(get_text(lang, "ask_level"), reply_markup=kb.level_markup(lang))
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
    analysis_steps = [
        (f"🎯 Aligning with your goal: {data['goal'].replace('_', ' ')}...", 
         f"🎯 ግብዎን መሰረት በማድረግ ፕሮግራሙን በማስተካከል ላይ፦ {data['goal'].replace('_', ' ')}..."),
        (f"📅 Designing your {freq}-day training split...", 
         f"📅 የ{freq} ቀን የልምምድ ክፍፍልዎን በማዘጋጀት ላይ..."),
        (f"⚖️ Scaling intensity for {data['level']} level...", 
         f"⚖️ የልምምድ ጥንካሬውን ለ{data['level']} ብቃት በማመጣጠን ላይ..."),
        ("✅ Assessment complete. Generating your profile...", 
         "✅ ግምገማው ተጠናቋል። መገለጫዎን በማውጣት ላይ...")
    ]
    
    for en, am in analysis_steps:
        step_text = en if lang == "EN" else am
        await asyncio.sleep(0.7)
        await callback.message.edit_text(f"{step_text}")

    # 3. MATCH THE PRODUCT
    product = await db.match_product(lang, data['gender'], data['level'], freq)
    if not product:
        await callback.message.edit_text(get_text(lang, "no_product_found"))
        return

    # 4. SEND THE PROFILE CARD (Edit existing message)
    gender_icon = "👨" if data['gender'] == "MALE" else "👩"
    profile_card = (
        f"💳 *PROFILE CARD*\n"
        f"————————————————————\n"
        f"👤 *NAME:* `{full_name.upper()}`\n"
        f"📊 *LEVEL:* `{data['level']}`\n"
        f"🆔 *ID:* `HE-{user_id % 10000:04d}`\n"
        f"————————————————————\n"
        f"🧬 *BIO:* {gender_icon} | {freq}x Weekly\n"
        f"🎯 *TARGET:* {data['goal'].replace('_', ' ')}\n"
        f"————————————————————"
    )
    
    await callback.message.edit_text(profile_card)

    # --- THE DRAMATIC PAUSE ---
    # We wait 2 seconds while showing the typing indicator
    await bot.send_chat_action(callback.message.chat.id, ChatAction.TYPING)
    await asyncio.sleep(2.5)

    # 5. SEND THE PITCH (As a NEW message)
    title = product['title']
    price = product['price']
    complete_label = get_text(lang, "analysis_complete")

    if lang == "EN":
        pitch = (
            f"🎯 *{complete_label}*\n\n"
            f"I have engineered the *{title}* specifically for your profile. 🏆\n\n"
            "*Your program includes:*\n"
            "✅ Science-based workout structure\n"
            "✅ Nutritional guidance for your level\n"
            "✅ The 'Hilawe-Method' for rapid results\n\n"
            f"💰 *Investment:* `{price} ETB`"
        )
    else:
        pitch = (
            f"🎯 *{complete_label}*\n\n"
            f"ለእርስዎ ተስማሚ የሆነውን *{title}* የተባለውን ልዩ እቅድ አውጥቻለሁ። 🏆\n\n"
            "*በዚህ እቅድ ውስጥ፦*\n"
            "✅ የልምምድ መዋቅር\n"
            "✅ የአመጋገብ መመሪያ\n"
            "✅ የ 'ህላዌ ዘዴ' ይካተታሉ\n\n"
            f"💰 *ኢንቨስትመንት፦* `{price} ብር`"
        )

    await callback.message.answer(pitch, reply_markup=kb.payment_markup(lang, product['id']))
    asyncio.create_task(notify_admin_new_lead(bot, data, full_name, user_id,username=callback.from_user.username))

    
    
    await state.clear()
    
    
async def notify_admin_new_lead(bot: Bot, user_data: dict, full_name: str, user_id: int, username: str = None):
        """Background task to notify admins of a new registered lead with username and contact."""
        try:
            # Format username for a clickable link
            user_link = f"@{username}" if username else "No Username"
            
            # Construct a high-end alert for the Admin
            admin_msg = (
                f"⚡️ *NEW USER REGISTERED*\n"
                f"————————————————————\n"
                f"👤 *Name:* {full_name}\n"
                f"🔗 *Username:* {user_link}\n"
                f"🆔 *ID:* `{user_id}`\n"
                f"🌍 *Lang:* {user_data['language']}\n"
                f"🎯 *Goal:* {user_data.get('goal', 'N/A')}\n"
                f"📊 *Level:* {user_data.get('level', 'N/A')}\n"
                f"📅 *Freq:* {user_data.get('frequency')}x/week\n"
                f"————————————————————\n"
                f"🔥 *The empire is growing...*"
            )
            
            for admin_id in settings.ADMIN_IDS:
                try:
                    # We use HTML or MarkdownV2 to make the username clickable
                    await bot.send_message(
                        chat_id=settings.ADMIN_NEW_USER_LOG_ID, 
                        text=admin_msg,
                        parse_mode="Markdown"
                    )
                except Exception:
                    continue
                    
        except Exception as e:
            pass