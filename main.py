import asyncio, os, uvicorn, datetime, psutil, logging
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
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from fpdf import FPDF

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8780973686:AAHskEYhW8GHMZN9SgRXDvgvcUFxGVqJAvE")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SHODAN_KEY = os.getenv("SHODAN_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
GOV_UA_KEY = os.getenv("GOV_UA_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "-1002220197777")
CHANNEL_USER = "@nexara_osint"
MAIGRET_BIN = "/usr/local/bin/maigret"
PORT = int(os.getenv("PORT", 8000))

# ROOT CAUSE FIX: Додано ID власника для безумовного обходу блокувань
ADMIN_IDS = [8089452251]

OWNER_DATA = ["ТИХОНЧУК", "ОЛЕКСАНДР", "СЕРГІЙОВИЧ", "14.09.1998", "0960391586", "380960391586", "0979218708", "380979218708", "@Nexara_EN"]

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
ai_client = AsyncOpenAI(api_key=OPENAI_KEY)
scheduler = AsyncIOScheduler()
user_usage = {}

class SearchState(StatesGroup):
    waiting_for_agreement = State()
    waiting_for_target = State()

class NexaraPDF(FPDF):
    def __init__(self):
        super().__init__()
        font_regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        font_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        try:
            if os.path.exists(font_regular):
                self.add_font("DejaVu", "", font_regular)
            if os.path.exists(font_bold):
                self.add_font("DejaVu", "B", font_bold)
        except Exception as e:
            logging.error(f"Font Error: {e}")

    def header(self):
        self.set_fill_color(10, 20, 35)
        self.rect(0, 0, 210, 297, 'F')
        self.set_text_color(0, 195, 255)
        self.set_font('DejaVu', 'B', 16)
        self.cell(0, 10, 'NEXARA INTELLIGENCE: DOSSIER', 0, 1, 'C')
        self.ln(5)

def generate_dosse_pdf(target, report, filename):
    pdf = NexaraPDF()
    pdf.add_page()
    pdf.set_text_color(0, 195, 255)
    pdf.set_font('DejaVu', 'B', 12)
    pdf.cell(0, 10, f"[1] ДАНІ ОБ'ЄКТА: {target}", 1, 1)
    pdf.ln(5)
    pdf.set_font('DejaVu', '', 10)
    clean_report = str(report).encode('utf-16', 'surrogatepass').decode('utf-16').replace('🚀','').replace('🛑','')
    pdf.multi_cell(0, 7, clean_report)
    pdf.set_text_color(255, 50, 50)
    pdf.set_font('DejaVu', 'B', 20)
    pdf.text(130, 45, "TOP SECRET")
    pdf.output(filename)

main_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔎 Новий пошук"), KeyboardButton(text="📊 Статистика")],
    [KeyboardButton(text="💎 VIP / Тарифи"), KeyboardButton(text="📂 Мої результати")]
], resize_keyboard=True)

agree_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Я ПРИЙМАЮ УМОВИ ТА ЗГОДУ", callback_data="agree")]])
sub_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📢 ПІДПИСАТИСЬ", url=f"https://t.me/{CHANNEL_USER[1:]}")],
    [InlineKeyboardButton(text="✅ ПЕРЕВІРИТИ", callback_data="check_sub")]
])

async def total_engine(target):
    res = {"web": "", "socials": "N/A", "infra": "N/A"}
    try:
        with DDGS() as ddgs:
            res["web"] = "\n".join([r.get('body', '') for r in ddgs.text(target, max_results=3)])
        if SERPAPI_KEY:
            s = GoogleSearch({"q": target, "api_key": SERPAPI_KEY, "num": 3})
            res["web"] += "\n" + "\n".join([o.get("snippet", "") for o in s.get_dict().get("organic_results", [])])
    except Exception as e:
        logging.error(f"Web Search Error: {e}")

    try:
        cmd = f"maigret {target} --json simple"
        p = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await asyncio.wait_for(p.communicate(), timeout=50)
        if out:
            res["socials"] = out.decode('utf-8', errors='ignore')
    except Exception as e:
        logging.error(f"Maigret Error: {e}")
    
    if SHODAN_KEY and ("." in target or target.isdigit()):
        try:
            api = shodan.Shodan(SHODAN_KEY)
            h = api.host(target)
            res["infra"] = f"Ports: {h.get('ports', [])}, OS: {h.get('os', 'N/A')}"
        except Exception as e:
            logging.error(f"Shodan Error: {e}")
            
    return res

async def check_sub(u_id):
    if u_id in ADMIN_IDS:
        return True
    try:
        m = await bot.get_chat_member(CHANNEL_ID, u_id)
        return m.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]
    except Exception as e: 
        logging.warning(f"Sub check failed for {u_id}: {e}")
        return False

@dp.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    if not await check_sub(m.from_user.id):
        await m.answer(f"🛑 <b>ДОСТУП ЗАБЛОКОВАНО</b>\nПідпишіться на {CHANNEL_USER}", reply_markup=sub_kb)
        return
    await state.set_state(SearchState.waiting_for_agreement)
    await m.answer("📑 <b>КОРИСТУВАЦЬКА ЗГОДА</b>\nВи підтверджуєте етичне використання даних...", reply_markup=agree_kb)

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(c: types.CallbackQuery, state: FSMContext):
    if await check_sub(c.from_user.id):
        await c.message.delete()
        await state.set_state(SearchState.waiting_for_agreement)
        await c.message.answer("📑 <b>КОРИСТУВАЦЬКА ЗГОДА</b>", reply_markup=agree_kb)
    else: 
        await c.answer("❌ Немає підписки", show_alert=True)

@dp.callback_query(F.data == "agree")
async def cb_agree(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.delete()
    await c.message.answer("<b>NEXARA ENTERPRISE V12.3 ACTIVE</b>", reply_markup=main_kb)

@dp.message(F.text == "📊 Статистика")
async def stats_cmd(m: types.Message):
    await m.answer(f"📊 CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}% | Uptime: {datetime.datetime.now().strftime('%H:%M:%S')}")

@dp.message(F.text == "💎 VIP / Тарифи")
async def prices_cmd(m: types.Message):
    await m.answer("<b>💎 ТАРИФИ:</b>\n\nFREE: 1 запит/доба\nVIP: $15/міс (Безліміт)\n\n@Nexara_Support")

@dp.message(F.text == "🔎 Новий пошук")
async def search_init(m: types.Message, state: FSMContext):
    if user_usage.get(m.from_user.id) == datetime.date.today() and m.from_user.id not in ADMIN_IDS:
        await m.answer("❌ ЛІМІТ: 1 запит/доба.")
        return
    await state.set_state(SearchState.waiting_for_target)
    await m.answer("📡 Введіть ціль:")

@dp.message(SearchState.waiting_for_target)
async def handle_search(m: types.Message, state: FSMContext):
    target = m.text.strip()
    if target in ["🔎 Новий пошук", "📊 Статистика", "💎 VIP / Тарифи", "📂 Мої результати"]: 
        return
    
    if any(x.upper() in target.upper() for x in OWNER_DATA):
        await m.answer("⚠️ <b>ACCESS DENIED: ЗАСЕКРЕЧЕНО</b>")
        await state.clear()
        return
    
    user_usage[m.from_user.id] = datetime.date.today()
    await state.clear()
    st = await m.answer("🔍 <b>ЗБІР ДАНИХ ТА ГЕНЕРАЦІЯ ДОСЬЄ...</b>")
    
    data = await total_engine(target)
    gov_key_safe = GOV_UA_KEY[:10] + "..." if GOV_UA_KEY else "Not Configured"
    prompt = f"TARGET: {target}\nDATA: {data}\nGOV_DATA: {gov_key_safe}\nЗвіт по 8 пунктах. Українською. Тільки факти."
    
    try:
        res = await ai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        report = res.choices[0].message.content
        pdf_path = f"reports/report_{m.from_user.id}.pdf"
        os.makedirs("reports", exist_ok=True)
        generate_dosse_pdf(target, report, pdf_path)
        await bot.send_document(m.chat.id, FSInputFile(pdf_path), caption=f"📄 Досьє: {target}")
    except Exception as e: 
        logging.error(f"Gen Error: {e}")
        await m.answer(f"❌ Error: {e}")
    await st.delete()

@dp.message(F.text == "📂 Мої результати")
async def my_results(m: types.Message):
    path = f"reports/report_{m.from_user.id}.pdf"
    if os.path.exists(path): 
        await bot.send_document(m.chat.id, FSInputFile(path))
    else: 
        await m.answer("📭 Порожньо")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Примусове знищення вебхука і перехід на Polling для 100% стабільності в Koyeb
    await bot.delete_webhook(drop_pending_updates=True)
    polling_task = asyncio.create_task(dp.start_polling(bot))
    scheduler.start()
    yield
    polling_task.cancel()
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "Nexara V12.3 Active"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
