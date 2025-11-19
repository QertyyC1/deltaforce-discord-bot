import os
import asyncio
import aiohttp
import re
from datetime import datetime, timedelta, timezone
from threading import Thread

import discord
from discord.ext import commands, tasks
from playwright.async_api import async_playwright
from flask import Flask

# ---------------- Config ----------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "1436296685788729415"))
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://deltaforce-discord-bot-production.up.railway.app")

if not DISCORD_TOKEN:
    print("❌ Brak DISCORD_TOKEN w env. Ustaw i restartuj.")
if not CHANNEL_ID:
    print("⚠️ CHANNEL_ID = 0 (nie ustawione) — auto-check nie wyśle niczego.")

# ---------------- Discord setup ----------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- Helpers ----------------
async def delete_old_bot_messages(channel, limit=100):
    """Usuwa stare wiadomości bota z kanału."""
    try:
        async for msg in channel.history(limit=limit):
            if msg.author == bot.user:
                await msg.delete()
    except Exception as e:
        print("⚠️ Błąd podczas usuwania starych wiadomości:", e)

# ---------------- Komenda !sprawdz ----------------
@bot.command(name="sprawdz")
async def cmd_sprawdz(ctx):
    SCREEN_X = 265
    SCREEN_Y = 900
    SCREEN_WIDTH = 1920
    SCREEN_HEIGHT = 350
    SCROLL_Y = 900
    WAIT_BEFORE_SCREEN = 3

    await ctx.send("🔄 Pobieram sekcję **Daily Codes**...")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1920, "height": 2000})

            await page.goto("https://deltaforcetools.gg", wait_until="networkidle")
            await asyncio.sleep(10)

            await page.evaluate(f"window.scrollTo(0, {SCROLL_Y})")
            await asyncio.sleep(WAIT_BEFORE_SCREEN)

            screenshot_path = "daily_codes_section.png"
            await page.screenshot(
                path=screenshot_path,
                clip={
                    "x": SCREEN_X,
                    "y": SCREEN_Y,
                    "width": SCREEN_WIDTH,
                    "height": SCREEN_HEIGHT,
                },
            )

            await browser.close()

            # Usuń stare wiadomości przed wysłaniem nowej
            await delete_old_bot_messages(ctx.channel)

            await ctx.send("✅ Oto aktualne **Daily Codes** 👇", file=discord.File(screenshot_path))
            os.remove(screenshot_path)

    except Exception as e:
        await ctx.send(f"❌ Błąd: `{e}`")
        import traceback
        traceback.print_exc()

# ---------------- Harmonogram codzienny ----------------
async def seconds_until_next_utc_run(hour_utc=23, minute_utc=20):
    """Zwraca liczbę sekund do następnego uruchomienia o określonej godzinie UTC."""
    now = datetime.now(timezone.utc)
    target = now.replace(hour=hour_utc, minute=minute_utc, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()

@tasks.loop(hours=24)
async def daily_job():
    """Automatycznie wysyła screena codziennie o 00:20 czasu polskiego."""
    if not CHANNEL_ID:
        print("⚠️ CHANNEL_ID not set — daily_job will skip sending.")
        return

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("⚠️ Nie znaleziono kanału (daily_job).")
        return

    print("📸 Wykonuję automatyczny zrzut sekcji Daily Codes...")

    SCREEN_X = 265
    SCREEN_Y = 900
    SCREEN_WIDTH = 1920
    SCREEN_HEIGHT = 350
    SCROLL_Y = 900
    WAIT_BEFORE_SCREEN = 3
    screenshot_path = "daily_codes_section.png"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1920, "height": 2000})
            await page.goto("https://deltaforcetools.gg", wait_until="networkidle")
            await asyncio.sleep(10)
            await page.evaluate(f"window.scrollTo(0, {SCROLL_Y})")
            await asyncio.sleep(WAIT_BEFORE_SCREEN)

            await page.screenshot(
                path=screenshot_path,
                clip={
                    "x": SCREEN_X,
                    "y": SCREEN_Y,
                    "width": SCREEN_WIDTH,
                    "height": SCREEN_HEIGHT,
                },
            )
            await browser.close()

            # usuń stare wiadomości
            await delete_old_bot_messages(channel)

            await channel.send("✅ Oto aktualne **Daily Codes** 👇", file=discord.File(screenshot_path))
            os.remove(screenshot_path)

    except Exception as e:
        print("❌ Błąd podczas automatycznego wysyłania:", e)

# ---------------- Keepalive webserver (Flask) ----------------
app = Flask("df_bot_keepalive")

@app.route("/")
def home():
    return "DeltaForceDailyCodes bot is running."

def run_web():
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, threaded=True)

def start_web_thread():
    Thread(target=run_web, daemon=True).start()

# ---------------- Keepalive ping ----------------
async def keepalive_ping():
    await bot.wait_until_ready()
    async with aiohttp.ClientSession() as session:
        while not bot.is_closed():
            try:
                await session.get(PUBLIC_URL, timeout=10)
            except Exception:
                pass
            await asyncio.sleep(30)

# ---------------- Setup hook ----------------
@bot.event
async def setup_hook():
    start_web_thread()
    print("✅ Keepalive webserver started.")

    asyncio.create_task(keepalive_ping())
    print("✅ Keepalive pinger started.")

    async def starter():
        wait = await seconds_until_next_utc_run(23, 20)
        print(f"⏳ Pierwsze uruchomienie za {int(wait)}s (-> 23:20 UTC / 00:20 czasu polskiego)")
        await asyncio.sleep(wait)
        await daily_job()
        daily_job.start()

    asyncio.create_task(starter())

# ---------------- Run bot ----------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)


