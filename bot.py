# bot.py
import os
import asyncio
import tempfile
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
    """
    Otwiera stronę z Playwright (async), czeka aż kafelki się pojawią,
    dla każdego kafelka robi screenshot elementu i zapisuje do temp file.
    Zwraca listę ścieżek do plików.
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
            page = await browser.new_page()
            # udawaj przeglądarkę
            await page.set_extra_http_headers({
                "Accept-Language": "en,pl;q=0.9"
            })
            await page.goto(url, timeout=30000)
            # Czekamy na pojawienie się kafelków — selector może się różnić, próbujemy kilku
            try:
                # standardowy kafelek używany wcześniej
                await page.wait_for_selector("div.col-lg-3.col-sm-6.mb-4", timeout=10000)
                card_selector = "div.col-lg-3.col-sm-6.mb-4"
            except Exception:
                # fallback do bardziej ogólnego selektora: elementy z green text
                try:
                    await page.wait_for_selector("span.greenText", timeout=8000)
                    # będziemy screenshotować rodzica span.greenText
                    card_selector = "span.greenText"
                except Exception:
                    # ostatnia deska ratunku: szukamy kafelków po aria roles / article
                    try:
                        await page.wait_for_selector("article, .card, .tile", timeout=8000)
                        card_selector = "article, .card, .tile"
                    except Exception as e:
                        print("❌ Nie znaleziono selektora kafelków:", e)
                        await browser.close()
                        return None

            # znajdź wszystkie elementy pasujące
            elements = await page.query_selector_all(card_selector)
            if not elements:
                print("⚠️ Brak elementów do screenshotowania.")
                await browser.close()
                return None

            # ograniczamy do 10 dla bezpieczeństwa (zwykle 5)
            max_take = min(len(elements), 10)
            for i in range(max_take):
                el = elements[i]
                # jeśli selektor to span.greenText - podejmij rodzica 3 poziomy w górę
                tag_name = await el.evaluate("(e) => e.tagName.toLowerCase()")
                if tag_name == "span":
                    # spróbuj użyć rodzica jako kafelka
                    parent = await el.evaluate_handle("(e) => e.closest('div') || e.parentElement")
                    # handle to element
                    try:
                        # create a temp file
                        tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                        path = tf.name
                        tf.close()
                        await parent.as_element().screenshot(path=path)
                        out_files.append(path)
                        await parent.dispose()
                    except Exception:
                        # fallback screenshot of element itself
                        tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                        path = tf.name
                        tf.close()
                        await el.screenshot(path=path)
                        out_files.append(path)
                else:
                    # normal screenshot
                    tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    path = tf.name
                    tf.close()
                    await el.screenshot(path=path)
                    out_files.append(path)

            await browser.close()
            return out_files

    except Exception as e:
        print("❌ Playwright error in fetch_and_screenshot_tiles:", e)
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
    port = int(os.getenv("PORT", "8080"))
    # flask in production is fine for keep-alive; Railway uses it only to keep container alive
    app.run(host="0.0.0.0", port=port)

# start webserver in thread
Thread(target=run_web, daemon=True).start()

# ---- Run the bot ----
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)










