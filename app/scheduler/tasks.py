import logging
import random
from aiogram import Bot
from aiogram.types import URLInputFile
from app.services.ai import generate_post
from app.core.config import CHANNEL_ID

rubrics = [
    {"theme": "OSINT / Розвідка", "desc": "як перевірити домен, OSINT кейси, інструменти тижня. Формат: OSINT Tip дня."},
    {"theme": "Scam Alerts", "desc": "нові шахрайські схеми, фейкові сайти, telegram fraud. Рубрика: Шахрай дня."},
    {"theme": "Кібер новини", "desc": "що сталося, чому важливо, як захиститися."},
    {"theme": "Build in Public NEXARA", "desc": "новий модуль, скріни досьє, demo reports."},
    {"theme": "Контент ВАУ", "desc": "risk score приклади, graph visualizations."}
]

async def cron_auto_post(bot: Bot):
    selected = random.choice(rubrics)
    try:
        text, img_url = await generate_post(selected["theme"], selected["desc"])
        await bot.send_photo(CHANNEL_ID, photo=URLInputFile(img_url), caption=f"{text}\n\n🤖 <b>@Nexara_Systems_Bot</b>")
    except Exception as e:
        logging.error(f"Cron Post Error: {e}")
