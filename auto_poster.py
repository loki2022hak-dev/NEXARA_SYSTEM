import aiohttp
import asyncio
import random
from aiogram import Bot
from openai import AsyncOpenAI

class ChannelAutoPoster:
    def __init__(self, bot: Bot, ai: AsyncOpenAI, channel_id: str, unsplash_key: str):
        self.bot = bot
        self.ai = ai
        self.channel_id = channel_id
        self.unsplash_key = unsplash_key
        self.categories = ['osint_tools', 'hacking_guides', 'cybersec_news', 'privacy_tips']

    async def get_image(self, topic):
        url = f"https://api.unsplash.com/photos/random?query={topic},cyber&client_id={self.unsplash_key}"
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                if r.status == 200:
                    d = await r.json()
                    return d['urls']['regular']
                return "https://via.placeholder.com/1024x768.png?text=NEXARA+INTEL"

    async def generate_and_post(self):
        topic = random.choice(self.categories)
        prompt = f"Напиши пост для Telegram-каналу CodeGuard. Тема: {topic}. Використовуй емодзі та хакерський стиль. Мова: Українська."
        res = await self.ai.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        text = res.choices[0].message.content
        img = await self.get_image(topic)
        await self.bot.send_photo(self.channel_id, img, caption=text, parse_mode="Markdown")
