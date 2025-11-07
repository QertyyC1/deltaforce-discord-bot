# bot.py — final, poprawiony
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
async def fetch_and_screenshot_tiles(url="https://deltaforcetools.gg"):
    out_files = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ])
            page = await browser.new_page(viewport={"width": 1280, "height": 2000})
            # udawaj normalną przeglądarkę
            await page.set_extra_http_headers({"Accept-Language": "en,en-US;q=0.9,pl;q=0.8"})
            await page.goto(url, wait_until="networkidle", timeout=45000)

            # dajemy trochę czasu na JS
            await page.wait_for_timeout(4000)

            # scrollujemy, żeby wymusić lazy-load
            for _ in range(6):
                await page.mouse.wheel(0, 800)
                await page.wait_for_timeout(400)

            # lista selektorów próbnych — wybieramy ten który zwróci najwięcej elementów
            selectors = [
                "div.col-lg-3.col-sm-6.mb-4",        # oryginalny bootstrap-like
                ".col-12.col-md-6.col-lg-4.col-xl-3",
                "article",
                ".card",
                ".tile",
                "div[data-role='tile']",
                ".daily-card",
                "span.greenText",                    # elementy tekstowe wskazywane wcześniej
                "div[class*='tile']",
            ]

            best = []
            best_sel = None
            for sel in selectors:
                try:
                    found = await page.query_selector_all(sel)
                    if found and len(found) > len(best):
                        best = found
                        best_sel = sel
                except Exception:
                    continue

            elements = best

            # Jeśli nic nie znaleziono, spróbuj znaleźć elementy zawierające cyfry (p/ spans)
            if not elements:
                print("⚠️ Nie znaleziono standardowych kafelków, próbuję elementów z cyframi...")
                cand = await page.query_selector_all("p, span, div")
                filtered = []
                for el in cand:
                    try:
                        txt = (await el.inner_text()).strip()
                        # krótka heurystyka: liczba 3-7 cyfr
                        import re
                        if re.search(r"\b\d{3,7}\b", txt):
                            filtered.append(el)
                    except Exception:
                        continue
                elements = filtered

            if not elements:
                # fallback: zrób full page screenshot
                print("⚠️ Brak elementów — wykonuję full page screenshot fallback")
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                await page.screenshot(path=tmp, full_page=True)
                out_files.append(tmp)
                await browser.close()
                return out_files

            # ogranicz do 5 (u Ciebie jest 5 kafelków)
            take = min(len(elements), 5)
            for i in range(take):
                el = elements[i]
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                try:
                    await el.screenshot(path=tmp)
                except Exception:
                    # fallback: screenshot bounding box via element screenshot may fail: screenshot region
                    try:
                        box = await el.bounding_box()
                        if box:
                            tmp2 = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                            await page.screenshot(path=tmp2, clip={"x": box["x"], "y": box["y"], "width": box["width"], "height": box["height"]})
                            tmp = tmp2
                    except Exception:
                        # as last resort do element.inner_text into a small image? (skip)
                        pass
                out_files.append(tmp)

            await browser.close()
            print(f"✅ Utworzono {len(out_files)} screenshotów")
            return out_files

    except Exception as e:
        print("❌ Playwright error (fetch_and_screenshot_tiles):", e)
        return None

# ---------------- Commands ----------------
@bot.command(name="sprawdz")
async def cmd_sprawdz(ctx):
    await ctx.send("🔄 Generuję zrzuty kafelków (może potrwać kilka sekund)...")
    files = await fetch_and_screenshot_tiles()
    if not files:
        return await ctx.send("❌ Nie udało się pobrać kafelków / zrzutów 😕")

    # usuń stare wiadomości bota
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
