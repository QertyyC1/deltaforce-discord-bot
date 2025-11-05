import os
import discord
from discord.ext import commands, tasks
import requests
from datetime import datetime

TOKEN = os.getenv("TOKEN")

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
    """Sprawdza dzisiejsze kody i wysyła na kanał"""
    await ctx.send("🔄 Sprawdzam kody...")

    url = "https://fortniteapi.io/v1/game/codes"
    headers = {"Authorization": os.getenv("API_KEY")}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        await ctx.send("❌ Brak odpowiedzi API")
        return

    data = response.json()
    codes = data.get("codes", [])

    if not codes:
        await ctx.send("😕 Dzisiaj brak nowych kodów!")
    else:
        msg = "✅ Dzisiejsze kody Fortnite:\n" + "\n".join([f"- `{c['code']}`" for c in codes])
        await ctx.send(msg)

@tasks.loop(minutes=5)
async def check_codes():
    """Automatyczne sprawdzanie kodów co 5 min"""
    channel_id = os.getenv("CHANNEL_ID")
    if not channel_id:
        print("❌ CHANNEL_ID nie ustawione!")
        return

    channel = bot.get_channel(int(channel_id))
    if channel:
        now = datetime.utcnow().strftime("%H:%M")
        await channel.send(f"⏰ Autosprawdzenie kodów ({now} UTC) — użyj !sprawdz")

bot.run(TOKEN)


