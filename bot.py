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
        return

    url = "https://fortniteapi.io/v1/codes/list"
    headers = {"Authorization": API_KEY}

    try:
        response = requests.get(url, headers=headers)
        data = response.json()
    except:
        await ctx.send("❌ Błąd połączenia z API")
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



