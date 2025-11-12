# bot.py (fixed & improved)
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


# ---------------- Screenshot helper ----------------
async def make_daily_codes_screenshot():
    """Tworzy screenshot sekcji Daily Codes i zwraca ścieżkę do pliku."""
    SCREEN_X = 265
    SCREEN_Y = 900
    SCREEN_WIDTH = 1920
    SCREEN_HEIGHT = 350
    SCROLL_Y = 900
    WAIT_BEFORE_SCREEN = 3

    screenshot_path = "daily_codes_section.png"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 2000})

        print("🌍 Otwieram stronę deltaforcetools.gg ...")
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

    print("✅ Screenshot gotowy:", screenshot_path)
    return screenshot_path


# ---------------- Command: !sprawdz ----------------
@bot.command(name="sprawdz")
async def cmd_sprawdz(ctx):
    await ctx.send("🔄 Pobieram sekcję **Daily Codes**...")

    try:
        screenshot_path = await make_daily_codes_screenshot()
        await ctx.send("✅ Oto aktualne **Daily Codes** 👇", file=discord.File(screenshot_path))
        os.remove(screenshot_path)
    except Exception as e:
        await ctx.send(f"❌ Błąd: `{e}`")
        import traceback; traceback.print_exc()


# ---------------- Auto daily check (00:10 Polish time) ----------------
@tasks.loop(minutes=1)
async def daily_codes_task():
    # Czas polski = UTC+1 zimą / UTC+2 latem — poniżej przeliczenie
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    now_pl = now_utc + timedelta(hours=1)  # zmień na 2h latem, jeśli potrzeba

    if now_pl.hour == 0 and now_pl.minute == 10:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            print("⚠️ Nie znaleziono kanału do wysłania screena.")
            return

        print("🕛 Godzina 00:10 PL — wysyłam Daily Codes!")

        try:
            await channel.send("🔄 Pobieram sekcję Daily Codes...")
            screenshot_path = await make_daily_codes_screenshot()

            # usuń poprzednie wiadomości bota
            async for msg in channel.history(limit=50):
                if msg.author == bot.user:
                    try:
                        await msg.delete()
                    except:
                        pass

            await channel.send("✅ Oto aktualne **Daily Codes** 👇", file=discord.File(screenshot_path))
            os.remove(screenshot_path)
            print("✅ Daily Codes wysłane pomyślnie.")

        except Exception as e:
            print("❌ Błąd podczas automatycznego wysyłania:", e)


@daily_codes_task.before_loop
async def before_task():
    await bot.wait_until_ready()
    print("🕒 Zadanie automatycznego wysyłania Daily Codes uruchomione...")


# ---------------- Keepalive webserver ----------------
app = Flask("df_bot_keepalive")

@app.route("/")
def home():
    return "✅ DeltaForceDailyCodes bot działa."

def run_web():
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, threaded=True)

def start_web_thread():
    Thread(target=run_web, daemon=True).start()


# ---------------- Keepalive pinger ----------------
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
    asyncio.create_task(keepalive_ping())
    daily_codes_task.start()
    print("✅ Bot w pełni gotowy — codzienne auto wysyłanie aktywne.")


# ---------------- Run bot ----------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
