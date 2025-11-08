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
    """
    Zwraca listę plików (screenshoty kafelków). Jako ostateczny fallback zawsze
    tworzy full-page screenshot i zapisuje HTML fragment do logów.
    """
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
            await page.set_extra_http_headers({"Accept-Language": "en,en-US;q=0.9,pl;q=0.8"})
            # dłuższy timeout i networkidle
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Dajemy JS więcej czasu
            await page.wait_for_timeout(8000)

            # Scroll powolny — wymusza lazy-load
            for _ in range(8):
                await page.mouse.wheel(0, 800)
                await page.wait_for_timeout(600)

            # Pobierz HTML i zaloguj pierwsze 4000 znaków (debug)
            try:
                html = await page.content()
                print("📄 DEBUG HTML PREVIEW (pierwsze 4000 znaków):")
                print(html[:4000])
                print("----- KONIEC PREVIEW -----")
            except Exception as e_html:
                print("⚠️ Nie udało się pobrać HTML preview:", e_html)
                html = ""

            # Próbne selektory (szukamy elementów, które wyglądają na kafelki)
            selectors = [
                "div.col-lg-3.col-sm-6.mb-4",
                ".col-12.col-md-6.col-lg-4.col-xl-3",
                "article",
                ".card",
                ".tile",
                "div[data-role='tile']",
                ".daily-card",
                "span.greenText",
                "div[class*='tile']",
            ]

            best = []
            for sel in selectors:
                try:
                    found = await page.query_selector_all(sel)
                    if found and len(found) > len(best):
                        best = found
                except Exception:
                    continue

            # jeśli niczego nie znaleziono, użyj heurystyki: elementy zawierające 3-7 cyfr
            elements = best
            if not elements:
                cand = await page.query_selector_all("p, span, div")
                filtered = []
                import re
                for el in cand:
                    try:
                        txt = (await el.inner_text()).strip()
                        if re.search(r"\b\d{3,7}\b", txt):
                            filtered.append(el)
                    except Exception:
                        continue
                elements = filtered

            # jeśli dalej pusto — fallback: full page screenshot + zwróć tylko ten plik
            if not elements:
                print("⚠️ Nie znaleziono kafelków — robię full-page screenshot fallback")
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                try:
                    await page.screenshot(path=tmp, full_page=True)
                    out_files.append(tmp)
                    # zapisz też HTML do pliku debugowego, żeby łatwiej pobrać
                    try:
                        with open("debug_deltaforce.html", "w", encoding="utf-8") as f:
                            f.write(html if html else await page.content())
                        print("📄 DEBUG: Zapisano debug_deltaforce.html")
                    except Exception as e:
                        print("⚠️ Nie udało się zapisać debug_deltaforce.html:", e)
                except Exception as e_s:
                    print("❌ Błąd robiąc full-page screenshot:", e_s)
                await browser.close()
                return out_files

            # W przeciwnym wypadku screenshoty elementów (max 5)
            take = min(len(elements), 5)
            for i in range(take):
                el = elements[i]
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                try:
                    await el.screenshot(path=tmp)
                except Exception:
                    # fallback: użyj bounding box
                    try:
                        box = await el.bounding_box()
                        if box:
                            tmp2 = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                            await page.screenshot(path=tmp2, clip={"x": box["x"], "y": box["y"], "width": box["width"], "height": box["height"]})
                            tmp = tmp2
                    except Exception as e_clip:
                        print("⚠️ Nie udało się screenshotować elementu:", e_clip)
                out_files.append(tmp)

            await browser.close()
            print(f"✅ Utworzono {len(out_files)} screenshotów kafelków")
            return out_files

    except Exception as e:
        print("❌ Playwright error (fetch_and_screenshot_tiles):", e)
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

