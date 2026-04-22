import asyncio, os, uvicorn, datetime, psutil, logging, random
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, URLInputFile
from aiogram.filters import CommandStart
from openai import AsyncOpenAI
from fastapi import FastAPI, Request
from duckduckgo_search import DDGS
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from fpdf import FPDF

logging.basicConfig(level=logging.INFO)

# --- SETTINGS ---
BOT_TOKEN = "8780973686:AAHskEYhW8GHMZN9SgRXDvgvcUFxGVqJAvE"
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
SHODAN_KEY = os.getenv("SHODAN_API_KEY")
CHANNEL_ID = "-1001003707514308"
CHANNEL_USER = "@nexara_osint"
RAW_URL = os.getenv("WEBHOOK_URL", "https://conservative-sheila-nexara-core-0fdc5bcb.koyeb.app")
WEBHOOK_URL = RAW_URL.rstrip('/')
PORT = int(os.getenv("PORT", 8000))
ADMIN_IDS = [8089452251]
OWNER_DATA = ["ТИХОНЧУК", "ОЛЕКСАНДР", "СЕРГІЙОВИЧ", "14.09.1998", "0960391586", "380960391586", "0979218708", "380979218708"]

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
ai_client = AsyncOpenAI(api_key=OPENAI_KEY)
scheduler = AsyncIOScheduler()

class SearchState(StatesGroup):
    waiting_for_target = State()

# --- PDF ENGINE ---
class NexaraPDF(FPDF):
    def __init__(self):
        super().__init__()
        f_reg = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        if os.path.exists(f_reg):
            self.add_font("DejaVu", "", f_reg)
            self.add_font("DejaVu", "B", f_reg.replace(".ttf", "-Bold.ttf"))
    def header(self):
        self.set_fill_color(10, 20, 35); self.rect(0, 0, 210, 297, 'F')
        self.set_text_color(0, 195, 255); self.set_font('DejaVu', 'B', 16)
        self.cell(0, 10, 'NEXARA INTELLIGENCE DOSSIER', 0, 1, 'C')

# --- CONTENT MODULE (5 RUBRICS) ---
async def auto_post():
    rubrics = [
        "OSINT / Розвідка: Як перевірити домен та інструменти тижня.",
        "Scam Alerts: Рубрика Шахрай дня 😈. Нові крипто-сками.",
        "Кібер новини: Що сталося, чому важливо, як захиститися.",
        "Build in Public: Нова фіча NEXARA та скріни досьє.",
        "Контент ВАУ: Risk Score приклади та що бачить OSINT про вас."
    ]
    rubric = random.choice(rubrics)
    try:
        txt = await ai_client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":f"Пост для Telegram {rubric}. Українська, емодзі."}])
        img = await ai_client.images.generate(model="dall-e-3", prompt=f"Cyberpunk high-tech visualization of {rubric}", n=1)
        await bot.send_photo(CHANNEL_ID, photo=URLInputFile(img.data[0].url), caption=txt.choices[0].message.content[:1024])
    except Exception as e: logging.error(f"Post error: {e}")

# --- HANDLERS ---
main_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔎 Новий пошук"), KeyboardButton(text="📊 Статистика")],
    [KeyboardButton(text="💎 VIP / Тарифи"), KeyboardButton(text="📂 Мої результати")]
], resize_keyboard=True)

@dp.message(CommandStart())
async def cmd_start(m: types.Message):
    await m.answer("🚀 <b>NEXARA V14.0 ONLINE</b>", reply_markup=main_kb)

@dp.message(F.text == "💎 VIP / Тарифи")
async def cmd_vip(m: types.Message):
    await m.answer("<b>💎 ТАРИФИ NEXARA:</b>\n\n🔸 LITE: $15/міс\n🔹 PRO: $45/міс\n👑 ELITE: $150/міс\n\nЗв'язок: @Nexara_EN")

@dp.message(F.text == "🔎 Новий пошук")
async def search_init(m: types.Message, state: FSMContext):
    await state.set_state(SearchState.waiting_for_target)
    await m.answer("📡 Введіть ціль (Нік/ПІБ):")

@dp.message(SearchState.waiting_for_target)
async def handle_search(m: types.Message, state: FSMContext):
    target = m.text.strip()
    if any(x.upper() in target.upper() for x in OWNER_DATA) and m.from_user.id not in ADMIN_IDS:
        await m.answer("⚠️ <b>ACCESS DENIED</b>"); await state.clear(); return
    
    st = await m.answer("🔍 <b>ГЕНЕРАЦІЯ ДОСЬЄ...</b>")
    # Maigret Fix: Виклик з базою
    proc = await asyncio.create_subprocess_exec('maigret', target, '--json', 'simple', '--top-20', stdout=asyncio.subprocess.PIPE)
    out, _ = await asyncio.wait_for(proc.communicate(), timeout=40)
    
    report = f"ЗВІТ ПО ОБ'ЄКТУ: {target}\n\nЗНАЙДЕНО: {out.decode() if out else 'Публічних даних не виявлено'}"
    pdf_p = f"reports/rep_{m.from_user.id}.pdf"; os.makedirs("reports", exist_ok=True)
    pdf = NexaraPDF(); pdf.add_page(); pdf.set_font("DejaVu", "", 10); pdf.multi_cell(0, 7, report); pdf.output(pdf_p)
    
    await bot.send_document(m.chat.id, FSInputFile(pdf_p), caption=f"📄 Досьє: {target}")
    await st.delete(); await state.clear()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook", drop_pending_updates=True)
    scheduler.add_job(auto_post, 'interval', hours=4)
    scheduler.start()
    yield

app = FastAPI(lifespan=lifespan)
@app.post("/webhook")
async def wh(r: Request):
    upd = types.Update.model_validate(await r.json(), context={"bot": bot})
    await dp.feed_update(bot, upd)
    return {"ok": True}
@app.get("/")
async def h(): return {"status": "working"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
