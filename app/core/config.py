import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
SHODAN_KEY = os.getenv("SHODAN_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL").rstrip('/')
PORT = int(os.getenv("PORT", 8000))
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "8089452251").split(",")]
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./nexara.db")
