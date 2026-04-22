import asyncio, os, uvicorn, datetime, random, aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, URLInputFile
from openai import AsyncOpenAI
from fastapi import FastAPI, Request
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager

# CONFIG FROM YOUR SCREENSHOT
BOT_TOKEN = "8780973686:AAHskEYhW8GHMZN9SgRXDvgvcUFxGVqJAvE"
CHANNEL_ID = os.getenv("CHANNEL_ID", "-1002220197777")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8000))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
ai_client = AsyncOpenAI(api_key=OPENAI_KEY)
scheduler = AsyncIOScheduler()

# CONTENT GENERATOR
async def auto_poster():
    try:
        res = await ai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Напиши OSINT кейс для каналу NEXARA. Українською."}]
        )
        # Для візуалу використовуємо DALL-E 3 (стабільніше за Unsplash API в рантаймі)
        img = await ai_client.images.generate(model="dall-e-3", prompt="Cyberpunk OSINT data visualization", n=1)
        await bot.send_photo(CHANNEL_ID, photo=img.data[0].url, caption=res.choices[0].message.content[:1024])
    except Exception as e:
        print(f"Post error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("reports", exist_ok=True)
    if WEBHOOK_URL:
        await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    scheduler.add_job(auto_poster, 'interval', hours=4)
    scheduler.start()
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def health(): return {"status": "healthy"}

@app.post("/webhook")
async def wh(request: Request):
    u = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, u)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
