import os
import discord
import asyncio
import requests
import re
from bs4 import BeautifulSoup
from discord.ext import commands, tasks
from datetime import datetime

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

last_codes = []

def fetch_daily_codes():
    url = "https://deltaforcetools.gg"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en,pl;q=0.9"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1) Znajdź nagłówek "Daily Codes"
        header = soup.find(lambda t: t.name in ("h1","h2","h3") and "daily codes" in t.get_text(strip=True).lower())

        blob = ""
        if header:
            # zbieramy tekst kolejnych siblings (cała sekcja)
            parts = []
            for sib in header.find_next_siblings():
                if sib.name and sib.name.lower() in ("h1","h2","h3"):
                    break
                parts.append(sib.get_text(" ", strip=True))
                if len(" ".join(parts)) > 10000:
                    break
            blob = " ".join(parts)
        else:
            # fallback: pobierz cały body
            body = soup.body
            blob = body.get_text(" ", strip=True) if body else soup.get_text(" ", strip=True)

        # DEBUG (usuń/zakomentuj jeśli nie chcesz logów)
        print("DEBUG: Sekcja blob (pierwsze 1200 chars):")
        print(blob[:1200])
        print("----- KONIEC PODGLĄDU -----")

        # 2) Szukamy wzorca: <kod - 3..7 cyfr> następnie data YYYY/MM/DD
        pattern = re.compile(r"\b(\d{3,7})\b[\s\S]{0,60}?\b(20\d{2}/\d{2}/\d{2})\b")
        matches = pattern.findall(blob)

        codes = []
        for m in matches:
            code = m[0]
            if code not in codes:
                codes.append(code)
            if len(codes) >= 5:
                break

        # 3) Jeżeli nic nie znaleziono — dajemy ostateczny, bardziej liberalny fallback:
        if not codes:
            fallback = re.findall(r"\b\d{3,7}\b", blob)
            uniq = []
            for f in fallback:
                if f not in uniq:
                    uniq.append(f)
                if len(uniq) >= 5:
                    break
            codes = uniq

        if not codes:
            print("⚠️ fetch_daily_codes: nie znaleziono kodów.")
            return None

        print("✅ fetch_daily_codes -> znalezione:", codes[:5])
        return codes[:5]

    except Exception as e:
        print("❌ fetch_daily_codes EX:", e)
        return None


async def delete_old_bot_messages(channel, limit=50):
    """Usuwa poprzednie wiadomości bota aby nie było spamu"""
    try:
        async for msg in channel.history(limit=limit):
            if msg.author == bot.user:
                await msg.delete()
    except Exception as e:
        print("Błąd czyszczenia wiadomości:", e)


@bot.command()
async def sprawdz(ctx):
    await ctx.send("🔄 Pobieram Daily Codes...")
    codes = fetch_daily_codes()

    if codes:
        # Usuń stare wiadomości z kodami
        await delete_old_bot_messages(ctx.channel)

        msg = "\n".join(f"✅ Kod #{i+1}: `{code}`" for i, code in enumerate(codes))
        await ctx.send(msg)
    else:
        await ctx.send("❌ Nie udało się pobrać kodów 😕")


@tasks.loop(minutes=60)
async def auto_check():
    global last_codes

    if not CHANNEL_ID:
        return

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return

    codes = fetch_daily_codes()
    now = datetime.utcnow().strftime("%H:%M UTC")

    if not codes:
        await channel.send(f"⚠️ Auto-check {now} — błąd pobierania!")
        return

    if codes != last_codes:
        last_codes = codes

        # Usuń stare wiadomości zanim wyślesz nowe
        await delete_old_bot_messages(channel)

        msg = f"🎯 Nowe Daily Codes {now}\n" + "\n".join(f"✅ `{c}`" for c in codes)
        await channel.send(msg)

        print("✅ Wysłano nowe kody!")
    else:
        print("⏳ Brak zmian w kodach")


@bot.event
async def on_ready():
    print(f"✅ Bot zalogowany jako: {bot.user}")
    auto_check.start()


bot.run(TOKEN)










