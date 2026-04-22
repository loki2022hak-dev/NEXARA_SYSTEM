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
CHANNEL_USER = "@nexara_osint"
CHANNEL_ID = os.getenv("CHANNEL_ID", CHANNEL_USER)
MAIGRET_BIN = os.getenv("MAIGRET_BIN", "maigret")
PORT = int(os.getenv("PORT", 8000))

# WHITELIST - ПОВНИЙ ЗАХИСТ
OWNER_DATA = ["ТИХОНЧУК", "0960391586", "380960391586", "0979218708", "380979218708", "Nexara_EN", "14.09.1998"]

# INIT
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
ai_client = AsyncOpenAI(api_key=OPENAI_KEY)
scheduler = AsyncIOScheduler()
user_usage = {}

class SearchState(StatesGroup):
    waiting_for_agreement = State()
    waiting_for_target = State()

# --- PDF ENGINE (GHOST DOSSIER STYLE) ---
class NexaraPDF(FPDF):
    def __init__(self):
        super().__init__()
        # Додавання шрифтів з підтримкою кирилиці
        self.add_font("DejaVu", "", "DejaVuSans.ttf")
        self.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf")

    def header(self):
        self.set_fill_color(10, 20, 35) # Cyber Background
        self.rect(0, 0, 210, 297, 'F')
        self.set_text_color(0, 195, 255) # Neon Blue
        self.set_font('DejaVu', 'B', 16)
        self.cell(0, 10, 'NEXARA: OPERATIVE ANALYTICAL DOSSIER', 0, 1, 'C')
        self.ln(5)

def generate_dosse_pdf(target, report_text, filename):
    pdf = NexaraPDF()
    pdf.add_page()
    pdf.set_text_color(0, 195, 255)
    pdf.set_font('DejaVu', 'B', 12)
    pdf.cell(0, 10, f"ID OBJECT: {target}", 1, 1)
    pdf.ln(5)
    pdf.set_font('DejaVu', '', 10)
    
    # Видалення можливих емодзі, які FPDF не зможе відрендерити навіть з DejaVu
    clean_text = report_text.encode('utf-16', 'surrogatepass').decode('utf-16')
    pdf.multi_cell(0, 8, clean_text)
    
    # Штамп CONFIDENTIAL
    pdf.set_text_color(255, 50, 50)
    pdf.set_font('DejaVu', 'B', 24)
    pdf.text(130, 45, "TOP SECRET")
    pdf.output(filename)

# --- KEYBOARDS ---
agree_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Я ПРИЙМАЮ УМОВИ ТА ЗГОДУ", callback_data="agree")]
])

main_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔎 Новий пошук"), KeyboardButton(text="📊 Статистика")],
    [KeyboardButton(text="💎 VIP / Тарифи"), KeyboardButton(text="📂 Мої результати")]
], resize_keyboard=True)

sub_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📢 ПІДПИСАТИСЬ НА КАНАЛ", url=f"https://t.me/{CHANNEL_USER[1:]}")],
    [InlineKeyboardButton(text="✅ ПЕРЕВІРИТИ", callback_data="check_sub")]
])

# --- OSINT ENGINES ---
async def run_maigret(target: str, timeout: int = 60) -> str:
    try:
        process = await asyncio.create_subprocess_exec(
            MAIGRET_BIN, target, "--json", "simple",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
            return stdout.decode('utf-8', errors='ignore')
        except asyncio.TimeoutError:
            process.kill()
            return "Maigret Error: Timeout"
    except Exception as e: return f"Maigret Exec Error: {e}"

async def total_engine(target: str) -> dict:
    res = {"web": "", "socials": "N/A", "infra": "N/A"}
    try:
        with DDGS() as ddgs:
            res["web"] = "\n".join([r.get('body', '') for r in ddgs.text(target, max_results=3)])
        s = GoogleSearch({"q": target, "api_key": SERPAPI_KEY, "num": 3})
        res["web"] += "\n" + "\n".join([o.get("snippet", "") for o in s.get_dict().get("organic_results", [])])
    except: pass
    res["socials"] = await run_maigret(target)
    if SHODAN_KEY and ("." in target or target.replace(".", "").isdigit()):
        try:
            api = shodan.Shodan(SHODAN_KEY)
            h = api.host(target)
            res["infra"] = f"Ports: {h.get('ports', [])}, OS: {h.get('os', 'N/A')}"
        except: pass
    return res

# --- VENICE MEDIA (AUTO-POSTER) ---
class NexaraMediaEngine:
    @staticmethod
    async def post_to_channel():
        if not CHANNEL_ID: return
        prompt = "Напиши пост: корисний Python-код для OSINT + опис якогось APK-моду (наприклад Instagram OSINT Mod) + багато емодзі + анімаційний стиль. Мова: Українська."
        try:
            res = await ai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": "Ти - Senior OSINT Architect Nexara. Пишеш для професіоналів."}, {"role": "user", "content": prompt}]
            )
            await bot.send_message(CHANNEL_ID, f"📡 <b>NEXARA SYSTEM UPDATE</b>\n\n{res.choices[0].message.content}\n\n🤖 @Nexara_Systems_Bot")
        except: pass

# --- HANDLERS ---
async def check_sub(user_id):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]
    except: return False

@dp.message(F.text == "/start")
async def start_cmd(m: types.Message, state: FSMContext):
    if not await check_sub(m.from_user.id):
        await m.answer(f"🛑 <b>ДОСТУП ЗАБЛОКОВАНО</b>\nПідпишіться: {CHANNEL_USER}", reply_markup=sub_kb)
        return
    await state.set_state(SearchState.waiting_for_agreement)
    await m.answer("📑 <b>КОРИСТУВАЦЬКА ЗГОДА</b>\n\nВи підтверджуєте використання NEXARA виключно в законних цілях. Ви берете повну відповідальність за отримані дані.", reply_markup=agree_kb)

@dp.callback_query(F.data == "check_sub")
async def check_sub_handler(call: types.CallbackQuery, state: FSMContext):
    if await check_sub(call.from_user.id):
        await call.message.delete()
        await state.set_state(SearchState.waiting_for_agreement)
        await call.message.answer("📑 <b>КОРИСТУВАЦЬКА ЗГОДА</b>\n\nВи підтверджуєте використання NEXARA виключно в законних цілях. Ви берете повну відповідальність за отримані дані.", reply_markup=agree_kb)
    else:
        await call.answer("❌ Ви ще не підписались на канал!", show_alert=True)

@dp.callback_query(F.data == "agree")
async def agreed(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.delete()
    await c.message.answer("<b>NEXARA ENTERPRISE V7.1 АКТИВНА</b>", reply_markup=main_kb)

@dp.message(F.text == "💎 VIP / Тарифи")
async def prices(m: types.Message):
    await m.answer("<b>💎 ТАРИФИ:</b>\n\nFREE: 1 запит/доба\nVIP: $15/міс (Безліміт)\n\n@Nexara_Support")

@dp.message(F.text == "📊 Статистика")
async def stats_cmd(m: types.Message):
    await m.answer(f"📊 CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}% | Uptime: {datetime.datetime.now().strftime('%H:%M:%S')}")

@dp.message(F.text == "🔎 Новий пошук")
async def search_init(m: types.Message, state: FSMContext):
    u_id = m.from_user.id
    today = datetime.date.today()
    u_data = user_usage.get(u_id, {"last": None, "vip": False})
    if not u_data["vip"] and u_data["last"] == today:
        await m.answer("❌ <b>ЛІМІТ ВИЧЕРПАНО.</b> 1 запит на добу.\nКупіть VIP для безліміту.")
        return
    await state.set_state(SearchState.waiting_for_target)
    await m.answer("📡 Введіть ціль (Нікнейм/IP/Email/ПІБ):")

@dp.message(SearchState.waiting_for_target)
async def process_search(m: types.Message, state: FSMContext):
    target = m.text.strip()
    if target in ["🔎 Новий пошук", "📊 Статистика", "💎 VIP / Тарифи", "📂 Мої результати"]: return
    
    if any(info.upper() in target.upper() for info in OWNER_DATA):
        await m.answer("⚠️ <b>ACCESS DENIED: RESTRICTED DATA</b>\nДані об'єкта захищені протоколом NEXARA-GHOST. Пошук неможливий.")
        await state.clear()
        return

    user_usage[m.from_user.id] = {"last": datetime.date.today(), "vip": False}
    await state.clear()
    
    st = await m.answer("🔍 <b>ГЕНЕРАЦІЯ ДОСЬЄ...</b>")
    data = await total_engine(target)
    
    prompt = f"TARGET: {target}\nCONTEXT: {data}\nСклади звіт по 8 пунктах (Ідентифікація, Зв'язки, Гео, Фінанси тощо). Українською."
    try:
        res = await ai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        full_report = res.choices[0].message.content
        
        # PDF Gen
        pdf_path = f"reports/report_{m.from_user.id}.pdf"
        os.makedirs("reports", exist_ok=True)
        generate_dosse_pdf(target, full_report, pdf_path)
        
        await bot.send_document(m.chat.id, types.FSInputFile(pdf_path), caption=f"🛑 <b>ЗВІТ: {target}</b>\n\n{full_report[:800]}...")
    except Exception as e: await st.edit_text(f"❌ Помилка: {e}")
    await st.delete()

@dp.message(F.text == "📂 Мої результати")
async def results(m: types.Message):
    pdf_path = f"reports/report_{m.from_user.id}.pdf"
    if os.path.exists(pdf_path):
        await bot.send_document(m.chat.id, types.FSInputFile(pdf_path), caption="📂 Останній збережений результат.")
    else:
        await m.answer("📭 У вас ще немає збережених результатів.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("WEBHOOK_URL"): await bot.set_webhook(os.getenv("WEBHOOK_URL"))
    scheduler.add_job(NexaraMediaEngine.post_to_channel, "interval", hours=24)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
@app.post("/webhook")
async def wh(request: Request):
    u = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, u)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
