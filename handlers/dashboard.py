import asyncio

from aiogram import Router, F, types
from database.db import Database
from keyboards.reply import main_menu
import logging
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from utils.localization import get_text

router = Router(name="dashboard")
async def send_user_plan(event: types.Message | types.CallbackQuery, db: Database):
    user_id = event.from_user.id
    lang = await db.get_user_language(user_id)
    
    # Updated Query: Check for the latest payment regardless of status
    query = """
        SELECT pay.status, pr.telegram_file_id, pr.title 
        FROM payments pay
        JOIN products pr ON pay.product_id = pr.id
        WHERE pay.user_id = $1
        ORDER BY pay.created_at DESC LIMIT 1
    """
    plan_data = await db._pool.fetchrow(query, user_id)
    
    message = event if isinstance(event, types.Message) else event.message

    # Case 1: Active/Approved Plan
    if plan_data and plan_data['status'] == 'approved':
        caption = (
            f"🏆 *{plan_data['title'].upper()}*\n"
            f"————————————————————\n"
            "Your transformation program is active. 🔥"
        ) if lang == "EN" else (
            f"🏆 *{plan_data['title'].upper()}*\n"
            f"————————————————————\n"
            "የእርስዎ የለውጥ መመሪያ ዝግጁ ነው። 🔥"
        )
        return await message.answer_document(
            document=plan_data['telegram_file_id'],
            caption=caption,
            parse_mode="Markdown"
        )

    # Case 2: Pending Payment (Waiting for Admin)
    elif plan_data and plan_data['status'] == 'pending':
        pending_text = (
            "⏳ *PAYMENT VERIFICATION IN PROGRESS*\n\n"
            "I've received your receipt. I am currently verifying the transfer.\n\n"
            "You will receive your plan here the moment it is approved! 🙏"
        ) if lang == "EN" else (
            "⏳ *የክፍያ ማረጋገጫ በመከናወን ላይ*\n\n"
            "የላኩትን ደረሰኝ ተቀብያለሁ። በአሁኑ ሰዓት ክፍያውን እያረጋገጥኩ ነው።\n\n"
            "ልክ እንደተረጋገጠ እቅድዎን እዚህ ይላክሎታል! 🙏"
        )
        return await message.answer(pending_text, parse_mode="Markdown")

    # Case 3: No Payment or Rejected
    else:
        no_plan_text = (
            "❌ *NO ACTIVE PLAN FOUND*\n\n"
            "You haven't unlocked your transformation program yet. "
            "Go to the main menu and tap 'Unlock Plan' to start."
        ) if lang == "EN" else (
            "❌ *ምንም አይነት እቅድ አልተገኘም*\n\n"
            "እስካሁን ምንም አይነት የልምምድ እቅድ አልከፈቱም። "
            "ለመጀመር 'እቅዴን ክፈት' የሚለውን ይጫኑ።"
        )
        return await message.answer(no_plan_text, parse_mode="Markdown")

# 1. Reply Keyboard Handler (📦 My Plan)
@router.message(F.text.in_({"📦 My Plan", "📦 የእኔ እቅድ"}))
async def show_my_plan_message(message: types.Message, db: Database):
    await send_user_plan(message, db)

# 2. Inline Keyboard Handler (view_current_plan)
@router.callback_query(F.data == "view_current_plan")
async def show_my_plan_callback(callback: types.CallbackQuery, db: Database):
    await callback.answer() # Always answer callbacks to remove the loading spinner
    await send_user_plan(callback, db)
        
@router.message(F.text.in_({"⚙️ Settings", "⚙️ ማስተካከያ"}))
async def settings_view(message: types.Message, db: Database):
    user = await db.get_user(message.from_user.id)
    lang = user['language']
    
    # Visual ID Card
    bio_card = (
        f"🛡️ *Profile Cart*\n"
        f"————————————————————\n"
        f"📊 *LEVEL:* `{user['level'].upper()}`\n"
        f"📅 *FREQ:* `{user['frequency']} Days/Week`\n"
        f"🎯 *GOAL:* `{user['goal'].replace('_', ' ')}`\n"
        f"🌍 *LANG:* `{user['language']}`\n"
        f"————————————————————\n"
        f"💡 *Select a field below to update your profile instantly.*"
    ) if lang == "EN" else (
        f"🛡️ *የአትሌት መገለጫ*\n"
        f"————————————————————\n"
        f"📊 *ብቃት:* `{user['level']}`\n"
        f"📅 *ቀናት:* በሳምንት `{user['frequency']} ቀን`\n"
        f"🎯 *ግብ:* `{user['goal']}`\n"
        f"🌍 *ቋንቋ:* `{user['language']}`\n"
        f"————————————————————\n"
        f"💡 *መረጃዎን ለመቀየር ከታች ያሉትን ምርጫዎች ይጠቀሙ።*"
    )

    # Gorgeous Inline Keyboard for surgical edits
    builder = InlineKeyboardBuilder()
    builder.button(text="🎯 Goal" if lang == "EN" else "🎯 ግብ", callback_data="edit_goal")
    builder.button(text="📊 Level" if lang == "EN" else "📊 ብቃት", callback_data="edit_level")
    builder.button(text="📅 Freq" if lang == "EN" else "📅 ቀናት", callback_data="edit_frequency")
    builder.button(text="🌍 Lang" if lang == "EN" else "🌍 ቋንቋ", callback_data="edit_lang")
    builder.adjust(2)

    await message.answer(bio_card, reply_markup=builder.as_markup())
    
    
@router.message(F.text.in_({"💳 Unlock Plan", "💳 እቅዴን ክፈት"}))
async def initiate_unlock_flow(message: types.Message, db: Database):
    user_id = message.from_user.id if message.from_user else message.chat.id
    user = await db.get_user(user_id)
    lang = user['language']
    
    # --- 1. STATUS CHECK (Approved or Pending) ---
    # We check for any payment that isn't 'rejected'
    status_query = """
        SELECT pay.status, p.title 
        FROM payments pay
        JOIN products p ON pay.product_id = p.id
        WHERE pay.user_id = $1 AND pay.status IN ('approved', 'pending')
        ORDER BY pay.created_at DESC LIMIT 1
    """
    existing_payment = await db._pool.fetchrow(status_query, user_id)

    if existing_payment:
        status = existing_payment['status']
        
        if status == 'approved':
            # Case: Already bought it
            text = (
                f"✅ *PROGRAM ACTIVE*\n\n"
                f"I have already activated the *{existing_payment['title']}* for you."
                f"Check your 'My Plan' section to start your transformation."
            ) if lang == "EN" else (
                f"✅ *እቅድዎ ገቢር ሆኗል*\n\n"
                f"የ*{existing_payment['title']}* ስልጠናዎን ቀድሞውኑ ተከፍቶልዎታል። "
                f"'የእኔ እቅድ' ውስጥ በመግባት ስልጠናዎን መጀመር ይችላሉ።"
            )
            builder = InlineKeyboardBuilder()
            builder.button(text="📦 View My Plan" if lang == "EN" else "📦 እቅዴን ተመልከት", callback_data="view_current_plan")
            return await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

        elif status == 'pending':
            # Case: Sent receipt, waiting for Admin
            text = (
                "⏳ *VERIFICATION IN PROGRESS*\n\n"
                "I have received your receipt! I am currently verifying the transfer. "
                "You will receive a notification and your PDF the moment it is approved. "
                "\n\n*Estimated time: 1-3 hours.*"
            ) if lang == "EN" else (
                "⏳ *ማረጋገጫ በመካሄድ ላይ*\n\n"
                "የላኩት ደረሰኝ ደርሶኛል!  ክፍያውን እያረጋገጥኩ ነው። "
                "ልክ እንደተረጋገጠ መልዕክት እና የፒዲኤፍ (PDF) ፋይሉ ይላክለታል።"
                "\n\n*የሚፈጀው ጊዜ: ከ1-3 ሰዓታት።*"
            )
            return await message.answer(text, parse_mode="Markdown")

    # --- 2. MATCH PRODUCT (For New Users) ---
    product = await db.match_product(lang, user['level'], user['frequency'])
    
    if not product:
        no_prod_text = (
            "🚧 *REFINING PROGRAM*\n\n"
            "I'm currently optimizing the perfect plan for your specific metrics. "
            "Please check back in a few hours."
        ) if lang == "EN" else (
            "🚧 *እቅድ እየተዘጋጀ ነው*\n\n"
            "ለእርስዎ የሚሆን ትክክለኛ እቅድ በማዘጋጀት ላይ ነኝ። እባክዎ ከጥቂት ሰዓታት በኋላ ይመለሱ።"
        )
        return await message.answer(no_prod_text, parse_mode="Markdown")

    # --- 3. COACH REVIEW (The Sales Closer) ---
    coach_review = (
        f"👤 *COACH HILAWE'S REVIEW*\n\n"
        f"I have reviewed your profile, `{message.from_user.first_name}`. "
        f"Based on your *{user['level']}* experience and *{user['goal']}* goal, "
        f"I have prepared a high-intensity *{user['frequency']}-day* program for you.\n\n"
        f"⚠️ *Wait!* If these details are incorrect, go to *Settings* to update them now. "
        f"If you are ready to transform, proceed to the secure invoice below."
    ) if lang == "EN" else (
        f"👤 *የአሰልጣኝ ህላዌ ግምገማ*\n\n"
        f"ሰላም `{message.from_user.first_name}`; መገለጫዎን ተመልክቻለሁ። "
        f"ባለዎት የ*{user['level']}* ብቃት እና የ*{user['goal']}* ግብ መሰረት፣ "
        f"በሳምንት የ*{user['frequency']} ቀን* ልዩ ስልጠና አዘጋጅቼልዎታለሁ።\n\n"
        f"⚠️ *ቆይ!* እነዚህ መረጃዎች ስህተት ከሆኑ *ማስተካከያ* ውስጥ በመግባት ይቀይሩ። "
        f"ለመቀጠል ዝግጁ ከሆኑ ከታች ያለውን 'ክፍያ ጀምር' የሚለውን ይጫኑ።"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Complete Payment" if lang == "EN" else "💳 ክፍያ ጀምር", callback_data=f"pay_{product['id']}")
    builder.button(text="⚙️ Edit Information" if lang == "EN" else "⚙️ መገለጫ ቀይር", callback_data="open_settings")
    builder.adjust(1)

    await message.answer(coach_review, reply_markup=builder.as_markup(), parse_mode="Markdown")
    from aiogram.filters import Command

# Handles both /help command and Help button text
from aiogram.filters import Command
@router.message(Command("help"))
@router.message(F.text.in_({"❓ Help", "❓ እርዳታ"}))
async def help_view(message: types.Message, db: Database):
    lang = await db.get_user_language(message.from_user.id)
    text = (
        "❓ *SUPPORT CENTER*\n\n"
        "If you have issues with payments or plan access, "
        "contact our support team: @CoachHilaweSupportbot"
    ) if lang == "EN" else (
        "❓ *እርዳታ*\n\n"
        "ክፍያ በሚፈጽሙበት ጊዜ ወይም እቅድዎን ለማግኘት ችግር ካጋጠመዎት "
        "የእርዳታ መስመራችንን ያነጋግሩ፦ @CoachHilaweSupportbot"
    )
    await message.answer(text, parse_mode="Markdown")

    
    
    
from aiogram.fsm.state import State, StatesGroup
from keyboards import inline as ikb # Your inline keyboards file

class EditStates(StatesGroup):
    waiting_for_value = State()

# --- STEP 1: Catch the Edit Button Press ---
@router.callback_query(F.data.startswith("edit_"))
async def start_surgical_edit(callback: types.CallbackQuery, state: FSMContext, db: Database):
    field = callback.data.split("_")[1] # goal, level, freq, lang
    user = await db.get_user(callback.from_user.id)
    lang = user['language']
    gender = user.get('gender') # 👈 FETCH GENDER HERE
    
    await state.update_data(editing_field=field)
    await state.set_state(EditStates.waiting_for_value)

    # Map fields to their specific keyboards
    if field == "goal":
        await callback.message.edit_text(get_text(lang, "ask_goal"), reply_markup=ikb.goal_markup(lang))
    
    elif field == "level":
        # 👈 PASS GENDER HERE so the button is filtered correctly during editing
        await callback.message.edit_text(
            get_text(lang, "ask_level"), 
            reply_markup=ikb.level_markup(lang, gender) 
        )
        
    elif field == "frequency":
        await callback.message.edit_text(get_text(lang, "ask_freq"), reply_markup=ikb.freq_markup(lang))
        
    elif field == "lang":
        new_lang = "AM" if lang == "EN" else "EN"
        await db.create_or_update_user(callback.from_user.id, language=new_lang)
        await state.clear() 
        
        await callback.answer("Language Changed" if new_lang == "EN" else "ቋንቋ ተቀይሯል")
        
        # We call the refresh with a special flag to send a NEW message
        return await refresh_settings_view(callback, db, force_new=True)

    await callback.answer()

# --- STEP 2: Process the New Selection ---
# Use a filter that catches the callbacks from your onboarding keyboards
# --- STEP 2: Process the New Selection ---
@router.callback_query(EditStates.waiting_for_value)
async def process_surgical_update(callback: types.CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    field = data.get("editing_field") 
    
    raw_value = callback.data
    
    # 1. Surgical prefix stripping
    # Instead of a loop, strip only the prefix relevant to the field being edited
    prefix_map = {
        "goal": "goal_",
        "level": "level_",
        "frequency": "freq_"
    }
    
    current_prefix = prefix_map.get(field, "")
    clean_value = raw_value.replace(current_prefix, "")

    # 2. Safety Check: If the clean_value is still the same as raw_value, 
    # it means the user clicked a button that doesn't belong to this field.
    if clean_value == raw_value and field in prefix_map:
        return await callback.answer("⚠️ Please select an option from the menu above.")

    # 3. Type Conversion with Error Handling
    try:
        if field == "frequency":
            val = int(clean_value)
        else:
            val = clean_value
    except ValueError:
        logging.error(f"ValueError: Field {field} got data {clean_value}")
        return await callback.answer("⚠️ Invalid selection. Please try again.")

    # 4. Update Database
    await db.create_or_update_user(callback.from_user.id, *{field: val})
    
    # 5. UI Feedback
    user = await db.get_user(callback.from_user.id)
    lang = user['language']
    
    sync_text = "⚡️ *Updating Your Profile...*" if lang == "EN" else "⚡️ *መረጃዎን በማመሳሰል ላይ...*"
    await callback.message.edit_text(sync_text, parse_mode="Markdown")
    await asyncio.sleep(0.6) # Slightly faster for better UX
    
    await state.clear()
    await refresh_settings_view(callback, db)
    await callback.answer("Profile Updated" if lang == "EN" else "መረጃው ተቀይሯል")
    
async def get_bio_card_text(user: dict) -> str:
    """Centralized logic for the high-end ID card string"""
    lang = user['language']
    if lang == "EN":
        return (
            f"🛡️ *Profile Data*\n"
            f"————————————————————\n"
            f"📊 *LEVEL:* `{user['level'].upper()}`\n"
            f"📅 *FREQ:* `{user['frequency']} Days/Week`\n"
            f"🎯 *GOAL:* `{user['goal'].replace('_', ' ')}`\n"
            f"🌍 *LANG:* `{user['language']}`\n"
            f"————————————————————\n"
            f"💡 *Select a field below to update your profile instantly.*"
        )
    return (
        f"🛡️ *የእርስዎ መረጃ*\n"
        f"————————————————————\n"
        f"📊 *ብቃት:* `{user['level']}`\n"
        f"📅 *ቀናት:* በሳምንት `{user['frequency']} ቀን`\n"
        f"🎯 *ግብ:* `{user['goal']}`\n"
        f"🌍 *ቋንቋ:* `{user['language']}`\n"
        f"————————————————————\n"
        f"💡 *መረጃዎን ለመቀየር ከታች ያሉትን ምርጫዎች ይጠቀሙ።*"
    )
async def refresh_settings_view(callback: types.CallbackQuery, db: Database, force_new: bool = False):
    user = await db.get_user(callback.from_user.id)
    text = await get_bio_card_text(user)
    lang = user['language']
    
    # 1. Build the Inline Keyboard
    builder = InlineKeyboardBuilder()
    builder.button(text="🎯 Goal" if lang == "EN" else "🎯 ግብ", callback_data="edit_goal")
    builder.button(text="📊 Level" if lang == "EN" else "📊 ብቃት", callback_data="edit_level")
    builder.button(text="📅 Freq" if lang == "EN" else "📅 ቀናት", callback_data="edit_frequency")
    builder.button(text="🌍 Lang" if lang == "EN" else "🌍 ቋንቋ", callback_data="edit_lang")
    builder.adjust(2)
    
    inline_markup = builder.as_markup()

    if force_new:
        # 2. Delete the old message safely
        try:
            await callback.message.delete()
        except Exception:
            pass # Message already deleted or missing

        # 3. Send ONE fresh message containing:
        #    - The Bio Text
        #    - The Inline Buttons (Surgical edits)
        #    - The NEW Reply Keyboard (Main Menu refresh)
        from keyboards import reply as rkb
        await callback.message.answer(
            text, 
            reply_markup=inline_markup, # Inline buttons go here
            parse_mode="Markdown"
        )
        
        # 4. Trigger the bottom Reply Keyboard update with a small confirmation
        # This is the secret to changing the main menu buttons!
        await callback.message.answer(
            "✅ Menu Updated" if lang == "EN" else "✅ ዝርዝር ተቀይሯል",
            reply_markup=rkb.main_menu(lang)
        )
        
    else:
        # Standard edit for Goal/Level/Freq (Fastest UX)
        await callback.message.edit_text(
            text, 
            reply_markup=inline_markup, 
            parse_mode="Markdown"
        )
        
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.types import InputMediaPhoto   
from config import settings
@router.message(F.text.in_({"ℹ️ About me", "ℹ️ ስለ እኔ"}))
async def about_the_coach(message: types.Message, db: Database):
    user_data = await db.get_user(message.from_user.id)
    lang = user_data.get('language', 'EN')

    # THE SCRIPT: Pure Authority and Empathy
    if lang == "AM":
        caption = (
            "🏆 *አሰልጣኝ ህላዌ!*\n\n"
            "ባለፉት አመታት ከ *300,000* በላይ ተከታዮችን በማህበራዊ ገጾች በማፍራት "
            "እና በሺዎች የሚቆጠሩ ሰዎችን ህይወት በመቀየር የሚታወቅ ባለሙያ ነው።\n\n"
            "• *ልምድ:* 8+ አመታት በፊቲነስ ኢንዱስትሪ\n"
            "• *ፍልስፍና:* ሳይንስን እና ትጋትን በማጣመር የሚገኝ ውጤት\n"
            "እዚህ የመጣሁት ላሰለጥንህ ብቻ አይደለም፤ ማንነትህን እንድትቀይር ለማገዝ ጭምር ነው። "
            "ለውጥህን ለመጀመር ዝግጁ ነህ?"
        )
        cta_text = "🚀 ጉዞዬን ልጀምር"
    else:
        caption = (
            "🏆 *COACH HILAWE*\n\n"
            "With a community of over *300,000* followers and years of deep-level coaching, "
            "Hilawe has become Ethiopia's leading voice in science-based body transformation.\n\n"
            "• *Experience:* 8+ Years in Elite Fitness\n"
            "• *Philosophy:* Precision science meets raw discipline\n"
            "I’m not here to just give you a PDF. I’m here to redefine what you see in the mirror. "
            "Are you ready to be next?"
        )
        cta_text = "🚀 Start My Evolution"
        

    # BUILD THE GALLERY
    album = MediaGroupBuilder(caption=caption)
    album.add_photo("AgACAgQAAxkBAAICkGmjBaYwVMA-T4Umx_Nz87gCMSOpAAJ0DWsbZFQYUWoJ6IIDLj7VAQADAgADeQADOgQ") # Use your actual file ID
    album.add_photo("AgACAgQAAxkBAAICjmmjBYWs5UG-eCePehQbSeK-uUxfAAJzDWsbZFQYUYHRaHc6PNjNAQADAgADeQADOgQ")
    # album.add_photo(media=settings.TRANSFORMATION_2_ID)

    await message.answer_media_group(media=album.build())
    
    # Delayed Button for a "Natural" feeling
    builder = InlineKeyboardBuilder()
    builder.button(
        text=cta_text, 
        callback_data="trigger_unlock"  # Changed from "initiate_onboarding_or_payment"
)   
    await asyncio.sleep(1) # Let them look at the photos first
    await message.answer(
        "👇 Tap below to get your personalized program" if lang == "EN" else "👇 የእርስዎን እቅድ ለማግኘት ከታች ይጫኑ።",
        reply_markup=builder.as_markup()
    )
@router.callback_query(F.data == "trigger_unlock")
async def process_unlock_callback(callback: types.CallbackQuery, db: Database):
    # 1. Stop the loading spinner on the button
    await callback.answer()

    # 2. Identify user and language
    user_id = callback.from_user.id
    user_data = await db.get_user(user_id)
    
    # Safety check
    if not user_data:
        return await callback.message.answer("👋 Please type /start to register first!")

    lang = user_data.get('language', 'EN')

    # 3. Instruction Text
    if lang == "AM":
        text = (
            "🎯 *ድንቅ ምርጫ!*\n\n"
            "የስልጠና እቅድዎን ለማየት እና ክፍያውን ለመፈጸም ከታች ያለውን "
            "*'💳 እቅዴን ክፈት'* የሚለውን ቁልፍ ይጫኑ።"
        )
    else:
        text = (
            "🎯 *GREAT CHOICE.*\n\n"
            "To review your custom program and complete the process, "
            "please tap the *'💳 Unlock Plan'* button on your main menu below."
        )

    # 4. Send the message (The user will then see their existing Reply Keyboard)
    await callback.message.answer(text, parse_mode="Markdown")
    
@router.message(F.photo)
async def get_photo_id(message: types.Message):
    # message.photo is a list of different sizes; [-1] is the highest quality
    file_id = message.photo[-1].file_id
    
    response = (
        f"✅ *High-Res File ID Captured:*\n\n"
        f"`{file_id}`\n\n"
        f"Copy the ID above and paste it into your MediaGroupBuilder."
    )
    await message.reply(response, parse_mode="Markdown")