import asyncio, os, datetime, psutil, logging, random
import shodan
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, URLInputFile
from aiogram.filters import CommandStart
from openai import AsyncOpenAI
from fastapi import FastAPI
from duckduckgo_search import DDGS
from serpapi import GoogleSearch
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from fpdf import FPDF

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
SHODAN_KEY = os.getenv("SHODAN_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "-1002220197777")
CHANNEL_USER = "@nexara_osint"
PORT = int(os.getenv("PORT", 8000))
MAIGRET_BIN = "maigret"
ADMIN_IDS = [8089452251]

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
ai = AsyncOpenAI(api_key=OPENAI_KEY)
scheduler = AsyncIOScheduler()

class StateFlow(StatesGroup):
    wait_target = State()

def ddg(q):
    try:
        with DDGS() as d:
            return "\n".join([i.get("body","") for i in d.text(q, max_results=3)])
    except:
        return ""

def shodan_lookup(t):
    if not SHODAN_KEY or "." not in t:
        return "N/A"
    try:
        api = shodan.Shodan(SHODAN_KEY)
        h = api.host(t)
        return str({"ports": h.get("ports"), "os": h.get("os")})
    except:
        return "N/A"

async def osint_engine(target):
    cmd = f"{MAIGRET_BIN} {target} --json simple --timeout 15"
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    out, _ = await proc.communicate()
    maigret = out.decode(errors="ignore") if out else "N/A"

    return {
        "ddg": await asyncio.to_thread(ddg, target),
        "shodan": await asyncio.to_thread(shodan_lookup, target),
        "maigret": maigret
    }

def pdf_report(target, data, path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 5, f"TARGET: {target}\n\n{data}")
    pdf.output(path)

kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🔎 Пошук")]],
    resize_keyboard=True
)

@dp.message(CommandStart())
async def start(m: types.Message, state: FSMContext):
    await state.set_state(StateFlow.wait_target)
    await m.answer("Введіть ціль:", reply_markup=kb)

@dp.message(StateFlow.wait_target)
async def handle(m: types.Message, state: FSMContext):
    target = m.text
    data = await osint_engine(target)

    prompt = f"Зроби OSINT досьє:\n{data}"
    res = await ai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )

    report = res.choices[0].message.content
    path = f"/tmp/{m.from_user.id}.pdf"
    pdf_report(target, report, path)

    await m.answer_document(FSInputFile(path))
    await state.clear()

app = FastAPI()

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(dp.start_polling(bot))
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
def root():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
