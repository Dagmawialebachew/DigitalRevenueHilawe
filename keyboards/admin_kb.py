import types

from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_admin_map():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Stats", callback_data="admin_home")
    kb.button(text="📦 Add Product", callback_data="add_new_product")
    kb.button(text="📢 Broadcast", callback_data="broadcast_push")
    kb.adjust(1)
    return kb.as_markup()

def lang_choice():
    kb = InlineKeyboardBuilder()
    kb.button(text="🇺🇸 EN", callback_data="set_lang_EN")
    kb.button(text="🇪🇹 AM", callback_data="set_lang_AM")
    return kb.as_markup()

def gender_choice():
    kb = InlineKeyboardBuilder()
    kb.button(text="Male", callback_data="set_gen_MALE")
    kb.button(text="Female", callback_data="set_gen_FEMALE")
    return kb.as_markup()

def level_choice():
    kb = InlineKeyboardBuilder()
    for lvl in ["BEGINNER", "INTERMEDIATE", "ADVANCED", "GLUTE_FOCUSED"]:
        kb.button(text=lvl.capitalize(), callback_data=f"set_lvl_{lvl}")
    kb.adjust(2)
    return kb.as_markup()

def freq_choice():
    kb = InlineKeyboardBuilder()
    for f in [3, 4, 5]:
        kb.button(text=f"{f} Days", callback_data=f"set_frq_{f}")
    return kb.as_markup()

def cancel_admin():
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Cancel", callback_data="admin_home")
    return kb.as_markup()


def payment_ledger_markup(payments, page: int, total_pages: int):
    builder = InlineKeyboardBuilder()
    
    # One button per payment in the current page
    for pay in payments:
        builder.button(
            text=f"🎫 #{pay['id']} | {pay['amount']} ETB | {pay['username'] or 'User'}",
            callback_data=f"view_pay_{pay['id']}"
        )
    
    builder.adjust(1)
    
    # Navigation Row
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton(text="⬅️ Previous", callback_data=f"paypage_{page-1}"))
    
    nav_buttons.append(types.InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="noop"))
    
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton(text="Next ➡️", callback_data=f"paypage_{page+1}"))
    
    builder.row(*nav_buttons)
    builder.row(types.InlineKeyboardButton(text="💎 Back to Dashboard", callback_data="admin_home"))
    
    return builder.as_markup()