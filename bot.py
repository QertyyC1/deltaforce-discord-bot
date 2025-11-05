import os
import discord
from discord.ext import commands, tasks
import requests
from datetime import datetime

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
    await ctx.send("🔄 Sprawdzam kody...")

    if not API_KEY:
        await ctx.send("❌ Brak API_KEY w zmiennych środowiskowych!")
        print("❌ DEBUG: API_KEY is None")
        return

    url = "https://fortniteapi.io/v1/codes/list"
    headers = {"Authorization": API_KEY}

    print("🔍 DEBUG: Wysyłam zapytanie do API...")
    print(f"🔍 DEBUG: URL = {url}")
    print(f"🔍 DEBUG: API_KEY preview = {API_KEY[:4]}...{API_KEY[-4:]}")

    try:
        response = requests.get(url, headers=headers)
        print(f"🔍 DEBUG: Status = {response.status_code}")
        print(f"🔍 DEBUG: Response = {response.text}")
    except Exception as e:
        await ctx.send("❌ Wyjątek podczas połączenia z API")
        print(f"❌ DEBUG ERROR: {e}")
        return

    if response.status_code != 200:
        await ctx.send(f"❌ API zwróciło błąd: {response.status_code}")
        return

    try:
        data = response.json()
    except:
        await ctx.send("⚠️ API nie zwróciło JSON!")
        return

    codes = data.get("codes", [])

    if not codes:
        await ctx.send("😕 Dzisiaj brak nowych kodów!")
    else:
        msg = "✅ Dzisiejsze kody Fortnite:\n"
        for c in codes:
            msg += f"> 🎯 `{c['code']}` — {c.get('title','Brak opisu')}\n"
        await ctx.send(msg)


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




