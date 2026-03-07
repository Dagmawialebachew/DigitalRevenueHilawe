from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def main_menu(lang: str) -> ReplyKeyboardMarkup:
    # Use Builder for better flexibility
    builder = ReplyKeyboardBuilder()
    
    # Primary Actions
    builder.button(text="📦 My Plan" if lang == "EN" else "📦 የእኔ እቅድ")
    builder.button(text="💳 Unlock Plan" if lang == "EN" else "💳 እቅዴን ክፈት")
    
    # Secondary Actions
    builder.button(text="⚙️ Settings" if lang == "EN" else "⚙️ ማስተካከያ")
    builder.button(text="❓ Help" if lang == "EN" else "❓ እርዳታ")
    builder.button(text="ℹ️ About me" if lang == "EN" else "ℹ️ ስለ እኔ")
    
    # Standard: 2 columns per row
    builder.adjust(2)
    
    return builder.as_markup(resize_keyboard=True, input_field_placeholder="Coach Hilawe Dashboard" if lang == "EN" else "ኮች ህላዌ ዳሽቦርድ")

def cancel_payment_kb(lang: str):
    text = "❌ Cancel Payment" if lang == "EN" else "❌ ክፍያውን ሰርዝ"
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text=text))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)