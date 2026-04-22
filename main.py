import asyncio, os, uvicorn, subprocess, psutil, datetime
import shodan
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from openai import AsyncOpenAI
from fastapi import FastAPI, Request
from serpapi import GoogleSearch
from duckduckgo_search import DDGS
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from fpdf import FPDF

# --- CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SHODAN_KEY = os.getenv("SHODAN_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
GOV_UA_KEY = os.getenv("GOV_UA_KEY") 
CHANNEL_USER = "@nexara_osint"
CHANNEL_ID = os.getenv("CHANNEL_ID")
MAIGRET_BIN = os.getenv("MAIGRET_BIN", "maigret")
PORT = int(os.getenv("PORT", 8000))

# WHITELIST - GHOST PROTECT
OWNER_DATA = [
    "ТИХОНЧУК", "ОЛЕКСАНДР", "СЕРГІЙОВИЧ", "14.09.1998", 
    "0960391586", "380960391586", "0979218708", "380979218708", "@Nexara_EN"
]

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
ai_client = AsyncOpenAI(api_key=OPENAI_KEY)
scheduler = AsyncIOScheduler()
user_usage = {}

class SearchState(StatesGroup):
    waiting_for_agreement = State()
    waiting_for_target = State()

# --- PDF ENGINE (CYBERPUNK DOSSIER) ---
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
        self.set_font('Helvetica', 'B', 16)
        self.cell(0, 10, 'NEXARA INTELLIGENCE: DOSSIER', 0, 1, 'C')
        self.ln(5)

def generate_dosse_pdf(target, report_text, filename):
    pdf = NexaraPDF()
    pdf.add_page()
    pdf.set_text_color(0, 195, 255)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, f"[1] OBJECT ID: {target}", 1, 1)
    pdf.ln(5)
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(0, 7, report_text.replace('🚀', '').replace('🛑', ''))
    pdf.set_text_color(255, 50, 50)
    pdf.set_font('Helvetica', 'B', 20)
    pdf.text(135, 45, "TOP SECRET")
    pdf.output(filename)

# --- UI ---
main_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔎 Новий пошук"), KeyboardButton(text="📊 Статистика")],
    [KeyboardButton(text="💎 VIP / Тарифи"), KeyboardButton(text="📂 Мої результати")]
], resize_keyboard=True)

agree_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Я ПРИЙМАЮ УМОВИ ТА ЗГОДУ", callback_data="agree")]
])

sub_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📢 ПІДПИСАТИСЬ НА КАНАЛ", url=f"https://t.me/{CHANNEL_USER[1:]}")],
    [InlineKeyboardButton(text="✅ ПЕРЕВІРИТИ ПІДПИСКУ", callback_data="check_sub")]
])

# --- ENGINES ---
async def total_engine(target):
    res = {"web": "", "socials": "N/A", "infra": "N/A", "gov": "N/A"}
    
    # Restored WEB Engine
    try:
        with DDGS() as ddgs:
            res["web"] = "\n".join([r.get('body', '') for r in ddgs.text(target, max_results=3)])
        if SERPAPI_KEY:
            s = GoogleSearch({"q": target, "api_key": SERPAPI_KEY, "num": 3})
            res["web"] += "\n" + "\n".join([o.get("snippet", "") for o in s.get_dict().get("organic_results", [])])
    except: pass

    # Socials Engine
    try:
        p = await asyncio.create_subprocess_exec(MAIGRET_BIN, target, "--json", "simple", stdout=asyncio.subprocess.PIPE)
        out, _ = await asyncio.wait_for(p.communicate(), timeout=50)
        res["socials"] = out.decode('utf-8', errors='ignore')
    except: pass
    
    # Infra Engine
    if SHODAN_KEY and ("." in target or target.isdigit()):
        try:
            api = shodan.Shodan(SHODAN_KEY)
            h = api.host(target)
            res["infra"] = f"Ports: {h.get('ports', [])}, OS: {h.get('os', 'N/A')}"
        except: pass
    return res

async def verify_user_sub(user_id: int) -> bool:
    try:
        chat_member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return chat_member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]
    except:
        return False

# --- HANDLERS ---
@dp.message(F.text == "/start")
async def start_cmd(m: types.Message, state: FSMContext):
    if not await verify_user_sub(m.from_user.id):
        await m.answer(f"🛑 <b>ДОСТУП ЗАБЛОКОВАНО</b>\nПідпишіться: {CHANNEL_USER}", reply_markup=sub_kb)
        return
    await state.set_state(SearchState.waiting_for_agreement)
    await m.answer("📑 <b>КОРИСТУВАЦЬКА ЗГОДА</b>\nВи підтверджуєте етичне використання даних NEXARA...", reply_markup=agree_kb)

@dp.callback_query(F.data == "check_sub")
async def handle_check_sub(call: types.CallbackQuery, state: FSMContext):
    if await verify_user_sub(call.from_user.id):
        await call.message.delete()
        await state.set_state(SearchState.waiting_for_agreement)
        await call.message.answer("📑 <b>КОРИСТУВАЦЬКА ЗГОДА</b>\nВи підтверджуєте етичне використання даних NEXARA...", reply_markup=agree_kb)
    else:
        await call.answer("❌ Ви ще не підписались на канал!", show_alert=True)

@dp.callback_query(F.data == "agree")
async def agreed(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.delete()
    await c.message.answer("<b>NEXARA ENTERPRISE V8.2 ACTIVE</b>", reply_markup=main_kb)

@dp.message(F.text == "💎 VIP / Тарифи")
async def prices(m: types.Message):
    await m.answer("<b>💎 ТАРИФИ:</b>\n\nFREE: 1 запит/доба\nVIP: $15/міс (Безліміт)\n\n@Nexara_Support")

@dp.message(F.text == "📊 Статистика")
async def stats_cmd(m: types.Message):
    await m.answer(f"📊 CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}% | Uptime: {datetime.datetime.now().strftime('%H:%M:%S')}")

@dp.message(F.text == "🔎 Новий пошук")
async def search_init(m: types.Message, state: FSMContext):
    if user_usage.get(m.from_user.id) == datetime.date.today():
        await m.answer("❌ ЛІМІТ: 1 запит на добу. Очікуйте або придбайте VIP.")
        return
    await state.set_state(SearchState.waiting_for_target)
    await m.answer("📡 Введіть ціль:")

@dp.message(SearchState.waiting_for_target)
async def process_search(m: types.Message, state: FSMContext):
    target = m.text.strip()
    if target in ["🔎 Новий пошук", "📊 Статистика", "💎 VIP / Тарифи", "📂 Мої результати"]: return

    if any(info.upper() in target.upper() for info in OWNER_DATA):
        await m.answer("⚠️ <b>ACCESS DENIED: ЗАСЕКРЕЧЕНО</b>")
        await state.clear()
        return

    user_usage[m.from_user.id] = datetime.date.today()
    await state.clear()
    st = await m.answer("🔍 <b>ГЕНЕРАЦІЯ ДОСЬЄ...</b>")
    
    data = await total_engine(target)
    gov_key_safe = GOV_UA_KEY[:10] + "..." if GOV_UA_KEY else "Not Configured"
    prompt = f"TARGET: {target}\nDATA: {data}\nGOV_DATA: {gov_key_safe}\nЗвіт по 8 пунктах. Українською."
    
    try:
        res = await ai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        report = res.choices[0].message.content
        pdf_path = f"reports/report_{m.from_user.id}.pdf"
        os.makedirs("reports", exist_ok=True)
        generate_dosse_pdf(target, report, pdf_path)
        await bot.send_document(m.chat.id, types.FSInputFile(pdf_path), caption=f"📄 Досьє: {target}\n\n{report[:500]}...")
    except Exception as e: await m.answer(f"Error: {e}")
    await st.delete()

@dp.message(F.text == "📂 Мої результати")
async def my_results(m: types.Message):
    path = f"reports/report_{m.from_user.id}.pdf"
    if os.path.exists(path):
        await bot.send_document(m.chat.id, types.FSInputFile(path))
    else: await m.answer("📭 Порожньо.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("WEBHOOK_URL"): await bot.set_webhook(os.getenv("WEBHOOK_URL"))
    yield

app = FastAPI(lifespan=lifespan)
@app.post("/webhook")
async def wh(request: Request):
    u = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, u)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
