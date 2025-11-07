# ✅ FULLY FIXED bot.py FOR RAILWAY ✅

import os
import asyncio
import tempfile
import aiohttp
from datetime import datetime, timedelta, timezone
from threading import Thread

import discord
from discord.ext import commands, tasks

from playwright.async_api import async_playwright
from flask import Flask

# ---- Config (env variables) ----
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://google.com")  # ✅ zmieniaj tylko w env

if not DISCORD_TOKEN:
    print("❌ Missing DISCORD_TOKEN!")
if not CHANNEL_ID:
    print("⚠️ Missing CHANNEL_ID (auto messages disabled)")

# ---- Discord bot ----
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---- Helper: Delete old bot messages ----
async def delete_old_bot_messages(channel, limit=50):
    try:
        async for msg in channel.history(limit=limit):
            if msg.author == bot.user:
                await msg.delete()
    except Exception as e:
        print("Błąd usuwania wiadomości:", e)

# ---- Scraper ----
async def fetch_and_screenshot_tiles(url="https://deltaforcetools.gg/daily-codes"):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ])
            page = await browser.new_page(viewport={"width": 1280, "height": 2400})

            await page.goto(url, wait_until="networkidle", timeout=45000)

            # ✅ Poczekaj aż kafelki się załadują
            try:
                await page.wait_for_selector("img", timeout=10000)
            except:
                print("⚠️ Nie wykryto obrazów — fallback")
            
            tiles = await page.query_selector_all("img")
            tmpfiles = []

            if tiles:
                for i, tile in enumerate(tiles[:12]):
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                    await tile.screenshot(path=tmp)
                    tmpfiles.append(tmp)
                print(f"✅ Znaleziono kafelków: {len(tmpfiles)}")
            else:
                print("⚠️ Brak kafelków → screen całej strony")
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                await page.screenshot(path=tmp, full_page=True)
                tmpfiles.append(tmp)

            await browser.close()
            return tmpfiles

    except Exception as e:
        print("❌ Playwright Error:", e)
        return None

# ---- Command ----
@bot.command()
async def sprawdz(ctx):
    await ctx.send("🔄 Pobieram zrzuty kafelków...")
    files = await fetch_and_screenshot_tiles()
    if not files:
        return await ctx.send("❌ Nie udało się pobrać 😕")

    await delete_old_bot_messages(ctx.channel)

    for f in files:
        await ctx.send(file=discord.File(f))
        os.remove(f)

    await ctx.send("✅ Gotowe!")

# ---- Daily Auto Job ----
async def seconds_until(hour=1):
    now = datetime.now(timezone.utc)
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()

@tasks.loop(hours=24)
async def auto_daily():
    if not CHANNEL_ID:
        return
    
    chan = bot.get_channel(CHANNEL_ID)
    if not chan:
        print("⚠️ Brak kanału!")
        return

    files = await fetch_and_screenshot_tiles()
    if not files:
        await chan.send("❌ Automatyczne pobranie nieudane")
        return

    await delete_old_bot_messages(chan)

    for f in files:
        await chan.send(file=discord.File(f))
        os.remove(f)

    now = datetime.utcnow()
    await chan.send(f"🎯 Daily codes update: {now:%Y-%m-%d %H:%M UTC}")

# ---- Keep Alive Server ----
app = Flask(__name__)
@app.route("/")
def home():
    return "✅ Bot działa!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, threaded=True)

def start_web():
    Thread(target=run_web, daemon=True).start()

async def keepalive():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            async with aiohttp.ClientSession() as s:
                await s.get(PUBLIC_URL)
        except:
            pass
        await asyncio.sleep(30)

# ---- On Ready ----
@bot.event
async def on_ready():
    print(f"✅ Zalogowano jako {bot.user}")
    bot.loop.create_task(keepalive())
    wait = await seconds_until(1)
    print(f"⏳ Pierwszy auto check za {int(wait)} sekund")
    await asyncio.sleep(wait)
    auto_daily.start()
    await auto_daily()

# ---- Startup ----
start_web()
bot.run(DISCORD_TOKEN)
