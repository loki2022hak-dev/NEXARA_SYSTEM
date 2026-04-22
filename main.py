import uvicorn, os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from app.core.config import BOT_TOKEN, WEBHOOK_URL, PORT, ADMIN_IDS
from app.services.osint import deep_scan
from app.services.pdf_gen import generate_report_v2
from contextlib import asynccontextmanager

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# UI
main_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔎 Новий пошук"), KeyboardButton(text="📊 Risk Score")],
    [KeyboardButton(text="📂 Мої звіти"), KeyboardButton(text="⚙ Профіль")],
    [KeyboardButton(text="💎 VIP")]
], resize_keyboard=True)

@dp.message(F.text == "🔎 Новий пошук")
async def start_search(m: types.Message):
    await m.answer("📡 Введіть ціль для аналітичного звіту:")

@dp.message()
async def handle_all(m: types.Message):
    if m.text in ["🔎 Новий пошук", "💎 VIP"]: return
    target = m.text.strip()
    st = await m.answer("🔍 **NEXARA СИНТЕЗУЄ ДАНІ...**")
    
    data = await deep_scan(target)
    path = f"reports/rep_{m.from_user.id}.pdf"
    generate_report_v2(target, data, path)
    
    await bot.send_document(m.chat.id, FSInputFile(path), caption=f"🛡 Аналітичний звіт: {target}")
    await st.delete()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook", drop_pending_updates=True)
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/health")
async def health(): return {"status": "elite"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
