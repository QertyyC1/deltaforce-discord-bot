import asyncio
import datetime
import os
import aiohttp
from bs4 import BeautifulSoup
from discord.ext import commands

URL = "https://deltaforcetools.gg/"
CHANNEL_ID = 000000000000000000  # <-- Tutaj wpisz ID kanału!
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

async def fetch_html(session, url):
    async with session.get(url, timeout=20) as resp:
        resp.raise_for_status()
        return await resp.text()

def parse_daily_codes(html):
    soup = BeautifulSoup(html, "html.parser")
    results = {}
    header = soup.find(lambda tag: tag.name in ["h2", "h3"] and "Daily Codes" in tag.get_text())
    if not header:
        return results
    elem = header.find_next_sibling()
    count = 0
    while elem and count < 10:
        map_name = elem.get_text(strip=True)
        code_elem = elem.find_next_sibling()
        date_elem = code_elem.find_next_sibling() if code_elem else None
        if code_elem and date_elem:
            code = code_elem.get_text(strip=True)
            date_text = date_elem.get_text(strip=True)
            results[map_name] = {"code": code, "date": date_text}
            elem = date_elem.find_next_sibling()
        else:
            break
        count += 1
    return results

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=commands.Intents.default())

    async def on_ready(self):
        print(f"✅ Bot online jako: {self.user}")
        self.loop.create_task(self.daily_job())

    async def daily_job(self):
        while True:
            now = datetime.datetime.now()
            next_run = now.replace(hour=1, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += datetime.timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()
            print(f"Czekam {wait_seconds} sekund do aktualizacji o 01:00...")
            await asyncio.sleep(wait_seconds)
            await self.check_and_send_codes()
            await asyncio.sleep(24 * 3600)

    async def check_and_send_codes(self):
        async with aiohttp.ClientSession() as session:
            try:
                html = await fetch_html(session, URL)
                codes = parse_daily_codes(html)
            except Exception as e:
                print("Błąd pobierania:", e)
                return

        if not hasattr(self, "last_codes"):
            self.last_codes = None

        if codes != self.last_codes:
            self.last_codes = codes
            channel = self.get_channel(CHANNEL_ID)
            if not channel:
                print("Nie mogę znaleźć kanału!")
                return

            message = "**🟢 Daily Codes — Delta Force Tools**\n"
            for map_name, info in codes.items():
                message += f"• **{map_name}:** `{info['code']}` *(data: {info['date']})*\n"

            await channel.send(message)
            print("✅ Wysłano aktualizację!")

bot = MyBot()

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("⚠️ Brak tokena! Ustaw zmienną środowiskową: DISCORD_BOT_TOKEN")
    else:
        bot.run(BOT_TOKEN)
