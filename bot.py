import os
import discord
import requests
import asyncio
from discord.ext import commands, tasks
from datetime import datetime

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

last_sent_ids = set()

API_URL = "https://deltaforcetools.gg/api/latest-codes"

def fetch_daily_codes():
    try:
        r = requests.get(API_URL, timeout=10)
        data = r.json()

        if "codes" in data and len(data["codes"]) >= 5:
            return data["codes"][:5]

        return None
    except Exception as e:
        print("❌ Fetch error:", e)
        return None


async def clear_old_messages(channel):
    async for msg in channel.history(limit=50):
        if msg.author == bot.user:
            await msg.delete()


@bot.command()
async def sprawdz(ctx):
    await ctx.send("🔄 Pobieram Daily Codes...")

    codes = fetch_daily_codes()
    if not codes:
        return await ctx.send("❌ Nie udało się pobrać kodów 😕")

    await clear_old_messages(ctx.channel)

    msg_text = "\n".join(f"✅ `{c}`" for c in codes)
    await ctx.send(f"🎯 Aktualne Daily Codes:\n{msg_text}")


@tasks.loop(minutes=60)
async def auto_check():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return

    codes = fetch_daily_codes()
    if not codes:
        return

    codes_id = tuple(codes)
    if codes_id in last_sent_ids:
        return
    
    last_sent_ids.add(codes_id)
    await clear_old_messages(channel)

    now = datetime.utcnow().strftime("%H:%M UTC")
    msg_text = "\n".join(f"✅ `{c}`" for c in codes)
    await channel.send(f"🎯 Nowe Daily Codes {now}:\n{msg_text}")


@bot.event
async def on_ready():
    print(f"✅ Bot zalogowany jako: {bot.user}")
    auto_check.start()


bot.run(TOKEN)












