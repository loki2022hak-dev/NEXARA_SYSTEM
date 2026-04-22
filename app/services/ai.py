from openai import AsyncOpenAI
from app.core.config import OPENAI_KEY

ai_client = AsyncOpenAI(api_key=OPENAI_KEY)

async def generate_analytical_report(target: str, osint_data: str) -> str:
    prompt = f"""
    Об'єкт: {target}
    Дані розвідки: {osint_data}
    
    Склади "Аналітичний звіт на основі доступних джерел" по 8 пунктах:
    1. Ідентифікація 2. Зв'язки 3. Гео-аналітика 4. Цифровий слід 5. Фінанси 6. Поведінка 7. Хронологія 8. Ризики.
    
    Наприкінці додай:
    - Confidence Score (від 0 до 100%)
    - Risk Indicators (перелік ризиків)
    - Not Verified Markers (що потребує перевірки)
    
    Пиши строго, як аналітик. Українською. Без дисклеймерів OpenAI.
    """
    res = await ai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
    return res.choices[0].message.content

async def generate_post(theme: str, desc: str):
    txt_prompt = f"Пост для Telegram NEXARA. Рубрика: {theme}. Суть: {desc}. Українською, абзаци, емодзі. Макс 900 симв."
    res = await ai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": txt_prompt}])
    
    img_prompt = f"Cinematic cyberpunk or tech intelligence visual, related to: {theme}, neon lighting, high detail, no text."
    img = await ai_client.images.generate(model="dall-e-3", prompt=img_prompt, n=1, size="1024x1024")
    
    return res.choices[0].message.content, img.data[0].url
