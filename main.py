import asyncio, logging, os
import uvicorn
from fastapi import FastAPI
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager

from app.core.config import BOT_TOKEN, PORT
from app.db.database import init_db
from app.bot.handlers import router
from app.scheduler.tasks import cron_auto_post

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Init DB
    await init_db()
    
    # 2. Cleanup Webhook & Start Polling
    await bot.delete_webhook(drop_pending_updates=True)
    polling_task = asyncio.create_task(dp.start_polling(bot))
    
    # 3. Start Scheduler (2 posts a day = every 12 hours)
    scheduler.add_job(cron_auto_post, 'interval', hours=12, args=[bot])
    scheduler.start()
    
    yield
    polling_task.cancel()
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"system": "NEXARA SAAS V14", "status": "Operational"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
