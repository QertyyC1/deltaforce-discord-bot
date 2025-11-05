import os
import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
from datetime import datetime

TOKEN = os.getenv("TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not TOKEN:
    print("❌ Debug: TOKEN brak zmiennej środowiskowej!")
else:
    print(f"✅ Debug: TOKEN OK length={len(TOKEN)} preview={TOKEN[:4]}...{TOKEN[-4:]}")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

def fetch_daily_codes():
    url = "https://deltaforcetools.gg"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            print(f"❌ Błąd HTTP podczas pobierania strony: {r.status_code}")
            return None

        soup = BeautifulSoup(r.text, "html5lib")

        # Znajdź nagłówek „Daily Codes”
        header = soup.find("h2", string=lambda s: s and "Daily Codes" in s)
        if not header:
            print("⚠️ Nie znaleziono nagłówka 'Daily Codes'")
            return None

        # Następne elementy — zazwyczaj <div> lub sekcja z listą
        container = header.find_next_sibling()
        if not container:
            print("⚠️ Nie znaleziono kontenera po nagłówku")
            return None

        # Zbierz wszystkie bloki tekstu w tym kontenerze
        texts = []
        for el in container.find_all(recursive=False):
            txt = el.get_text(strip=True)
            if txt:
                texts.append(txt)

        # texts zawiera naprzemienne: mapa, kod, data, godzina
        codes = []
        import re
        for txt in texts:
            # szukamy ciągu cyfr minimum 2 cyfry
            m = re.search(r"\b\d{2,}\b", txt)
            if m:
                codes.append(m.group(0))
            if len(codes) >= 5:
                break

        if not codes:
            print("⚠️ Nie udało się wyciągnąć żadnych kodów z tekstów:", texts[:10])
            return None

        return codes[:5]

    except Exception as e:
        print("❌ Błąd podczas scrapowania:", e)
        return None

@bot.event
async def on_ready():
    print(f"✅ Bot zalogowany jako: {bot.user}")
    check_codes.start()

@bot.command()
async def sprawdz(ctx):
    await ctx.send("🔄 Pobieram Daily Codes...")

    codes = fetch_daily_codes()
    if not codes:
        await ctx.send("❌ Nie udało się pobrać kodów! 😕")
        return

    msg = "**✅ Dzisiejsze Daily Codes:**\n"
    for idx, code in enumerate(codes, start=1):
        msg += f"• Kod {idx}: `{code}`\n"
    await ctx.send(msg)

@tasks.loop(hours=24)
async def check_codes():
    if not CHANNEL_ID:
        print("❌ Brak CHANNEL_ID w zmiennych środowiskowych.")
        return

    channel = bot.get_channel(int(CHANNEL_ID))
    if not channel:
        print("❌ Nie mogę znaleźć kanału o ID:", CHANNEL_ID)
        return

    now = datetime.utcnow().strftime("%H:%M UTC")
    codes = fetch_daily_codes()
    if codes:
        msg = "**🕒 Auto-Daily Codes:**\n" + "\n".join([f"• `{code}`" for code in codes])
        await channel.send(msg)
    else:
        await channel.send(f"⚠️ Autosprawdzenie ({now}) — nie udało się pobrać kodów!")

bot.run(TOKEN)









