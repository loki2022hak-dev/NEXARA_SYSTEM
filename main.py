import asyncio, os, uvicorn, datetime, psutil, logging, random
import shodan
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

# CONFIG
BOT_TOKEN = os.getenv("BOT_TOKEN", "8780973686:AAHskEYhW8GHMZN9SgRXDvgvcUFxGVqJAvE")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
SHODAN_KEY = os.getenv("SHODAN_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "-1001003707514308")
CHANNEL_USER = "@nexara_osint"
PORT = int(os.getenv("PORT", 8000))
ADMIN_IDS = [8089452251]

# GHOST PROTECT
OWNER_DATA = ["ТИХОНЧУК", "ОЛЕКСАНДР", "СЕРГІЙОВИЧ", "14.09.1998", "0960391586", "380960391586", "0979218708", "380979218708", "@Nexara_EN"]

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
ai_client = AsyncOpenAI(api_key=OPENAI_KEY)
scheduler = AsyncIOScheduler()
user_usage = {}

class SearchState(StatesGroup):
    waiting_for_agreement = State()
    waiting_for_target = State()

# --- PDF GENERATOR ---
class NexaraPDF(FPDF):
    def __init__(self):
        super().__init__()
        font_p = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        if os.path.exists(font_p):
            self.add_font("DejaVu", "", font_p)
            self.add_font("DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    def header(self):
        self.set_fill_color(10, 20, 35)
        self.rect(0, 0, 210, 297, 'F')
        self.set_text_color(0, 195, 255)
        self.set_font('DejaVu', 'B', 16)
        self.cell(0, 10, 'NEXARA INTELLIGENCE REPORT', 0, 1, 'C')

def make_pdf(target, report, path):
    pdf = NexaraPDF()
    pdf.add_page()
    pdf.set_text_color(0, 195, 255)
    pdf.set_font('DejaVu', '', 10)
    pdf.multi_cell(0, 7, report.replace('🚀',''))
    pdf.output(path)

# --- KEYBOARDS ---
main_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔎 Новий пошук"), KeyboardButton(text="📊 Статистика")],
    [KeyboardButton(text="💎 VIP / Тарифи"), KeyboardButton(text="📂 Мої результати")]
], resize_keyboard=True)

# --- AUTO-POSTING SYSTEM ---
async def auto_poster():
    rubrics = [
        "OSINT / Розвідка (чеклісти, кейси)",
        "Scam Alerts (Шахрай дня 😈, крипто-сками)",
        "Кібер/злом новини (що сталося, як захиститися)",
        "Build in Public (NEXARA: нові фічі, скріни досьє)",
        "Контент ВАУ (графіки, risk score, що бачить OSINT про вас)"
    ]
    rubric = random.choice(rubrics)
    try:
        # Generate Text
        res = await ai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": f"Напиши пост для Telegram каналу на тему {rubric}. Українською. Формат: Заголовок, Суть, Порада. Додай емодзі."}]
        )
        post_text = res.choices[0].message.content
        
        # Generate Image
        img_gen = await ai_client.images.generate(
            model="dall-e-3",
            prompt=f"Cyberpunk futuristic OSINT interface, high-tech, digital intelligence theme, relating to: {rubric}",
            n=1
        )
        await bot.send_photo(CHANNEL_ID, photo=URLInputFile(img_gen.data[0].url), caption=post_text[:1024])
    except Exception as e:
        logging.error(f"Auto-poster failed: {e}")

# --- HANDLERS ---
@dp.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    await state.set_state(SearchState.waiting_for_agreement)
    await m.answer("📑 <b>ЗГОДА NEXARA V13</b>\n\nЯ підтверджую, що не буду використовувати систему в незаконних цілях.", 
                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ ПРИЙМАЮ", callback_data="agree")]]))

@dp.callback_query(F.data == "agree")
async def cb_agree(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.delete()
    await c.message.answer("<b>NEXARA ENTERPRISE ACTIVE</b>", reply_markup=main_kb)

@dp.message(F.text == "📊 Статистика")
async def stats_cmd(m: types.Message):
    await m.answer(f"📈 CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}% | Status: Healthy")

@dp.message(F.text == "💎 VIP / Тарифи")
async def prices_cmd(m: types.Message):
    price_text = (
        "<b>💎 ТАРИФИ NEXARA OSINT:</b>\n\n"
        "🔸 <b>BASIC (FREE):</b> 1 запит/доба, Maigret Simple.\n"
        "🔹 <b>PREMIUM ($15/міс):</b> Безліміт, Глибокий Maigret, пріоритет.\n"
        "👑 <b>ENTERPRISE ($50/міс):</b> Shodan, DarkWeb-Leaks, PDF-звіти.\n\n"
        "💳 <b>Оплата:</b> @Nexara_EN"
    )
    await m.answer(price_text)

@dp.message(F.text == "🔎 Новий пошук")
async def search_init(m: types.Message, state: FSMContext):
    if user_usage.get(m.from_user.id) == datetime.date.today() and m.from_user.id not in ADMIN_IDS:
        await m.answer("❌ Ліміт FREE вичерпано. Чекайте завтра або купіть VIP.")
        return
    await state.set_state(SearchState.waiting_for_target)
    await m.answer("📡 Введіть ціль (Нікнейм, ПІБ або IP):")

@dp.message(SearchState.waiting_for_target)
async def handle_search(m: types.Message, state: FSMContext):
    target = m.text.strip()
    if any(x.upper() in target.upper() for x in OWNER_DATA):
        await m.answer("⚠️ <b>ACCESS DENIED: GHOST-PROTECT</b>")
        await state.clear()
        return
    
    st_msg = await m.answer("🔍 <b>ЗБІР ДАНИХ (MAIGRET + SHODAN + WEB)...</b>")
    
    # OSINT Logic
    web_res = ""
    with DDGS() as ddgs:
        web_res = "\n".join([r['body'] for r in ddgs.text(target, max_results=3)])
    
    maigret_out = "No data."
    try:
        proc = await asyncio.create_subprocess_exec('maigret', target, '--json', 'simple', '--top-100', 
                                                   stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=40)
        maigret_out = out.decode() if out else "Nothing found."
    except: maigret_out = "Search timeout."

    report_prompt = f"Target: {target}\nWeb: {web_res}\nSocials: {maigret_out}\nЗвіт 8 розділів. Українською."
    res = await ai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": report_prompt}])
    report = res.choices[0].message.content
    
    pdf_p = f"reports/rep_{m.from_user.id}.pdf"
    os.makedirs("reports", exist_ok=True)
    make_pdf(target, report, pdf_p)
    
    await bot.send_document(m.chat.id, FSInputFile(pdf_p), caption=f"📄 Звіт: {target}")
    await st_msg.delete()
    user_usage[m.from_user.id] = datetime.date.today()
    await state.clear()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(dp.start_polling(bot))
    scheduler.add_job(auto_poster, 'interval', hours=4)
    scheduler.start()
    yield

app = FastAPI(lifespan=lifespan)
@app.get("/")
async def root(): return {"status": "V13_STABLE"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
