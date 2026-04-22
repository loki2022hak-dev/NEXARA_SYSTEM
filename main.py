import asyncio, os, uvicorn, datetime, random
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager

# DATA FROM YOUR SCREENSHOTS
BOT_TOKEN = "8780973686:AAHskEYhW8GHMZN9SgRXDvgvcUFxGVqJAvE"
CHANNEL_ID = "-1002220197777"
# Очищення URL від зайвих слешів
RAW_URL = os.getenv("WEBHOOK_URL", "https://conservative-sheila-nexara-core-0fdc5bcb.koyeb.app")
WEBHOOK_URL = RAW_URL.rstrip('/')
PORT = int(os.getenv("PORT", 8000))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

@dp.message(F.text == "/start")
async def cmd_start(m: types.Message):
    await m.answer("🚀 <b>NEXARA ONLINE</b>\nСистема активована. Чекаю на OSINT запит.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Примусове скидання та встановлення вебхука
    await bot.delete_webhook(drop_pending_updates=True)
    target_url = f"{WEBHOOK_URL}/webhook"
    await bot.set_webhook(url=target_url)
    print(f"DEPLOY: Webhook set to {target_url}")
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def health():
    return {"status": "operational", "webhook": f"{WEBHOOK_URL}/webhook"}

@app.post("/webhook")
async def wh(request: Request):
    try:
        data = await request.json()
        update = types.Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"ERR: {e}")
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
