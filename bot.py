# bot.py — final, poprawiony
import os
import asyncio
import tempfile
import aiohttp
import discord
from datetime import datetime, timedelta, timezone
from threading import Thread
from playwright.async_api import async_playwright
from discord.ext import commands, tasks
from flask import Flask

# ---------------- Config ----------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
# domyślnie użyj ID które podałeś; można nadpisać przez zmienną CHANNEL_ID
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "1436296685788729415"))
# publiczny URL Railway (używany do keepalive). Możesz ustawić w env PUBLIC_URL.
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
# returns list of temp file paths or None

async def fetch_tiles():
    url = "https://deltaforcetools.gg"
    print(f"[DEBUG] Otwieram stronę: {url}")

    async with async_playwright() as p:
        # Uruchamiamy Chromium z odpowiednimi argumentami
        browser = await p.chromium.launch(
            headless=True,  # Możesz dać False, jeśli chcesz zobaczyć co się dzieje
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu"
            ]
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        page = await context.new_page()

        try:
            # Wejście na stronę
            await page.goto(url, timeout=60000)
            await page.wait_for_load_state("networkidle")
            print("[DEBUG] Strona załadowana")

            # Scrollowanie do dołu kilka razy (lazy-load)
            for i in range(5):
                await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

            # Czekamy, aż kafelki się pojawią (zmień selektor jeśli inny)
            await page.wait_for_selector(".MuiPaper-root", timeout=10000)
            print("[DEBUG] Kafelki załadowane ✅")

            # Zrzut ekranu do debugowania
            await page.screenshot(path="screenshot.png", full_page=True)

            # Zapisujemy HTML (dla analizy błędów)
            html = await page.content()
            with open("debug.html", "w", encoding="utf-8") as f:
                f.write(html)

            # Pobieramy dane z kafelków
            tiles = await page.query_selector_all(".MuiPaper-root")
            results = []

            for tile in tiles:
                text = await tile.inner_text()
                results.append(text.strip())

            await browser.close()
            print(f"[DEBUG] Znaleziono {len(results)} kafelków")
            return results

        except Exception as e:
            print(f"[ERROR] Nie udało się pobrać kafelków: {e}")
            await page.screenshot(path="error.png", full_page=True)
            await browser.close()
            return None

# ---------------- Commands ----------------
@bot.command(name="sprawdz")
async def cmd_sprawdz(ctx):
    info_msg = await ctx.send("🔄 Generuję zrzuty kafelków (może potrwać do ~30s)...")
    files = await fetch_and_screenshot_tiles()
    if not files:
        await info_msg.edit(content="❌ Nie udało się pobrać kafelków / zrzutów 😕 — sprawdź logi (DEBUG HTML PREVIEW).")
        return

    # Jeśli fallback (full page) — oznacz w wiadomości i wyślij plik
    if len(files) == 1:
        # usuń stare
        await delete_old_bot_messages(ctx.channel)
        try:
            await ctx.send("⚠️ Wysyłam fallbackowy screenshot (co widzi bot). Jeśli nie widać kodów, skopiuj LOGi HTML i podeślij mi je.")
            await ctx.send(file=discord.File(files[0]))
        except Exception as e:
            print("Błąd wysyłania fallback screenshot:", e)
        try:
            os.remove(files[0])
        except:
            pass
        await info_msg.delete()
        return

    # normalny przypadek: wiele kafelków
    await delete_old_bot_messages(ctx.channel)
    for path in files:
        try:
            await ctx.send(file=discord.File(path))
        except Exception as e:
            print("Błąd wysyłania obrazka:", e)
        try:
            os.remove(path)
        except:
            pass
    await info_msg.delete()
    await ctx.send(f"✅ Wysłano {len(files)} kafelków.")

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

    files = await fetch_and_screenshot_tiles()
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


