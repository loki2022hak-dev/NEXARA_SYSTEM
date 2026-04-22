import os
from aiogram import Router, Bot, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from app.bot.states import SearchState
from app.bot.keyboards import main_kb, sub_kb
from app.core.config import CHANNEL_ID, ADMIN_IDS, GHOST_TARGETS, CHANNEL_USER
from app.core.rate_limit import check_rate_limit
from app.services.osint import execute_osint
from app.services.ai import generate_analytical_report
from app.services.pdf import build_pdf_report
from app.db.database import AsyncSessionLocal
from app.db.models import User, SearchHistory
from sqlalchemy.future import select

router = Router()

async def is_sub(bot: Bot, u_id: int):
    if u_id in ADMIN_IDS: return True
    try:
        m = await bot.get_chat_member(CHANNEL_ID, u_id)
        return m.status not in ["left", "kicked"]
    except: return False

async def get_or_create_user(session, tg_id: int):
    q = await session.execute(select(User).where(User.tg_id == tg_id))
    u = q.scalar_one_or_none()
    if not u:
        u = User(tg_id=tg_id, tier="ELITE" if tg_id in ADMIN_IDS else "GUEST")
        session.add(u)
        await session.commit()
    return u

@router.message(CommandStart())
async def cmd_start(m: types.Message, bot: Bot):
    if not await is_sub(bot, m.from_user.id):
        await m.answer(f"🛑 <b>ДОСТУП ЗАБЛОКОВАНО</b>\nПідпишіться на {CHANNEL_USER}", reply_markup=sub_kb)
        return
    async with AsyncSessionLocal() as session:
        await get_or_create_user(session, m.from_user.id)
    await m.answer("🚀 <b>NEXARA SYSTEM ONLINE</b>", reply_markup=main_kb)

@router.callback_query(F.data == "check_sub")
async def cb_check_sub(c: types.CallbackQuery, bot: Bot):
    if await is_sub(bot, c.from_user.id):
        await c.message.delete()
        await c.message.answer("🚀 <b>NEXARA SYSTEM ONLINE</b>", reply_markup=main_kb)
    else:
        await c.answer("❌ Немає підписки", show_alert=True)

@router.message(F.text == "💎 VIP")
async def cmd_vip(m: types.Message):
    txt = (
        "<b>💎 ТАРИФИ NEXARA:</b>\n\n"
        "🟢 <b>FREE:</b> 1 пошук\n"
        "🟡 <b>LITE ($15/міс):</b> 50 пошуків + PDF\n"
        "🔵 <b>PRO ($45/міс):</b> Безліміт + Deep Search\n"
        "🔴 <b>ELITE ($150/міс):</b> API + Monitoring\n\n"
        "💳 <b>Оплата:</b> @Nexara_EN"
    )
    await m.answer(txt)

@router.message(F.text == "⚙ Профіль")
async def cmd_profile(m: types.Message):
    async with AsyncSessionLocal() as session:
        u = await get_or_create_user(session, m.from_user.id)
        await m.answer(f"👤 <b>ПРОФІЛЬ</b>\nID: {u.tg_id}\nТариф: <b>{u.tier}</b>")

@router.message(F.text.in_(["📊 Risk Score", "🛡 AntiScam"]))
async def cmd_modules(m: types.Message):
    await m.answer("Модуль у процесі інтеграції. (Update 14.1)")

@router.message(F.text == "📂 Мої звіти")
async def cmd_reports(m: types.Message):
    p = f"reports/report_{m.from_user.id}.pdf"
    if os.path.exists(p): await m.answer_document(FSInputFile(p))
    else: await m.answer("📭 Порожньо")

@router.message(F.text == "🔎 Новий пошук")
async def search_init(m: types.Message, state: FSMContext):
    async with AsyncSessionLocal() as session:
        u = await get_or_create_user(session, m.from_user.id)
        if not await check_rate_limit(m.from_user.id, u.tier):
            await m.answer("❌ Ліміт вичерпано. Купіть VIP.")
            return
    await state.set_state(SearchState.waiting_for_target)
    await m.answer("📡 Введіть ціль (Домен, IP, ПІБ, Нікнейм):")

@router.message(SearchState.waiting_for_target)
async def do_search(m: types.Message, state: FSMContext):
    target = m.text.strip()
    await state.clear()
    
    if any(x in target.upper() for x in GHOST_TARGETS) and m.from_user.id not in ADMIN_IDS:
        await m.answer("⚠️ <b>ACCESS DENIED: GHOST PROTECT</b>")
        return
    
    async with AsyncSessionLocal() as session:
        u = await get_or_create_user(session, m.from_user.id)
        history = SearchHistory(tg_id=m.from_user.id, target=target)
        session.add(history)
        await session.commit()
    
    st = await m.answer("🔍 <b>Агрегація даних (Whois, Shodan, Web, Socials)...</b>")
    
    is_pro = u.tier in ["PRO", "ELITE"]
    raw_osint = await execute_osint(target, is_pro)
    
    await st.edit_text("🧠 <b>AI Аналіз та генерація Risk Score...</b>")
    report_text = await generate_analytical_report(target, raw_osint)
    
    pdf_path = build_pdf_report(target, report_text, m.from_user.id)
    
    await m.answer_document(FSInputFile(pdf_path), caption=f"📄 Аналітичний звіт: {target}")
    await st.delete()
