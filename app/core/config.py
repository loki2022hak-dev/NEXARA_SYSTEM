import os
from dotenv import load_line_dotenv

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
SHODAN_KEY = os.getenv("SHODAN_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "-1002220197777")
CHANNEL_USER = os.getenv("CHANNEL_USER", "@nexara_osint")
PORT = int(os.getenv("PORT", 8000))
MAIGRET_BIN = "/usr/local/bin/maigret"

# Security (ENV lists format: item1,item2)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "8089452251").split(",") if x]
GHOST_TARGETS = [x.upper() for x in os.getenv("GHOST_TARGETS", "").split(",") if x]

# DB & Redis (Fallbacks to local/memory if not provided)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///nexara.db")
REDIS_URL = os.getenv("REDIS_URL", "")
