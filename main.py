import asyncio, os, uvicorn, datetime, psutil, aiohttp
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
from serpapi import GoogleSearch
from duckduckgo_search import DDGS
from contextlib import asynccontextmanager
from fpdf import FPDF

# CONFIG
BOT_TOKEN = os.getenv("BOT_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SHODAN_KEY = os.getenv("SHODAN_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
GOV_UA_KEY = os.getenv("GOV_UA_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_USER = "@nexara_osint"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
MAIGRET_BIN = os.getenv("MAIGRET_BIN", "maigret")
PORT = int(os.getenv("PORT", 8000))

# GHOST PROTECT
OWNER_DATA = ["ТИХОНЧУК", "ОЛЕКСАНДР", "СЕРГІЙОВИЧ", "14.09.1998", "0960391586", "380960391586", "0979218708", "380979218708", "@Nexara_EN"]

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
ai_client = AsyncOpenAI(api_key=OPENAI_KEY)
user_usage = {}

class SearchState(StatesGroup):
    waiting_for_agreement = State()
    waiting_for_target = State()

# PDF CORE
class NexaraPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("DejaVu", "", "DejaVuSans.ttf")
        self.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")
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
    clean_text = report.encode('utf-16', 'surrogatepass').decode('utf-16').replace('🚀','').replace('🛑','')
    pdf.multi_cell(0, 7, clean_text)
    pdf.output(filename)

async def total_engine(target):
    res = {"web": "", "socials": "N/A", "infra": "N/A", "debt": "N/A"}
    try:
        p = await asyncio.create_subprocess_exec(MAIGRET_BIN, target, "--json", "simple", stdout=asyncio.subprocess.PIPE)
        out, _ = await asyncio.wait_for(p.communicate(), timeout=60)
        res["socials"] = out.decode('utf-8', errors='ignore')
    except: pass
    if SHODAN_KEY and ("." in target or target.replace(".","").isdigit()):
        try:
            api = shodan.Shodan(SHODAN_KEY)
            h = api.host(target)
            res["infra"] = f"Ports: {h.get('ports', [])}, OS: {h.get('os', 'N/A')}"
        except: pass
    try:
        with DDGS() as ddgs:
            res["web"] = "\n".join([r.get('body', '') for r in ddgs.text(target, max_results=5)])
    except: pass
    return res

async def is_sub(u_id):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, u_id)
        return m.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]
    except: return False

# HANDLERS
@dp.message(F.text == "/start")
async def h_start(m: types.Message, state: FSMContext):
    if not await is_sub(m.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 КАНАЛ", url=f"https://t.me/{CHANNEL_USER[1:]}")], [InlineKeyboardButton(text="✅ ПЕРЕВІРИТИ", callback_data="check_sub")]])
        await m.answer(f"🛑 <b>ДОСТУП ЗАБЛОКОВАНО</b>\nПідпишіться на {CHANNEL_USER}", reply_markup=kb)
        return
    await state.set_state(SearchState.waiting_for_agreement)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Я ПРИЙМАЮ УМОВИ", callback_data="agree")]])
    await m.answer("📑 <b>КОРИСТУВАЦЬКА ЗГОДА</b>\nВи підтверджуєте етичне використання даних NEXARA.", reply_markup=kb)

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
    if user_usage.get(m.from_user.id) == datetime.date.today():
        await m.answer("❌ ЛІМІТ: 1 запит/доба.")
        return
    await state.set_state(SearchState.waiting_for_target)
    await m.answer("📡 Введіть ціль (ПІБ/Нік/IP):")

@dp.message(SearchState.waiting_for_target)
async def h_process_search(m: types.Message, state: FSMContext):
    target = m.text.strip()
    if any(x.upper() in target.upper() for x in OWNER_DATA):
        await m.answer("⚠️ <b>ACCESS DENIED: ЗАСЕКРЕЧЕНО</b>")
        await state.clear()
        return
    user_usage[m.from_user.id] = datetime.date.today()
    await state.clear()
    st = await m.answer("🔍 <b>ГЕНЕРАЦІЯ ДОСЬЄ...</b>")
    data = await total_engine(target)
    try:
        res = await ai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": f"Target: {target}. Data: {data}. Report in 8 sections. Ukrainian."}])
        report = res.choices[0].message.content
        path = f"reports/report_{m.from_user.id}.pdf"
        os.makedirs("reports", exist_ok=True)
        generate_pdf(target, report, path)
        await bot.send_document(m.chat.id, FSInputFile(path), caption=f"📄 Звіт: {target}")
    except Exception as e: await m.answer(f"Error: {e}")
    await st.delete()

@dp.message(F.text == "📂 Мої результати")
async def h_results(m: types.Message):
    path = f"reports/report_{m.from_user.id}.pdf"
    if os.path.exists(path): await bot.send_document(m.chat.id, FSInputFile(path))
    else: await m.answer("📭 Порожньо")

@asynccontextmanager
async def lifespan(app: FastAPI):
    if WEBHOOK_URL: await bot.set_webhook(WEBHOOK_URL)
    yield

app = FastAPI(lifespan=lifespan)
@app.post("/webhook")
async def wh(request: Request):
    u = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, u)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
