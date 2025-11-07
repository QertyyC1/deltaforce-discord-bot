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
        "Accept-Language": "pl,en;q=0.8",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        # 1) Najpierw: znajdź nagłówek "Daily Codes" i szukaj liczb tylko w jego sekcji
        header = soup.find(lambda t: t.name in ("h1","h2","h3") and t.get_text(strip=True).lower().find("daily codes") != -1)
        if header:
            section_texts = []
            for sib in header.find_next_siblings():
                # przerwij jak trafimy na kolejny nagłówek (koniec sekcji)
                if sib.name and sib.name.lower() in ("h1","h2","h3"):
                    break
                section_texts.append(sib.get_text(" ", strip=True))
                # ograniczenie bezpieczeństwa
                if len(" ".join(section_texts)) > 4000:
                    break
            section_blob = " ".join(section_texts)
            found = re.findall(r"\b\d{3,12}\b", section_blob)  # liczby 3-12 cyfr
            if found:
                # usuń duplikaty zachowując kolejność
                uniq = []
                for x in found:
                    if x not in uniq:
                        uniq.append(x)
                    if len(uniq) >= 5:
                        break
                if uniq:
                    return uniq[:5]

        # 2) Fallback: szukaj "kafelków" (bootstrap classes) — często używane przez stronę
        cards = soup.select("div.col-lg-3.col-sm-6.mb-4")
        if cards:
            codes = []
            for card in cards:
                text = card.get_text(" ", strip=True)
                m = re.search(r"\b\d{3,12}\b", text)
                if m:
                    codes.append(m.group(0))
                if len(codes) >= 5:
                    break
            if codes:
                return codes[:5]

        # 3) Fallback: span z font-bold (często pokazuje sam kod)
        bolds = soup.select("span.font-bold, strong")
        if bolds:
            codes = []
            for b in bolds:
                t = b.get_text(strip=True)
                if re.fullmatch(r"\d{3,12}", t):
                    codes.append(t)
                else:
                    m = re.search(r"\b\d{3,12}\b", t)
                    if m:
                        codes.append(m.group(0))
                if len(codes) >= 5:
                    break
            if codes:
                return codes[:5]

        # 4) Ostateczny fallback: przeszukaj sekcję main/ body, ale filtruj kontekstami (unikaj nagłówków statystyk)
        possible = []
        for tag in soup.find_all(["p","span","div"]):
            text = tag.get_text(" ", strip=True)
            # odrzucaj ciągi które wyglądają jak duże id (np. page counters) — heurystyka
            matches = re.findall(r"\b\d{3,12}\b", text)
            for m in matches:
                # odrzucaj jeśli tekst zawiera słowa typu "views","members","online","players" (statystyki)
                ctx = text.lower()
                if any(k in ctx for k in ("views","members","online","players","users","subscribers","votes")):
                    continue
                possible.append(m)
            if len(possible) >= 20:
                break
        if possible:
            # wybierz unikalne i pierwsze 5
            uniq = []
            for x in possible:
                if x not in uniq:
                    uniq.append(x)
                if len(uniq) >= 5:
                    break
            if uniq:
                return uniq[:5]

        # nic nie znaleziono
        return None

    except Exception as e:
        print("Błąd pobierania kodów (fetch_daily_codes):", e)
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









