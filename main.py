import asyncio, os, uvicorn, datetime, random
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

# --- CONFIG ---
BOT_TOKEN = "8780973686:AAHskEYhW8GHMZN9SgRXDvgvcUFxGVqJAvE"
CHANNEL_ID = "-1001003707514308"
RAW_URL = os.getenv("WEBHOOK_URL", "https://conservative-sheila-nexara-core-0fdc5bcb.koyeb.app")
WEBHOOK_URL = RAW_URL.rstrip('/')
PORT = int(os.getenv("PORT", 8000))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
ai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class SearchState(StatesGroup):
    waiting_for_target = State()

async def maigret_search(target):
    try:
        cmd = f"maigret {target} --json simple"
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        return stdout.decode() if stdout else "No data found."
    except Exception as e:
        return f"Maigret Error: {str(e)}"

@dp.message(F.text == "/start")
async def cmd_start(m: types.Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔎 Пошук")]], resize_keyboard=True)
    await m.answer("🚀 <b>NEXARA V12.2</b>\nMaigret Engine: ONLINE", reply_markup=kb)

@dp.message(F.text == "🔎 Пошук")
async def search_init(m: types.Message, state: FSMContext):
    await state.set_state(SearchState.waiting_for_target)
    await m.answer("📡 Введіть нікнейм:")

@dp.message(SearchState.waiting_for_target)
async def handle_search(m: types.Message, state: FSMContext):
    target = m.text.strip()
    st = await m.answer("🔍 <b>MAIGRET SCANNING...</b>")
    res = await maigret_search(target)
    await m.answer(f"📄 <b>РЕЗУЛЬТАТ:</b>\n\n<code>{res[:3500]}</code>")
    await st.delete()
    await state.clear()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    yield

app = FastAPI(lifespan=lifespan)
@app.post("/webhook")
async def wh(request: Request):
    u = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, u)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
