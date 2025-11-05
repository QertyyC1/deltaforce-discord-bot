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

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

def fetch_daily_codes():
    url = "https://deltaforcetools.gg"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            print(f"❌ Błąd HTTP: {r.status_code}")
            return None
        
        soup = BeautifulSoup(r.text, "html5lib")

        section = soup.find("h2", text=lambda x: x and "Daily Codes" in x)
        if not section:
            print("⚠️ Nie znaleziono nagłówka 'Daily Codes'")
            return None

        container = section.find_next("div")
        code_elements = container.find_all("p")[:5]  # pierwsze 5 kodów

        codes = [c.text.strip() for c in code_elements if c.text.strip()]
        return codes

    except Exception as e:
        print(f"❌ Błąd scrapowania: {e}")
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

    msg = "✅ Dzisiejsze kody Fortnite:\n"
    msg += "\n".join([f"• `{code}`" for code in codes])
    await ctx.send(msg)


@tasks.loop(minutes=10)
async def check_codes():
    if not CHANNEL_ID:
        print("❌ Brak CHANNEL_ID w env!")
        return

    channel = bot.get_channel(int(CHANNEL_ID))
    if not channel:
        print("❌ Nie mogę znaleźć kanału!")
        return

    now = datetime.utcnow().strftime("%H:%M")
    await channel.send(f"⏰ Auto-check ({now} UTC) — użyj `!sprawdz`")


bot.run(TOKEN)










