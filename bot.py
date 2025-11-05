import discord
from discord.ext import commands, tasks
from bs4 import BeautifulSoup
import requests
from datetime import time

TOKEN = "WSTAW_SWÓJ_TOKEN"
CHANNEL_ID = 1435569396394233856  # Twój kanał

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def get_daily_codes():
    try:
        url = "https://deltaforcetools.gg"
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        # Szukamy sekcji Daily Codes
        codes_section = soup.find("div", {"class": "code-grid"})
        codes = [item.text.strip() for item in codes_section.find_all("p")]

        if len(codes) >= 5:
            return codes[:5]
        else:
            return None
    except Exception as e:
        print("Błąd przy pobieraniu kodów:", e)
        return None


@bot.event
async def on_ready():
    print(f"✅ Bot zalogowany jako {bot.user}")
    daily_update.start()


@commands.is_owner()
@bot.command()
async def codes(ctx):
    codes = get_daily_codes()
    if codes:
        await ctx.send(
            "**🎯 Daily Codes:**\n"
            + "\n".join([f"> `{c}`" for c in codes])
        )
    else:
        await ctx.send("❌ Nie udało się pobrać aktualnych kodów.")


@tasks.loop(time=time(hour=1, minute=0, second=0))  # Wysyła o 01:00
async def daily_update():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ Nie znaleziono kanału!")
        return

    codes = get_daily_codes()
    if codes:
        await channel.send(
            "**📌 Daily Codes (Auto Update):**\n"
            + "\n".join([f"> `{c}`" for c in codes])
        )
    else:
        await channel.send("⚠️ Błąd podczas automatycznej aktualizacji kodów.")


bot.run(TOKEN)


