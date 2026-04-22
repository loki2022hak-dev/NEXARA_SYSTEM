import asyncio, os, uvicorn, subprocess, shodan, psutil, datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from openai import AsyncOpenAI
from fastapi import FastAPI, Request
from serpapi import GoogleSearch
from duckduckgo_search import DDGS
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()

# КЛЮЧІ БЕРУТЬСЯ ТІЛЬКИ З ENV (KOYEB)
BOT_TOKEN = os.getenv("BOT_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SHODAN_KEY = os.getenv("SHODAN_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN MISSING")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
ai_client = AsyncOpenAI(api_key=OPENAI_KEY)
scheduler = AsyncIOScheduler()
_started = False

main_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🔎 Новий пошук"), KeyboardButton(text="📊 Статистика")]],
    resize_keyboard=True
)

class VenicePoster:
    @staticmethod
    async def run():
        if not CHANNEL_ID or not OPENAI_KEY: return
        try:
            res = await ai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": "Ти - Senior OSINT Architect Nexara."},
                          {"role": "user", "content": "Напиши пост про деанонімізацію."}]
            )
            await bot.send_message(CHANNEL_ID, f"📡 <b>NEXARA INTEL:</b>\n\n{res.choices[0].message.content}")
        except: pass

async def engine(target):
    data = {"web": "N/A", "socials": "N/A", "infra": "N/A"}
    try:
        with DDGS() as ddgs:
            data["web"] = str([r['body'] for r in ddgs.text(target, max_results=3)])
        if SERPAPI_KEY:
            s = GoogleSearch({"q": target, "api_key": SERPAPI_KEY})
            data["web"] += str([o.get("snippet") for o in s.get_dict().get("organic_results", [])[:3]])
    except: pass
    try:
        p = await asyncio.create_subprocess_exec("maigret", target, "--json", "simple", "--timeout", "40", stdout=asyncio.subprocess.PIPE)
        out, _ = await p.communicate()
        data["socials"] = out.decode('utf-8', errors='ignore')
    except: pass
    if SHODAN_KEY:
        try:
            api = shodan.Shodan(SHODAN_KEY)
            h = api.host(target)
            data["infra"] = f"Ports: {h['ports']}, OS: {h.get('os', 'N/A')}"
        except: pass
    return data

@dp.message(F.text == "/start")
async def start(m: types.Message):
    await m.answer("<b>NEXARA V4.8 [STABLE] ONLINE.</b>", reply_markup=main_kb)

@dp.message(F.text == "📊 Статистика")
async def stats(m: types.Message):
    await m.answer(f"📊 CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}% | Status: <b>Online</b>")

@dp.message()
async def handle(m: types.Message):
    if m.text == "🔎 Новий пошук":
        await m.answer("📡 Введіть ідентифікатор:")
        return
    if not m.text or m.text.startswith("/"): return
    st = await m.answer("📡 <b>SCANNING...</b>")
    raw = await engine(m.text)
    prompt = f"TARGET: {m.text}\nDATA: {raw}\nЗгенеруй звіт по 8 пунктах. Жорстко."
    try:
        res = await ai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        await st.edit_text(f"🛑 <b>ЗВІТ: {m.text}</b>\n\n{res.choices[0].message.content}")
    except Exception as e: await st.edit_text(f"❌ Error: {str(e)}")

app = FastAPI()
@app.post("/webhook")
async def wh(r: Request):
    u = types.Update.model_validate(await r.json(), context={"bot": bot})
    await dp.feed_update(bot, u)
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    global _started
    if not _started:
        if WEBHOOK_URL: await bot.set_webhook(WEBHOOK_URL)
        scheduler.add_job(VenicePoster.run, "interval", hours=24)
        scheduler.start()
        _started = True

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
