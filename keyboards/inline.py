from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# --- [ SECTION 1: MAIN COMMAND CENTER (REPLY) ] ---
# Using ReplyKeyboardMarkup for 300k scale ensures the admin never 
# loses the "Main Menu" even if they scroll up far.

def admin_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📊 Business Stats"),
        KeyboardButton(text="⏳ Pending Payments")
    )
    builder.row(
        KeyboardButton(text="📦 Add New Product"),
        KeyboardButton(text="📢 Global Broadcast")
    )
    builder.row(
        KeyboardButton(text="🛠 Manage Products")
    )
    return builder.as_markup(resize_keyboard=True, placeholder="Hilawe Elite Admin Panel")


# --- [ SECTION 2: ONBOARDING ENGINE (INLINE) ] ---

def language_markup() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇸 English", callback_data="lang_EN")
    builder.button(text="🇪🇹 አማርኛ", callback_data="lang_AM")
    builder.adjust(2)
    return builder.as_markup()

def gender_markup(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    m_text = "♂️ Male" if lang == "EN" else "♂️ ወንድ"
    f_text = "♀️ Female" if lang == "EN" else "♀️ ሴት"
    builder.button(text=m_text, callback_data="gender_MALE")
    builder.button(text=f_text, callback_data="gender_FEMALE")
    builder.adjust(2)
    return builder.as_markup()

def goal_markup(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if lang == "EN":
        builder.button(text="🔥 Shed Fat & Lean", callback_data="goal_FATLOSS")
        builder.button(text="💪 Build Muscle & Strength", callback_data="goal_MUSCLE")
        builder.button(text="🏃 Conditioning & Endurance", callback_data="goal_ATHLETE")
    else:
        builder.button(text="🔥 ስብ መቀነስ/ማስተካከል", callback_data="goal_FATLOSS")
        builder.button(text="💪 ጡንቻ መገንባት", callback_data="goal_MUSCLE")
        builder.button(text="🏃 አጠቃላይ የአካል ብቃት", callback_data="goal_ATHLETE")
    builder.adjust(1)
    return builder.as_markup()

def level_markup(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    levels = [
        ("Beginner", "ጀማሪ", "BEGINNER"),
        ("Intermediate", "መካከለኛ", "INTERMEDIATE"),
        ("Glute Focused", "ዳሌ ላይ ያተኮረ", "GLUTE_FOCUSED"),
        ("Advanced/Elite", "የላቀ", "ADVANCED"),
    ]
    for en, am, val in levels:
        builder.button(text=en if lang == "EN" else am, callback_data=f"level_{val}")
    builder.adjust(1)
    return builder.as_markup()

def obstacle_markup(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if lang == "EN":
        builder.button(text="🥗 Nutrition & Diet", callback_data="obs_DIET")
        builder.button(text="⏳ Consistency", callback_data="obs_CONSISTENCY")
        builder.button(text="📋 Lack of Plan", callback_data="obs_NOPLAN")
    else:
        builder.button(text="🥗 የአመጋገብ ስርዓት", callback_data="obs_DIET")
        builder.button(text="⏳ ተነሳሽነት ማጣት", callback_data="obs_CONSISTENCY")
        builder.button(text="📋 የተዋቀረ እቅድ ማጣት", callback_data="obs_NOPLAN")
    builder.adjust(1)
    return builder.as_markup()

def freq_markup(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    days = [3, 4, 5]
    for d in days:
        suffix = "Days" if lang == "EN" else "ቀናት"
        builder.button(text=f"{d} {suffix}", callback_data=f"freq_{d}")
    builder.adjust(2)
    return builder.as_markup()


# --- [ SECTION 3: PRODUCT MANAGEMENT (INLINE) ] ---

def lang_choice() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇸 EN", callback_data="set_lang_EN")
    builder.button(text="🇪🇹 AM", callback_data="set_lang_AM")
    return builder.as_markup()

def gender_choice() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Male Only", callback_data="set_gen_MALE")
    builder.button(text="Female Only", callback_data="set_gen_FEMALE")
    return builder.as_markup()

def level_choice() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for lvl in ["BEGINNER", "INTERMEDIATE", "ADVANCED"]:
        builder.button(text=lvl.capitalize(), callback_data=f"set_lvl_{lvl}")
    builder.adjust(1)
    return builder.as_markup()

def freq_choice() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for f in [3, 4, 5]:
        builder.button(text=f"{f} Training Days", callback_data=f"set_frq_{f}")
    builder.adjust(2)
    return builder.as_markup()

def cancel_admin() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Abort Operation", callback_data="admin_home")
    return builder.as_markup()


# --- [ SECTION 4: FINANCIAL AUDIT & PAGINATION ] ---

def payment_ledger_markup(payments, page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Ledger Rows
    for pay in payments:
        builder.button(
            text=f"ID:#{pay['id']} | {pay['amount']} ETB | @{pay['username'] or 'HIDDEN'}",
            callback_data=f"view_pay_{pay['id']}"
        )
    
    builder.adjust(1)
    
    # Navigation Row (Ultra-Clean Logic)
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Back", callback_data=f"paypage_{page-1}"))
    
    nav_row.append(InlineKeyboardButton(text=f"Page {page+1}/{total_pages}", callback_data="noop"))
    
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"paypage_{page+1}"))
    
    builder.row(*nav_row)
    
    # Final Action Row
    builder.row(InlineKeyboardButton(text="💎 Close Ledger", callback_data="admin_home"))
    
    return builder.as_markup()

def admin_approval_markup(payment_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve & Send PDF", callback_data=f"approve_{payment_id}")
    builder.button(text="❌ Reject", callback_data=f"reject_{payment_id}")
    builder.adjust(1)
    return builder.as_markup()

def payment_markup(lang: str, product_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    btn_text = "💳 Complete Payment" if lang == "EN" else "💳 ክፍያውን ፈጽም"
    builder.button(text=btn_text, callback_data=f"pay_{product_id}")
    return builder.as_markup()


def product_manage_list(products, page: int, total_pages: int):
    builder = InlineKeyboardBuilder()
    
    for p in products:
        status_icon = "✅" if p['is_active'] else "🚫"
        builder.button(
            text=f"{status_icon} {p['title']} ({p['language']})",
            callback_data=f"manage_view_{p['id']}"
        )
    
    builder.adjust(1)
    
    # Paging row
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"prodpage_{page-1}"))
    nav.append(InlineKeyboardButton(text=f"Page {page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"prodpage_{page+1}"))
    
    builder.row(*nav)
    builder.row(InlineKeyboardButton(text="💎 Back to Dashboard", callback_data="admin_home"))
    return builder.as_markup()

def product_detail_settings(product_id: int, is_active: bool):
    builder = InlineKeyboardBuilder()
    
    # The Toggle Button
    toggle_text = "🔴 Deactivate Product" if is_active else "🟢 Activate Product"
    builder.button(text=toggle_text, callback_data=f"toggle_prod_{product_id}")
    
    # Dangerous actions
    builder.button(text="🗑 Delete Permanently", callback_data=f"confirm_del_{product_id}")
    builder.button(text="⬅️ Back to List", callback_data="manage_refresh")
    
    builder.adjust(1)
    return builder.as_markup()