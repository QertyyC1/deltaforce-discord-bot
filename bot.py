import os
import discord
from discord.ext import commands, tasks
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from requests_html import HTMLSession

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
    await ctx.send("🔄 Pobieram Daily Codes z DeltaForceTools…")

    try:
        session = HTMLSession()
        r = session.get("https://deltaforcetools.gg/")
        r.html.render(timeout=20)  # renderuje JS
    except Exception as e:
        await ctx.send(f"❌ Błąd pobierania/renderowania: {e}")
        return

    # Zakładam, że kody są w elementach .code-box lub podobnych
    elements = r.html.find(".daily-codes-box span.code")  # przykładowy selektor
    codes = [el.text for el in elements]

    if len(codes) < 5:
        await ctx.send("⚠️ Nie udało się pobrać pełnych danych!")
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









