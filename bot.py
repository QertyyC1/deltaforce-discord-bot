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
    """
    Pobiera 5 kodów spod nagłówka "Daily Codes" na stronie https://deltaforcetools.gg
    Zwraca listę stringów (kodów) lub None przy błędzie.
    """
    url = "https://deltaforcetools.gg"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            print(f"❌ Błąd HTTP podczas pobierania strony: {r.status_code}")
            return None

        soup = BeautifulSoup(r.text, "html5lib")

        # Znajdź nagłówek "Daily Codes"
        header = soup.find(lambda tag: tag.name in ["h1", "h2", "h3"] and "Daily Codes" in tag.get_text())
        if not header:
            print("⚠️ Nie znaleziono nagłówka 'Daily Codes' na stronie.")
            return None

        # Zbierz teksty kolejnych siblings aż do następnego nagłówka (h1/h2/h3) lub limitu
        texts = []
        for sib in header.find_next_siblings():
            if sib.name and sib.name.lower() in ["h1", "h2", "h3"]:
                break
            txt = sib.get_text(separator="\n", strip=True)
            if txt:
                # rozbijamy po nowych liniach, bo elementy mogą zawierać kilka wierszy
                for line in txt.splitlines():
                    line = line.strip()
                    if line:
                        texts.append(line)

            # klauzula bezpieczeństwa: nie zbieraj zbyt dużo
            if len(texts) > 100:
                break

        # Na stronie każdy rekord to: nazwa_mapy, kod, data, godzina (4 linie)
        codes = []
        i = 0
        while i + 1 < len(texts):
            # zabezpieczenie: jeśli nie pasuje idealnie w grupy po 4, spróbujemy wyłuskać liczbowy kod
            map_name = texts[i]
            code_candidate = texts[i + 1]
            # kod powinien być krótkim ciągiem cyfr (np. '5364' lub z zerami)
            # jeżeli code_candidate zawiera cyfry, weźmy pierwsze słowo zawierające cyfry
            import re
            m = re.search(r"\d{2,}", code_candidate)
            if m:
                codes.append(m.group(0))
                i += 4  # przejdź do następnej grupy (mapa, kod, data, godzina)
            else:
                # jeśli nie pasuje, przesuwamy o 1 i próbujemy dalej (tolerancyjnie)
                i += 1

            if len(codes) >= 5:
                break

        if not codes:
            print("⚠️ Nie udało się wyciągnąć żadnego kodu z tekstów:", texts[:20])
            return None

        return codes[:5]

    except Exception as e:
        print("❌ Błąd podczas scrapowania:", e)
        return None


@bot.event
async def on_ready():
    print(f"✅ Bot zalogowany jako: {bot.user}")
    # startujemy automatyczne sprawdzanie (jeśli chcesz, możesz zmienić interwał)
    check_codes.start()


@bot.command()
async def sprawdz(ctx):
    """Ręczne pobranie i wysłanie Daily Codes"""
    await ctx.send("🔄 Pobieram Daily Codes...")

    codes = fetch_daily_codes()
    if not codes:
        await ctx.send("❌ Nie udało się pobrać kodów! 😕")
        return

    msg = "**✅ Dzisiejsze kody DeltaForceTools:**\n"
    for idx, code in enumerate(codes, start=1):
        msg += f"• Kod {idx}: `{code}`\n"
    await ctx.send(msg)


@tasks.loop(minutes=20)
async def check_codes():
    """Automatyczne przypomnienie co 20 minut (zmień jeśli chcesz)."""
    if not CHANNEL_ID:
        print("❌ Brak CHANNEL_ID w zmiennych środowiskowych.")
        return

    channel = bot.get_channel(int(CHANNEL_ID))
    if not channel:
        print("❌ Nie mogę znaleźć kanału o ID:", CHANNEL_ID)
        return

    # tylko informacyjne autosprawdzenie, możesz zastąpić wysyłką kodów bezpośrednio
    now = datetime.utcnow().strftime("%H:%M")
    await channel.send(f"⏰ Auto-check ({now} UTC) — użyj `!sprawdz`")


bot.run(TOKEN)










