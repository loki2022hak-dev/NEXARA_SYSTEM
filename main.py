import asyncio, os, uvicorn
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager

# HARD DATA
BOT_TOKEN = "8780973686:AAHskEYhW8GHMZN9SgRXDvgvcUFxGVqJAvE"
# Беремо URL з env, який ми щойно встановили
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://conservative-sheila-nexara-core-0fdc5bcb.koyeb.app")
PORT = int(os.getenv("PORT", 8000))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

@dp.message(F.text == "/start")
async def cmd_start(m: types.Message):
    await m.answer("🚀 <b>NEXARA SYSTEM ONLINE</b>\n\nЗв'язок встановлено. Система готова до OSINT-запитів.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Видаляємо старі хвости та ставимо чистий вебхук
    await bot.delete_webhook(drop_pending_updates=True)
    webhook_path = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    await bot.set_webhook(url=webhook_path)
    print(f"--- WEBHOOK ACTIVE AT: {webhook_path} ---")
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def health():
    return {"status": "active", "webhook": WEBHOOK_URL}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = types.Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"Update error: {e}")
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
