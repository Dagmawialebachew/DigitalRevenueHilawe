with open('handlers/onboarding.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('\r\n', '\n')

old_code = """    builder.adjust(1, 2)
    await loading_msg.edit_text(welcome_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(OnboardingStepping.gender)
    
    
@router.callback_query(OnboardingStepping.gender)
async def process_gender(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data['language']
    await state.update_data(gender=callback.data.replace("gender_", ""))"""

new_code = """    builder.adjust(1, 2)
    await loading_msg.edit_text(welcome_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(OnboardingStepping.gender)


@router.callback_query(F.data == "retarget_resume")
async def process_retarget_resume(callback: types.CallbackQuery, state: FSMContext, db: Database):
    await callback.answer()
    user_id = callback.from_user.id
    user_data = await db.get_user(user_id)
    lang = user_data.get('language', 'AM') if user_data else 'AM'
    await state.update_data(language=lang)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()

    if lang == "AM":
        resume_text = (
            "🎯 <b>በጣም አሪፍ ወዳጄ! ጥያቄዎቹን ፈጠን ብለን እንጨርስ።</b>\\n\\n"
            "<b>ጾታዎን ይምረጡ፦</b>"
        )
        builder.button(text="👨 ወንድ", callback_data="gender_MALE")
        builder.button(text="👩 ሴት", callback_data="gender_FEMALE")
    else:
        resume_text = (
            "🎯 <b>Awesome! Let's finish up in 30 seconds.</b>\\n\\n"
            "<b>Select your gender:</b>"
        )
        builder.button(text="👨 Male", callback_data="gender_MALE")
        builder.button(text="👩 Female", callback_data="gender_FEMALE")

    builder.adjust(2)
    await callback.message.answer(resume_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(OnboardingStepping.gender)


@router.callback_query(OnboardingStepping.gender)
@router.callback_query(F.data.startswith("gender_"))
async def process_gender(callback: types.CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    lang = data.get('language')
    if not lang:
        user_data = await db.get_user(callback.from_user.id)
        lang = user_data.get('language', 'AM') if user_data else 'AM'
        await state.update_data(language=lang)
    await state.update_data(gender=callback.data.replace("gender_", ""))"""

if old_code in text:
    text = text.replace(old_code, new_code)
    with open('handlers/onboarding.py', 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print("Updated handlers/onboarding.py successfully!")
else:
    print("old_code not found in handlers/onboarding.py")

