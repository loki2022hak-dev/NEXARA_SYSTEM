import asyncio, os, uvicorn, datetime, psutil, aiohttp
import shodan
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import CommandStart
from openai import AsyncOpenAI
from fastapi import FastAPI, Request
from serpapi import GoogleSearch
from duckduckgo_search import DDGS
from contextlib import asynccontextmanager
from fpdf import FPDF

# CONFIG
BOT_TOKEN = "8780973686:AAHskEYhW8GHMZN9SgRXDvgvcUFxGVqJAvE"
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_USER = "@nexara_osint"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
MAIGRET_BIN = os.getenv("MAIGRET_BIN", "maigret")
PORT = int(os.getenv("PORT", 8000))

# GHOST PROTECT
OWNER_DATA = ["ТИХОНЧУК", "ОЛЕКСАНДР", "СЕРГІЙОВИЧ", "14.09.1998", "0960391586", "380960391586", "0979218708", "380979218708", "@Nexara_EN"]

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
ai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
user_usage = {}

class SearchState(StatesGroup):
    waiting_for_agreement = State()
    waiting_for_target = State()

class NexaraPDF(FPDF):
    def __init__(self):
        super().__init__()
        # Використовуємо абсолютний системний шлях до шрифтів встановлених через apt-get
        font_path_regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        font_path_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        
        try:
            if os.path.exists(font_path_regular):
                self.add_font("DejaVu", "", font_path_regular)
            if os.path.exists(font_path_bold):
                self.add_font("DejaVu", "B", font_path_bold)
        except Exception as e:
            print(f"Font Load Error: {e}")

    def header(self):
        self.set_fill_color(10, 20, 35)
        self.rect(0, 0, 210, 297, 'F')
        self.set_text_color(0, 195, 255)
        self.set_font('DejaVu', 'B', 14)
        self.cell(0, 10, 'NEXARA INTELLIGENCE: OFFICIAL DOSSIER', 0, 1, 'C')

def generate_pdf(target, report, filename):
    pdf = NexaraPDF()
    pdf.add_page()
    pdf.set_text_color(0, 195, 255)
    pdf.set_font('DejaVu', '', 10)
    clean_text = str(report).encode('utf-16', 'surrogatepass').decode('utf-16').replace('🚀','').replace('🛑','')
    pdf.multi_cell(0, 7, clean_text)
    pdf.output(filename)

async def is_sub(u_id):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, u_id)
        return m.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]
    except: return False

@dp.message(CommandStart())
async def h_start(m: types.Message, state: FSMContext):
    if not await is_sub(m.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 КАНАЛ", url=f"https://t.me/{CHANNEL_USER[1:]}")], [InlineKeyboardButton(text="✅ ПЕРЕВІРИТИ", callback_data="check_sub")]])
        await m.answer(f"🛑 <b>ДОСТУП ЗАБЛОКОВАНО</b>", reply_markup=kb)
        return
    await state.set_state(SearchState.waiting_for_agreement)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Я ПРИЙМАЮ УМОВИ", callback_data="agree")]])
    await m.answer("📑 <b>КОРИСТУВАЦЬКА ЗГОДА</b>", reply_markup=kb)

@dp.callback_query(F.data == "check_sub")
async def h_check_sub(c: types.CallbackQuery, state: FSMContext):
    if await is_sub(c.from_user.id):
        await c.message.delete()
        await state.set_state(SearchState.waiting_for_agreement)
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Я ПРИЙМАЮ УМОВИ", callback_data="agree")]])
        await c.message.answer("📑 <b>КОРИСТУВАЦЬКА ЗГОДА</b>", reply_markup=kb)
    else: await c.answer("❌ Підписка не знайдена", show_alert=True)

@dp.callback_query(F.data == "agree")
async def h_agree(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.delete()
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔎 Новий пошук"), KeyboardButton(text="📊 Статистика")],[KeyboardButton(text="💎 VIP / Тарифи"), KeyboardButton(text="📂 Мої результати")]], resize_keyboard=True)
    await c.message.answer("<b>NEXARA ENTERPRISE ACTIVE</b>", reply_markup=kb)

@dp.message(F.text == "🔎 Новий пошук")
async def h_search_init(m: types.Message, state: FSMContext):
    await state.set_state(SearchState.waiting_for_target)
    await m.answer("📡 Введіть ціль:")

@dp.message(SearchState.waiting_for_target)
async def h_search(m: types.Message, state: FSMContext):
    target = m.text.strip()
    if any(x.upper() in target.upper() for x in OWNER_DATA):
        await m.answer("⚠️ <b>ЗАСЕКРЕЧЕНО</b>")
        await state.clear()
        return
    st = await m.answer("🔍 Пошук...")
    try:
        pdf_path = f"reports/report_{m.from_user.id}.pdf"
        os.makedirs("reports", exist_ok=True)
        generate_pdf(target, f"OSINT Report for {target}", pdf_path)
        await bot.send_document(m.chat.id, FSInputFile(pdf_path))
    except Exception as e: await m.answer(f"Помилка генерації: {e}")
    await st.delete()
    await state.clear()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if WEBHOOK_URL: await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "ok"}

@app.post("/webhook")
async def wh(request: Request):
    u = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, u)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
