# bot.py (final)
import os
import asyncio
import tempfile
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
async def delete_old_bot_messages(channel, limit=50):
    try:
        async for msg in channel.history(limit=limit):
            if msg.author == bot.user:
                await msg.delete()
    except Exception as e:
        print("Błąd podczas usuwania starych wiadomości:", e)

# ---------------- Playwright scraper + screenshots ----------------
# returns list of temp file paths (screenshots) or None
import asyncio
from playwright.async_api import async_playwright

async def fetch_and_screenshot_tiles():
    url = "https://deltaforcetools.gg"
    output_file = "daily_codes.png"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1600, "height": 1200})

        print("🌍 Otwieram stronę...")
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(5)  # pozwól stronie się załadować

        # przewiń trochę w dół żeby sekcja się pojawiła
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await asyncio.sleep(2)

        print("🔎 Szukam sekcji 'Daily Codes'...")
        # znajdź sekcję po nagłówku tekstowym
        section = await page.query_selector("text=Daily Codes")

        if not section:
            print("❌ Nie znaleziono sekcji 'Daily Codes'")
            await browser.close()
            return None

        # znajdź nadrzędny kontener sekcji (czyli div, w którym jest ten nagłówek)
        container = await section.evaluate_handle("node => node.closest('section') || node.parentElement")

        if not container:
            print("❌ Nie znaleziono kontenera sekcji.")
            await browser.close()
            return None

        # przewiń do widoku i zrób screenshot tylko tej sekcji
        await container.scroll_into_view_if_needed()
        await asyncio.sleep(1)
        await container.screenshot(path=output_file)

        print(f"✅ Zrzut sekcji zapisany jako {output_file}")
        await browser.close()
        return [output_file]



# ---------------- Commands ----------------
@bot.command(name="sprawdz")
async def cmd_sprawdz(ctx):
    info_msg = await ctx.send("🔄 Generuję zrzut sekcji **Daily Codes** (może potrwać kilka sekund)...")
    
    files = await fetch_and_screenshot_tiles()
    if not files:
        try:
            await info_msg.edit(content="❌ Nie udało się pobrać sekcji / zrzutu 😕 — sprawdź logi.")
        except:
            pass
        return

    # usuń stare wiadomości bota
    await delete_old_bot_messages(ctx.channel)

    # usuń komunikat informacyjny bez błędu jeśli już nie istnieje
    try:
        await info_msg.delete()
    except discord.NotFound:
        pass

    # wyślij pojedynczy zrzut ekranu
    try:
        await ctx.send(file=discord.File(files[0]))
    except Exception as e:
        print("Błąd wysyłania pliku:", e)

    # usuń plik tymczasowy
    try:
        os.remove(files[0])
    except:
        pass


# ---------------- Daily scheduler ----------------
async def seconds_until_next_utc_run(hour_utc=1, minute_utc=0):
    now = datetime.now(timezone.utc)
    target = now.replace(hour=hour_utc, minute=minute_utc, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()

@tasks.loop(hours=24)
async def daily_job():
    if not CHANNEL_ID:
        print("⚠️ CHANNEL_ID not set — daily_job will skip sending.")
        return

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("⚠️ Nie znaleziono kanału (daily_job).")
        return

    print("⏳ daily_job: robimy screenshoty...")
    files = await fetch_tiles()
    if not files:
        try:
            await channel.send("⚠️ Autosprawdzenie — nie udało się pobrać kafelków.")
        except:
            pass
        return

    await delete_old_bot_messages(channel)

    for path in files:
        try:
            await channel.send(file=discord.File(path))
        except Exception as e:
            print("Błąd wysyłania pliku w daily_job:", e)
        try:
            os.remove(path)
        except:
            pass

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        await channel.send(f"🎯 Daily Codes — aktualizacja: {now}")
    except:
        pass

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

# ---------------- Async keepalive ping ----------------
async def keepalive_ping():
    await bot.wait_until_ready()
    # ping PUBLIC_URL to keep Railway happy
    async with aiohttp.ClientSession() as session:
        while not bot.is_closed():
            try:
                await session.get(PUBLIC_URL, timeout=10)
            except Exception:
                pass
            await asyncio.sleep(30)

# ---------------- Setup hook -> start web + keepalive + scheduler ----------------
@bot.event
async def setup_hook():
    # start keep-alive webserver thread
    start_web_thread()
    print("✅ Keepalive webserver started (Flask thread).")

    # start async keepalive pinger
    asyncio.create_task(keepalive_ping())
    print("✅ Keepalive pinger started.")

    # schedule first daily run at next 01:00 UTC and then start loop
    async def starter():
        wait = await seconds_until_next_utc_run(1, 0)
        print(f"⏳ First daily_job will run in {int(wait)}s (-> 01:00 UTC)")
        await asyncio.sleep(wait)
        # run once now
        await daily_job()
        # then start the loop every 24h
        daily_job.start()
    asyncio.create_task(starter())

# ---------------- Run bot ----------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)



