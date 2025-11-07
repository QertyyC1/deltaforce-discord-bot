import os
import json
import re
import asyncio
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks
from bs4 import BeautifulSoup

# ---- Konfiguracja (ENV) ----
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
PERSIST_FILE = "last_codes.json"  # przechowuje ostatnie kody, żeby nie spamować

if not DISCORD_TOKEN:
    print("❌ Brak DISCORD_TOKEN w env. Ustaw zmienną środowiskową i restartuj.")
    # nie exitujemy — discord.py i tak zwróci błąd przy run

# ---- Intents ----
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---- Pomoc: zapisz/odczytaj ostatnie kody (persistencja) ----
def load_last_codes():
    try:
        with open(PERSIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_last_codes(codes):
    try:
        with open(PERSIST_FILE, "w", encoding="utf-8") as f:
            json.dump(codes, f)
    except Exception as e:
        print("⚠️ Nie udało się zapisać last_codes:", e)

# ---- Funkcja scrapująca (Playwright async) ----
def fetch_daily_codes():
    url = "https://deltaforcetools.gg"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()

            page.goto(url, timeout=30000)
            # ✅ Czekamy aż pokaże się ikonka prezentu (gift)
            page.wait_for_selector("svg[data-icon='gift']", timeout=15000)

            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")

        codes = []
        gift_cards = soup.select("div.flex-col span.font-bold")

        for span in gift_cards:
            text = span.get_text(strip=True)
            if text.isdigit():
                codes.append(text)

            if len(codes) >= 5:
                break

        if len(codes) >= 5:
            print("✅ Kody znalezione:", codes)
            return codes[:5]

        print("⚠️ Znaleziono za mało kodów:", codes)
        return None

    except Exception as e:
        print("❌ Błąd Playwright:", e)
        return None


# ---- Wysyłka kodów na Discord (embed) ----
async def send_codes_to_channel(codes, reason="Ręczne"):
    if not CHANNEL_ID:
        print("⚠️ CHANNEL_ID nie ustawione.")
        return False
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("⚠️ Nie znaleziono kanału o ID:", CHANNEL_ID)
        return False

    embed = discord.Embed(title="Daily Codes — DeltaForceTools", color=0x1abc9c)
    embed.set_footer(text=f"{reason} • {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    for i, c in enumerate(codes, start=1):
        embed.add_field(name=f"Kod #{i}", value=f"`{c}`", inline=False)

    await channel.send(embed=embed)
    return True

# ---- Komenda ręczna !sprawdz ----
@bot.command(name="sprawdz")
async def cmd_sprawdz(ctx):
    await ctx.send("🔄 Pobieram Daily Codes...")
    codes = await fetch_daily_codes()
    if not codes:
        await ctx.send("❌ Nie udało się pobrać kodów 😕")
        return

    # pokaż i zapis
    await send_codes_to_channel(codes, reason="Ręczne !sprawdz")
    save_last_codes(codes)

# ---- Zadanie: sprawdzaj raz dziennie o 01:00 Europe/Warsaw ----
async def wait_until_next_run(hour=1, minute=0, tz_name="Europe/Warsaw"):
    tz = ZoneInfo(tz_name)
    while True:
        now = datetime.now(tz)
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run = next_run + timedelta(days=1)
        wait_seconds = (next_run - now).total_seconds()
        return wait_seconds

@tasks.loop(hours=24)
async def daily_job():
    """Ta pętla uruchamia się codziennie — jednak aby wywołać ją dokładnie o 01:00 CET,
    będziemy ręcznie czekać podczas startu."""
    # w pętli tasks.loop(hours=24) wywoływana jest co 24h, ale wywołanie start() zaplanujemy na exact time.
    codes = await fetch_daily_codes()
    if not codes:
        # wysyłamy informację, że nie pobraliśmy
        if CHANNEL_ID:
            ch = bot.get_channel(CHANNEL_ID)
            if ch:
                await ch.send("⚠️ Autosprawdzenie — nie udało się pobrać kodów.")
        return

    # porównaj z ostatnimi zapisanymi, wysyłaj tylko jeśli inne
    last = load_last_codes()
    if codes != last:
        await send_codes_to_channel(codes, reason="Autoupdate 01:00")
        save_last_codes(codes)
    else:
        print("ℹ️ Kody takie same jak poprzednio — nie wysyłam.")

@bot.event
async def on_ready():
    print(f"✅ Bot zalogowany jako: {bot.user}")
    # start pętli codziennej dokładnie o 01:00 Europe/Warsaw
    # oblicz ile sekund do next run
    wait_seconds = await wait_until_next_run(1, 0, "Europe/Warsaw")
    print(f"⏳ Poczekam {int(wait_seconds)}s do pierwszego uruchomienia o 01:00 Europe/Warsaw")
    # odpalenie z opóźnieniem (nie blokuj event loop)
    async def starter():
        await asyncio.sleep(wait_seconds)
        # pierwszy raz
        await daily_job()
        # teraz uruchom loop, który robi job co 24h (tasks.loop hours=24)
        daily_job.start()
    bot.loop.create_task(starter())

# ---- Uruchomienie bota ----
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)












