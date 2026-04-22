import asyncio, os, uvicorn, datetime, random, psutil
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
from fpdf import FPDF

# --- CONFIG ---
BOT_TOKEN = "8780973686:AAHskEYhW8GHMZN9SgRXDvgvcUFxGVqJAvE"
CHANNEL_ID = "-1001003707514308"
CHANNEL_USER = "@nexara_osint"
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
SHODAN_KEY = os.getenv("SHODAN_API_KEY")
MAIGRET_BIN = os.getenv("MAIGRET_BIN", "maigret")
PORT = int(os.getenv("PORT", 8000))
# Авто-детекція URL: пріоритет на ENV, інакше заглушка
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# GHOST PROTECT
OWNER_DATA = ["ТИХОНЧУК", "ОЛЕКСАНДР", "СЕРГІЙОВИЧ", "14.09.1998", "0960391586", "380960391586", "0979218708", "380979218708", "@Nexara_EN"]

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
ai_client = AsyncOpenAI(api_key=OPENAI_KEY)
scheduler = AsyncIOScheduler()

class SearchState(StatesGroup):
    waiting_for_agreement = State()
    waiting_for_target = State()

# --- PDF ENGINE ---
class NexaraPDF(FPDF):
    def __init__(self):
        super().__init__()
        try:
            self.add_font("DejaVu", "", "DejaVuSans.ttf")
            self.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")
        except: pass
    def header(self):
        self.set_fill_color(10, 20, 35)
        self.rect(0, 0, 210, 297, 'F')
        self.set_text_color(0, 195, 255)
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, 'NEXARA INTELLIGENCE: DOSSIER', 0, 1, 'C')

# --- ENGINES ---
async def total_engine(target):
    res = {"socials": "N/A", "infra": "N/A"}
    try:
        p = await asyncio.create_subprocess_exec(MAIGRET_BIN, target, "--json", "simple", stdout=asyncio.subprocess.PIPE)
        out, _ = await asyncio.wait_for(p.communicate(), timeout=60)
        res["socials"] = out.decode('utf-8', errors='ignore')
    except: pass
    return res

async def is_sub(u_id):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, u_id)
        return m.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]
    except: return False

# --- CONTENT MODULE ---
async def auto_content():
    topics = ["OSINT Case", "Scam Alert", "Cyber News", "Build in Public"]
    topic = random.choice(topics)
    try:
        res = await ai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": f"Write a professional Telegram post for NEXARA channel about: {topic}. Ukrainian language."}]
        )
        await bot.send_message(CHANNEL_ID, res.choices[0].message.content)
    except: pass

# --- HANDLERS ---
@dp.message(F.text == "/start")
async def cmd_start(m: types.Message, state: FSMContext):
    if not await is_sub(m.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 ПІДПИСАТИСЬ", url=f"https://t.me/{CHANNEL_USER[1:]}")], [InlineKeyboardButton(text="✅ ПЕРЕВІРИТИ", callback_data="check")]])
        await m.answer(f"🛑 <b>ДОСТУП ОБМЕЖЕНО</b>\nПідпишіться на {CHANNEL_USER}", reply_markup=kb)
        return
    await state.set_state(SearchState.waiting_for_agreement)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ ПРИЙНЯТИ УМОВИ", callback_data="agree")]])
    await m.answer("📑 <b>КОРИСТУВАЦЬКА ЗГОДА</b>\nNEXARA V9.7 ACTIVE.", reply_markup=kb)

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
    await c.message.answer("<b>ДОСТУП НАДАНО</b>", reply_markup=kb)

@dp.message(F.text == "🔎 Новий пошук")
async def search_init(m: types.Message, state: FSMContext):
    await state.set_state(SearchState.waiting_for_target)
    await m.answer("📡 Введіть об'єкт:")

@dp.message(SearchState.waiting_for_target)
async def handle_search(m: types.Message, state: FSMContext):
    target = m.text.strip()
    if any(x.upper() in target.upper() for x in OWNER_DATA):
        await m.answer("⚠️ <b>ЗАСЕКРЕЧЕНО</b>")
        await state.clear()
        return
    st = await m.answer("🔍 <b>СКАНУВАННЯ...</b>")
    data = await total_engine(target)
    await m.answer(f"📄 <b>РЕЗУЛЬТАТ:</b>\n{str(data)[:500]}...")
    await st.delete()
    await state.clear()

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("reports", exist_ok=True)
    if WEBHOOK_URL:
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    scheduler.add_job(auto_content, 'interval', hours=6)
    scheduler.start()
    yield

app = FastAPI(lifespan=lifespan)
@app.get("/")
async def health(): return {"status": "running"}
@app.post("/webhook")
async def wh(request: Request):
    u = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, u)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
