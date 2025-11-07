# bot.py
import os
import asyncio
import tempfile
import aiohttp
from datetime import datetime, timedelta, timezone
from threading import Thread

import discord
from discord.ext import commands, tasks

import requests
from bs4 import BeautifulSoup

# Playwright async
from playwright.async_api import async_playwright

# Flask keep-alive
from flask import Flask

# ---- Config (env) ----
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

if not DISCORD_TOKEN:
    print("❌ Brak DISCORD_TOKEN w env. Ustaw i restartuj.")
if not CHANNEL_ID:
    print("⚠️ CHANNEL_ID = 0 (nie ustawione) — auto-check nie wyśle niczego.")

# ---- Discord bot setup ----
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---- helper: delete old bot messages ----
async def delete_old_bot_messages(channel, limit=50):
    try:
        async for msg in channel.history(limit=limit):
            if msg.author == bot.user:
                await msg.delete()
    except Exception as e:
        print("Błąd podczas usuwania starych wiadomości:", e)

# ---- Playwright scraper + screenshots ----
# returns list of file paths to screenshots (in tmp files) or None
async def fetch_and_screenshot_tiles(url="https://deltaforcetools.gg/daily-codes"):
    out_files = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ])
            page = await browser.new_page(
                viewport={"width": 1280, "height": 2000},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            )

            await page.goto(url, wait_until="networkidle", timeout=45000)

            # ✅ Czekamy dodatkowo aż JS przetworzy wyniki
            await page.wait_for_timeout(6000)

            # ✅ Scrollujemy stronę, żeby wymusić lazy-load
            for y in range(0, 5000, 500):
                await page.mouse.wheel(0, 500)
                await page.wait_for_timeout(500)

            # ✅ Listă możliwych selectorów kafelków
            selectors = [
                "div.col-lg-3.col-sm-6.mb-4",
                ".col-12.col-md-6.col-lg-4.col-xl-3",
                "article",
                ".card",
                ".tile",
                "span.greenText"
            ]

            elements = []
            for sel in selectors:
                found = await page.query_selector_all(sel)
                if len(found) > len(elements):
                    elements = found

            if elements:
                print(f"✅ Znaleziono {len(elements)} elementów — robimy screenshoty kafelków!")
                for i, el in enumerate(elements[:10]):
                    tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    path = tf.name
                    tf.close()
                    await el.screenshot(path=path)
                    out_files.append(path)
            else:
                # ❌ Brak kafelków — robimy screenshot całej strony
                print("⚠️ Brak elementów — wykonujemy fallback screenshot całej strony!")
                tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                path = tf.name
                tf.close()
                await page.screenshot(path=path, full_page=True)
                out_files.append(path)

            await browser.close()
            return out_files

    except Exception as e:
        print("❌ Playwright FATAL:", e)
        return None

# ---- Command: manual check ----
@bot.command(name="sprawdz")
async def cmd_sprawdz(ctx):
    await ctx.send("🔄 Generuję zrzuty kafelków (może potrwać kilka sekund)...")
    files = await fetch_and_screenshot_tiles()
    if not files:
        return await ctx.send("❌ Nie udało się pobrać kafelków / zrzutów 😕")

    # usuń stare wiadomości bota w kanale
    await delete_old_bot_messages(ctx.channel)

    # wyślij każdy obrazek jako osobny plik (wariant A)
    for path in files:
        try:
            await ctx.send(file=discord.File(path))
        except Exception as e:
            print("Błąd wysyłania obrazka:", e)
    await ctx.send(f"✅ Wysłano {len(files)} kafelków.")
    # cleanup temp files
    for p in files:
        try:
            os.remove(p)
        except:
            pass

# ---- Daily job (01:00 UTC) ----
async def seconds_until_next_utc_run(hour_utc=1, minute_utc=0):
    now = datetime.now(timezone.utc)
    target = now.replace(hour=hour_utc, minute=minute_utc, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return (target - now).total_seconds()

@tasks.loop(hours=24)
async def daily_job():
    # runs every 24h but we'll start it at the right time on_ready
    if not CHANNEL_ID:
        print("⚠️ CHANNEL_ID not set — daily_job will skip sending.")
        return

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("⚠️ Nie znaleziono kanału (daily_job).")
        return

    print("⏳ daily_job: robimy screenshoty...")
    files = await fetch_and_screenshot_tiles()
    if not files:
        try:
            await channel.send("⚠️ Autosprawdzenie — nie udało się pobrać kafelków.")
        except:
            pass
        return

    # usuń stare wiadomości
    await delete_old_bot_messages(channel)

    # wyślij kafelki, każdy osobno
    for path in files:
        try:
            await channel.send(file=discord.File(path))
        except Exception as e:
            print("Błąd wysyłania pliku w daily_job:", e)

    # send a small footer message with timestamp
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        await channel.send(f"🎯 Daily Codes — aktualizacja: {now}")
    except:
        pass

    # cleanup
    for p in files:
        try:
            os.remove(p)
        except:
            pass

# ---- on_ready: schedule the first run at next 01:00 UTC ----
@bot.event
async def on_ready():
    print(f"✅ Bot zalogowany jako: {bot.user}")
    # start daily_job at the exact 01:00 UTC
    wait = await seconds_until_next_utc_run(1, 0)
    print(f"⏳ Poczekam {int(wait)}s do pierwszego uruchomienia daily_job o 01:00 UTC")
    async def starter():
        await asyncio.sleep(wait)
        await daily_job()
        daily_job.start()
    bot.loop.create_task(starter())

# ---- Keep-alive Flask app so Railway doesn't stop container ----
app = Flask("df_bot_keepalive")
@app.route("/")
def home():
    return "DeltaForceDailyCodes bot is running."

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# start webserver in thread
Thread(target=run_web, daemon=True).start()

# 🔄 Anti-idle ping co 30 sekund
async def keepalive():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            async with aiohttp.ClientSession() as session:
                await session.get("https://deltaforce-discord-bot-production.up.railway.app")  # <- zmienimy za chwilę
        except:
            pass
        await asyncio.sleep(30)

@bot.event
async def on_disconnect():
    print("⚠️ BOT DISCONNECTED — trying to reconnect...")

@bot.event
async def on_resume():
    print("✅ Reconnected successfully!")
    
bot.loop.create_task(keepalive())

# ---- Run the bot ----
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)














