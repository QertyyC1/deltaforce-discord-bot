import os
import sys
import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# === TOKEN DEBUG ===
TOKEN = os.getenv("TOKEN")

if TOKEN is None:
    print("❌ DEBUG: TOKEN is None — Brak zmiennej środowiskowej 'TOKEN' w Railway!")
    sys.exit(1)
else:
    TOKEN = TOKEN.strip()  # usuwa spacje i nowe linie
    display = f"{TOKEN[:4]}...{TOKEN[-4:]}" if len(TOKEN) > 8 else TOKEN
    print(f"✅ DEBUG: TOKEN OK — length: {len(TOKEN)}, preview: {display}")

# === Discord Intents ===
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

CHANNEL_ID = 1435569396394233856  # Twój kanał

# === Funkcja pobierająca Daily Codes ===
def fetch_daily_codes():
    url = "https://deltaforcetools.gg"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    code_boxes = soup.find_all("div", class_="box-code")
    codes = [box.text.strip() for box in code_boxes][:5]  # Pobierz 5 kodów

    return codes

# === Zadanie automatyczne o 01:00 ===
@tasks.loop(minutes=1)
async def daily_task():
    now = datetime.utcnow().strftime("%H:%M")
    if now == "00:00":  # 01:00 w Polsce = 00:00 UTC
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            codes = fetch_daily_codes()
            msg = "📌 Daily Codes:\n" + "\n".join(f"• {c}" for c in codes)
            await channel.send(msg)

@bot.event
async def on_ready():
    print(f"✅ Bot zalogowany jako: {bot.user}")
    daily_task.start()

# === Komenda ręczna: !codes ===
@bot.command()
async def codes(ctx):
    codes = fetch_daily_codes()
    msg = "📌 Daily Codes:\n" + "\n".join(f"• {c}" for c in codes)
    await ctx.send(msg)

# === Start bota ===
bot.run(TOKEN)

