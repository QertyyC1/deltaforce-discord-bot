import os
import discord
from discord.ext import commands, tasks
import requests
from datetime import datetime
from bs4 import BeautifulSoup

TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not TOKEN:
    print("❌ DEBUG: TOKEN is None — brak zmiennej środowiskowej!")
else:
    print(f"✅ DEBUG: TOKEN OK — length: {len(TOKEN)}, preview: {TOKEN[:4]}...{TOKEN[-4:]}")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot zalogowany jako: {bot.user}")
    check_codes.start()

@bot.command()
async def sprawdz(ctx):
    await ctx.send("🔄 Pobieram Daily Codes z DeltaForceTools...")

    url = "https://deltaforcetools.gg/api/codes.json"

    try:
        response = requests.get(url, timeout=10)
    except Exception as e:
        await ctx.send(f"❌ Błąd połączenia: {e}")
        return

    if response.status_code != 200:
        await ctx.send(f"❌ Błąd API: {response.status_code}")
        return

    data = response.json()
    codes = data.get("dailyCodes", [])

    if len(codes) < 5:
        await ctx.send("⚠️ Brak pełnej listy kodów!")
        return

    message = "**✅ Dzisiejsze Daily Codes:**\n\n"
    for i, code in enumerate(codes[:5], start=1):
        message += f"🔹 Kod {i}: `{code}`\n"

    await ctx.send(message)



@tasks.loop(minutes=5)
async def check_codes():
    if not CHANNEL_ID:
        print("❌ CHANNEL_ID nie ustawione!")
        return

    channel = bot.get_channel(int(CHANNEL_ID))
    if channel:
        now = datetime.utcnow().strftime("%H:%M")
        await channel.send(f"⏰ Autosprawdzenie kodów ({now} UTC) — użyj !sprawdz")

bot.run(TOKEN)








