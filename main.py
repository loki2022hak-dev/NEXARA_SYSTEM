import asyncio, os, uvicorn, datetime, random
import shodan
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from openai import AsyncOpenAI
from fastapi import FastAPI, Request
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager

# --- CORE CONFIG ---
BOT_TOKEN = "8780973686:AAHskEYhW8GHMZN9SgRXDvgvcUFxGVqJAvE"
CHANNEL_ID = "-1001003707514308"
CHANNEL_USER = "@nexara_osint"
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") # Має бути https://domain.koyeb.app
PORT = int(os.getenv("PORT", 8000))

# GHOST PROTECT
OWNER_DATA = ["ТИХОНЧУК", "ОЛЕКСАНДР", "СЕРГІЙОВИЧ", "14.09.1998", "0960391586", "380960391586", "0979218708", "380979218708", "@Nexara_EN"]

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
ai_client = AsyncOpenAI(api_key=OPENAI_KEY)
scheduler = AsyncIOScheduler()

class SearchState(StatesGroup):
    waiting_for_agreement = State()
    waiting_for_target = State()

async def is_sub(u_id):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, u_id)
        return m.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]
    except: return False

# --- HANDLERS ---
@dp.message(F.text == "/start")
async def cmd_start(m: types.Message, state: FSMContext):
    if not await is_sub(m.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 ПІДПИСАТИСЬ", url=f"https://t.me/{CHANNEL_USER[1:]}")], [InlineKeyboardButton(text="✅ ПЕРЕВІРИТИ", callback_data="check")]])
        await m.answer(f"🛑 <b>ДОСТУП ОБМЕЖЕНО</b>\nПідпишіться на {CHANNEL_USER}", reply_markup=kb)
        return
    await state.set_state(SearchState.waiting_for_agreement)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ ПРИЙНЯТИ УМОВИ", callback_data="agree")]])
    await m.answer("📑 <b>ЗГОДА NEXARA V9.8</b>\n\nСистема готова. Ви підтверджуєте умови?", reply_markup=kb)

@dp.callback_query(F.data == "check")
async def cb_check(c: types.CallbackQuery, state: FSMContext):
    if await is_sub(c.from_user.id):
        await c.message.delete()
        await cmd_start(c.message, state)
    else: await c.answer("❌ Підписка відсутня", show_alert=True)

@dp.callback_query(F.data == "agree")
async def cb_agree(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.delete()
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔎 Новий пошук"), KeyboardButton(text="📊 Статистика")]], resize_keyboard=True)
    await c.message.answer("<b>ДОСТУП НАДАНО.</b> Очікую команду.", reply_markup=kb)

@dp.message(F.text == "🔎 Новий пошук")
async def search_init(m: types.Message, state: FSMContext):
    await state.set_state(SearchState.waiting_for_target)
    await m.answer("📡 Введіть об'єкт пошуку:")

@dp.message(SearchState.waiting_for_target)
async def handle_search(m: types.Message, state: FSMContext):
    target = m.text.strip()
    if any(x.upper() in target.upper() for x in OWNER_DATA):
        await m.answer("⚠️ <b>ЗАСЕКРЕЧЕНО: GHOST-PROTECT ACTIVE</b>")
        await state.clear()
        return
    st = await m.answer("🔍 <b>СКАНУВАННЯ ТА ГЕНЕРАЦІЯ ЗВІТУ...</b>")
    await asyncio.sleep(2) # Симуляція роботи Maigret
    await m.answer(f"✅ <b>ОБ'ЄКТ: {target}</b>\nДані завантажено у файл.")
    await st.delete()
    await state.clear()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if WEBHOOK_URL:
        # Примусовий скид вебхука для дебагу
        await bot.delete_webhook(drop_pending_updates=True)
        # Встановлення вебхука на правильний шлях
        webhook_path = f"{WEBHOOK_URL.rstrip('/')}/webhook"
        await bot.set_webhook(url=webhook_path)
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def health(): return {"status": "ok", "version": "9.8"}

@app.post("/webhook")
async def wh(request: Request):
    u = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, u)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
