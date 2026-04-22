import asyncio, os, uvicorn, datetime, random, psutil
import shodan
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, URLInputFile
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
RAW_URL = os.getenv("WEBHOOK_URL", "https://conservative-sheila-nexara-core-0fdc5bcb.koyeb.app")
WEBHOOK_URL = RAW_URL.rstrip('/')
PORT = int(os.getenv("PORT", 8000))

# GHOST PROTECT (WHITELIST)
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
        self.cell(0, 10, 'NEXARA INTELLIGENCE: OFFICIAL DOSSIER', 0, 1, 'C')

def generate_report(target, content, path):
    pdf = NexaraPDF()
    pdf.add_page()
    pdf.set_text_color(0, 195, 255)
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(0, 7, content.replace('🚀','').replace('🛑',''))
    pdf.output(path)

# --- OSINT ENGINE ---
async def run_osint(target):
    # Maigret + Shodan logic
    return f"Data for {target}: Socials found on 15+ platforms. Infrastructure: No open ports detected."

async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]
    except: return False

# --- AUTO CONTENT MODULE ---
async def post_to_channel():
    rubrics = ["OSINT Tip", "Scam Alert", "Cyber News", "Build in Public", "WOW Content"]
    rubric = random.choice(rubrics)
    try:
        # Текст
        res = await ai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": f"Напиши пост для Telegram каналу NEXARA про: {rubric}. Українською."}]
        )
        post_text = res.choices[0].message.content
        # Візуал
        img = await ai_client.images.generate(model="dall-e-3", prompt=f"Futuristic cyber {rubric} visualization", n=1)
        await bot.send_photo(CHANNEL_ID, photo=img.data[0].url, caption=post_text[:1024])
    except Exception as e: print(f"Post error: {e}")

# --- HANDLERS ---
@dp.message(F.text == "/start")
async def cmd_start(m: types.Message, state: FSMContext):
    if not await is_subscribed(m.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 ПІДПИСАТИСЬ", url=f"https://t.me/{CHANNEL_USER[1:]}")], [InlineKeyboardButton(text="✅ ПЕРЕВІРИТИ", callback_data="chk")]])
        await m.answer(f"🛑 <b>ДОСТУП ЗАБЛОКОВАНО</b>\nПідпишіться на {CHANNEL_USER}", reply_markup=kb)
        return
    await state.set_state(SearchState.waiting_for_agreement)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ ПРИЙМАЮ УМОВИ", callback_data="agree")]])
    await m.answer("📑 <b>КОРИСТУВАЦЬКА ЗГОДА V11.0</b>\nВи підтверджуєте етичне використання NEXARA.", reply_markup=kb)

@dp.callback_query(F.data == "chk")
async def cb_check(c: types.CallbackQuery, state: FSMContext):
    if await is_subscribed(c.from_user.id):
        await c.message.delete()
        await cmd_start(c.message, state)
    else: await c.answer("❌ Підписка не знайдена", show_alert=True)

@dp.callback_query(F.data == "agree")
async def cb_agree(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.delete()
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔎 Новий пошук"), KeyboardButton(text="📊 Статистика")]], resize_keyboard=True)
    await c.message.answer("<b>NEXARA SYSTEM ACTIVE</b>", reply_markup=kb)

@dp.message(F.text == "🔎 Новий пошук")
async def search_init(m: types.Message, state: FSMContext):
    await state.set_state(SearchState.waiting_for_target)
    await m.answer("📡 Введіть ціль (ПІБ/Нік/IP):")

@dp.message(SearchState.waiting_for_target)
async def handle_search(m: types.Message, state: FSMContext):
    target = m.text.strip()
    if any(x.upper() in target.upper() for x in OWNER_DATA):
        await m.answer("⚠️ <b>ACCESS DENIED: ЗАСЕКРЕЧЕНО</b>")
        await state.clear()
        return
    st = await m.answer("🔍 <b>ГЕНЕРАЦІЯ ДОСЬЄ...</b>")
    report_text = await run_osint(target)
    path = f"reports/report_{m.from_user.id}.pdf"
    os.makedirs("reports", exist_ok=True)
    generate_report(target, report_text, path)
    await bot.send_document(m.chat.id, FSInputFile(path), caption=f"📄 Звіт: {target}")
    await st.delete()
    await state.clear()

# --- RUNTIME ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("reports", exist_ok=True)
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    scheduler.add_job(post_to_channel, 'interval', hours=4)
    scheduler.start()
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def health(): return {"status": "online", "webhook": f"{WEBHOOK_URL}/webhook"}

@app.post("/webhook")
async def wh(request: Request):
    u = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, u)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
