import asyncio, os, uvicorn, subprocess, psutil, datetime
import shodan
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from openai import AsyncOpenAI
from fastapi import FastAPI, Request
from serpapi import GoogleSearch
from duckduckgo_search import DDGS
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager

# CONFIG
BOT_TOKEN = os.getenv("BOT_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SHODAN_KEY = os.getenv("SHODAN_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
MAIGRET_BIN = os.getenv("MAIGRET_BIN", "maigret")
PORT = int(os.getenv("PORT", 8000))

# INIT
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
ai_client = AsyncOpenAI(api_key=OPENAI_KEY)
scheduler = AsyncIOScheduler()

class SearchState(StatesGroup):
    waiting_for_target = State()

main_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🔎 Новий пошук"), KeyboardButton(text="📊 Статистика")]],
    resize_keyboard=True
)

async def run_maigret(target: str, timeout: int = 45) -> str:
    try:
        process = await asyncio.create_subprocess_exec(
            MAIGRET_BIN, target, "--json", "simple",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            return stdout.decode('utf-8', errors='ignore') or stderr.decode('utf-8', errors='ignore')
        except asyncio.TimeoutError:
            process.kill()
            return "Maigret Error: Timeout"
    except Exception as e: return f"Maigret Error: {e}"

async def total_engine(target: str) -> dict:
    res = {"web": "N/A", "socials": "N/A", "infra": "N/A"}
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

class ChannelAutoPoster:
    @staticmethod
    async def post_daily_insight():
        if not CHANNEL_ID: return
        try:
            res = await ai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": "Ти - Senior OSINT Analyst Nexara."},
                          {"role": "user", "content": "Згенеруй пост про вразливості."}]
            )
            await bot.send_message(CHANNEL_ID, f"🚀 <b>NEXARA INTELLIGENCE</b>\n\n{res.choices[0].message.content}")
        except: pass

@dp.message(F.text == "/start")
async def start_cmd(m: types.Message, state: FSMContext):
    await state.clear()
    await m.answer("<b>NEXARA V5.1 ACTIVE</b>", reply_markup=main_kb)

@dp.message(F.text == "📊 Статистика")
async def stats_cmd(m: types.Message):
    await m.answer(f"📊 CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}%")

@dp.message(F.text == "🔎 Новий пошук")
async def new_search_cmd(m: types.Message, state: FSMContext):
    await state.set_state(SearchState.waiting_for_target)
    await m.answer("📡 Введіть ідентифікатор:")

@dp.message(SearchState.waiting_for_target)
async def process_target(m: types.Message, state: FSMContext):
    if m.text in ["🔎 Новий пошук", "📊 Статистика"]: return
    await state.clear()
    st = await m.answer("📡 <b>SCANNING...</b>")
    data = await total_engine(m.text)
    prompt = f"TARGET: {m.text}\nCONTEXT: {data}\nВидай звіт по 8 пунктах."
    try:
        res = await ai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        await st.edit_text(f"🛑 <b>ЗВІТ: {m.text}</b>\n\n{res.choices[0].message.content}")
    except: await st.edit_text("❌ Error")

@asynccontextmanager
async def lifespan(app: FastAPI):
    if WEBHOOK_URL: await bot.set_webhook(WEBHOOK_URL)
    scheduler.add_job(ChannelAutoPoster.post_daily_insight, "interval", hours=24)
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
