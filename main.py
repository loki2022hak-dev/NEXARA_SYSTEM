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
from serpapi import GoogleSearch
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from fpdf import FPDF

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8780973686:AAHskEYhW8GHMZN9SgRXDvgvcUFxGVqJAvE")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
SHODAN_KEY = os.getenv("SHODAN_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "-1002220197777")
CHANNEL_USER = "@nexara_osint"
PORT = int(os.getenv("PORT", 8000))
MAIGRET_BIN = "/usr/local/bin/maigret"
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

# --- PDF ENGINE ---
class NexaraPDF(FPDF):
    def __init__(self):
        super().__init__()
        font_reg = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        font_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        try:
            if os.path.exists(font_reg):
                self.add_font("DejaVu", "", font_reg)
                self.add_font("DejaVu", "B", font_bold)
        except Exception as e:
            logging.error(f"Font Error: {e}")

    def header(self):
        self.set_fill_color(10, 20, 35)
        self.rect(0, 0, 210, 297, 'F')
        self.set_text_color(0, 195, 255)
        self.set_font('DejaVu', 'B', 16)
        self.cell(0, 10, 'NEXARA INTELLIGENCE DOSSIER', 0, 1, 'C')
        self.ln(5)

def make_pdf(target, report, path):
    pdf = NexaraPDF()
    pdf.add_page()
    pdf.set_text_color(0, 195, 255)
    pdf.set_font('DejaVu', 'B', 12)
    pdf.cell(0, 10, f"[ID] ОБ'ЄКТ: {target}", 1, 1)
    pdf.ln(5)
    pdf.set_font('DejaVu', '', 10)
    clean_text = str(report).encode('utf-16', 'surrogatepass').decode('utf-16').replace('🚀','').replace('🛑','')
    pdf.multi_cell(0, 7, clean_text)
    pdf.set_text_color(255, 50, 50)
    pdf.set_font('DejaVu', 'B', 20)
    pdf.text(130, 45, "TOP SECRET")
    pdf.output(path)

# --- AUTO-POSTING (5 RUBRICS + DALL-E) ---
async def auto_post():
    rubrics = [
        {"theme": "OSINT / Розвідка", "desc": "Формат: 'OSINT Tip дня', 'Threat розбір' або '1 інструмент = 1 пост'. Теми: як перевірити домен, OSINT кейси, інструменти тижня, чеклісти, mini investigations."},
        {"theme": "Scam Alerts", "desc": "Рубрика: 'Шахрай дня 😈'. Теми: нові шахрайські схеми, фейкові сайти, крипто-сками, telegram fraud, розбір шахрая."},
        {"theme": "Кібер/злом новини", "desc": "Розбір: що сталося, чому важливо, як захиститися."},
        {"theme": "Build in Public", "desc": "Показуй як росте NEXARA: новий модуль, нова фіча, скріни досьє, demo intelligence reports."},
        {"theme": "Контент ВАУ", "desc": "красиві досьє скріни, risk score приклади, graph visualizations, що бачить OSINT про вас."}
    ]
    selected = random.choice(rubrics)
    
    try:
        text_prompt = f"Напиши унікальний, професійний і цікавий пост для Telegram каналу NEXARA. Рубрика: {selected['theme']}. Суть: {selected['desc']}. Мова: українська. Використовуй абзаци та емодзі. Максимум 900 символів."
        res_text = await ai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": text_prompt}])
        post_text = res_text.choices[0].message.content
        
        img_prompt = f"High quality cinematic hacker or cyberpunk aesthetic visualization, tech intelligence, relating to: {selected['theme']}, no text, dark mode."
        img_gen = await ai_client.images.generate(model="dall-e-3", prompt=img_prompt, n=1, size="1024x1024")
        image_url = img_gen.data[0].url
        
        await bot.send_photo(CHANNEL_ID, photo=URLInputFile(image_url), caption=f"{post_text}\n\n🤖 <b>@Nexara_Systems_Bot</b>")
    except Exception as e:
        logging.error(f"Auto-post error: {e}")

# --- ASYNC FAST OSINT ---
def sync_ddg(target):
    try:
        with DDGS() as ddgs:
            return "\n".join([r.get('body', '') for r in ddgs.text(target, max_results=3)])
    except: return ""

def sync_serp(target):
    if not SERPAPI_KEY: return ""
    try:
        s = GoogleSearch({"q": target, "api_key": SERPAPI_KEY, "num": 3})
        return "\n".join([o.get("snippet", "") for o in s.get_dict().get("organic_results", [])])
    except: return ""

def sync_shodan(target):
    if not SHODAN_KEY or not ("." in target or target.isdigit()): return "N/A"
    try:
        api = shodan.Shodan(SHODAN_KEY)
        h = api.host(target)
        return f"Ports: {h.get('ports', [])}, OS: {h.get('os', 'N/A')}, Vulns: {h.get('vulns', [])}"
    except: return "N/A"

async def fast_engine(target):
    # Зменшуємо timeout і кількість сайтів для Maigret щоб не висіло довго
    m_cmd = f"{MAIGRET_BIN} {target} --json simple --top-30 --timeout 15"
    
    t_ddg = asyncio.to_thread(sync_ddg, target)
    t_serp = asyncio.to_thread(sync_serp, target)
    t_shodan = asyncio.to_thread(sync_shodan, target)
    
    maigret_res = "N/A"
    try:
        proc = await asyncio.create_subprocess_shell(m_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=35)
        if out: maigret_res = out.decode('utf-8', errors='ignore')
    except asyncio.TimeoutError:
        proc.kill()
        maigret_res = "[TIMEOUT] Соціальні мережі проаналізовано частково."
    except: pass

    r_ddg, r_serp, r_shodan = await asyncio.gather(t_ddg, t_serp, t_shodan)
    
    return f"WEB:\n{r_ddg}\n{r_serp}\n\nINFRA:\n{r_shodan}\n\nSOCIALS:\n{maigret_res}"

# --- HANDLERS ---
async def is_sub(u_id):
    if u_id in ADMIN_IDS: return True
    try:
        m = await bot.get_chat_member(CHANNEL_ID, u_id)
        return m.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]
    except: return False

main_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔎 Новий пошук"), KeyboardButton(text="📊 Статистика")],
    [KeyboardButton(text="💎 VIP / Тарифи"), KeyboardButton(text="📂 Мої результати")]
], resize_keyboard=True)

@dp.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    if not await is_sub(m.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 ПІДПИСАТИСЬ", url=f"https://t.me/{CHANNEL_USER[1:]}")],
            [InlineKeyboardButton(text="✅ ПЕРЕВІРИТИ", callback_data="check_sub")]
        ])
        await m.answer(f"🛑 <b>ДОСТУП ЗАБЛОКОВАНО</b>\nПідпишіться на канал NEXARA.", reply_markup=kb)
        return
    await state.set_state(SearchState.waiting_for_agreement)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Я ПРИЙМАЮ УМОВИ", callback_data="agree")]])
    await m.answer("📑 <b>ЗГОДА NEXARA V14</b>\n\nЯ підтверджую етичне використання даних.", reply_markup=kb)

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(c: types.CallbackQuery, state: FSMContext):
    if await is_sub(c.from_user.id):
        await c.message.delete()
        await state.set_state(SearchState.waiting_for_agreement)
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Я ПРИЙМАЮ УМОВИ", callback_data="agree")]])
        await c.message.answer("📑 <b>ЗГОДА NEXARA V14</b>", reply_markup=kb)
    else: 
        await c.answer("❌ Підписка не знайдена", show_alert=True)

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
        "🟢 <b>GUEST (FREE):</b> 1 запит/доба.\n"
        "🟡 <b>LITE ($15/міс):</b> 50 запитів/доба, PDF-звіти.\n"
        "🔵 <b>PRO ($45/міс):</b> Безліміт, Глибокий Maigret (Top-1000), пріоритет у черзі.\n"
        "🔴 <b>ELITE ($150/міс):</b> Shodan, DarkWeb-Leaks, API доступ, Custom OSINT.\n\n"
        "💳 <b>Оплата/Питання:</b> @Nexara_EN"
    )
    await m.answer(price_text)

@dp.message(F.text == "🔎 Новий пошук")
async def search_init(m: types.Message, state: FSMContext):
    if user_usage.get(m.from_user.id) == datetime.date.today() and m.from_user.id not in ADMIN_IDS:
        await m.answer("❌ Ліміт GUEST (1 запит/доба) вичерпано. Придбайте LITE/PRO.")
        return
    await state.set_state(SearchState.waiting_for_target)
    await m.answer("📡 Введіть ціль (Нікнейм, ПІБ, Телефон, Email або IP):")

@dp.message(SearchState.waiting_for_target)
async def handle_search(m: types.Message, state: FSMContext):
    target = m.text.strip()
    if target in ["🔎 Новий пошук", "📊 Статистика", "💎 VIP / Тарифи", "📂 Мої результати"]: return
    
    if any(x.upper() in target.upper() for x in OWNER_DATA) and m.from_user.id not in ADMIN_IDS:
        await m.answer("⚠️ <b>ACCESS DENIED: GHOST-PROTECT ACTIVE</b>")
        await state.clear()
        return
    
    user_usage[m.from_user.id] = datetime.date.today()
    await state.clear()
    
    st_msg = await m.answer("🔍 <b>ЗБІР ДАНИХ ТА АНАЛІЗ...</b>\n<i>Швидкий режим (до ~30 сек).</i>")
    
    raw_data = await fast_engine(target)
    
    prompt = (
        f"Target: {target}\nData Context: {raw_data}\n\n"
        "Склади офіційне досьє по 8 пунктах:\n"
        "1. Ідентифікація\n2. Зв'язки\n3. Гео-аналітика\n4. Цифровий слід\n"
        "5. Фінанси\n6. Поведінковий патерн\n7. Події/Хронологія\n8. LIVE-статус/Ризики\n\n"
        "Тільки факти на основі контексту. Українською мовою."
    )
    
    try:
        res = await ai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        report = res.choices[0].message.content
        
        pdf_p = f"reports/rep_{m.from_user.id}.pdf"
        os.makedirs("reports", exist_ok=True)
        make_pdf(target, report, pdf_p)
        
        await bot.send_document(m.chat.id, FSInputFile(pdf_p), caption=f"📄 Фінальне досьє: {target}")
    except Exception as e:
        logging.error(f"Analysis Error: {e}")
        await m.answer(f"❌ Збій AI: {e}")
    finally:
        await st_msg.delete()

@dp.message(F.text == "📂 Мої результати")
async def my_results(m: types.Message):
    path = f"reports/rep_{m.from_user.id}.pdf"
    if os.path.exists(path): await bot.send_document(m.chat.id, FSInputFile(path))
    else: await m.answer("📭 У вас ще немає збережених звітів.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Long-polling для стабільності
    await bot.delete_webhook(drop_pending_updates=True)
    polling_task = asyncio.create_task(dp.start_polling(bot))
    
    # Автопостинг
    scheduler.add_job(auto_post, 'interval', hours=4)
    scheduler.start()
    
    yield
    polling_task.cancel()
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
@app.get("/")
async def root(): return {"status": "V14_PROD_OPERATIONAL"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
