from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from app.core.config import CHANNEL_USER

main_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔎 Новий пошук"), KeyboardButton(text="📂 Мої звіти")],
    [KeyboardButton(text="📊 Risk Score"), KeyboardButton(text="🛡 AntiScam")],
    [KeyboardButton(text="💎 VIP"), KeyboardButton(text="⚙ Профіль")]
], resize_keyboard=True)

sub_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📢 ПІДПИСАТИСЬ", url=f"https://t.me/{CHANNEL_USER[1:]}")],
    [InlineKeyboardButton(text="✅ ПЕРЕВІРИТИ", callback_data="check_sub")]
])
