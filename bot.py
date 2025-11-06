import os
import discord
import asyncio
from discord.ext import commands, tasks
from datetime import datetime
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

# ✅ Playwright Scraper
def fetch_daily_codes():
    url = "https://deltaforcetools.gg"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=25000)
            page.wait_for_timeout(3500)  # czekanie na JS

            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        p_tags = soup.find_all("p")

        codes = [p.get_text(strip=True) for p in p_tags if p.get_text(strip=True).isdigit()]
        return codes[:5] if len(codes) >= 5 else None

    except Exception as e:
        print("❌ Błąd Playwright:", e)
        return None


# ✅ Komenda "!sprawdz"
@bot.command()
async def sprawdz(ctx):
    await ctx.send("🔄 Pobieram Daily Codes...")
    codes = fetch_daily_codes()

    if codes:
        msg = "\n".join(f"✅ Kod #{i+1}: `{code}`" for i, code in enumerate(codes))
        await ctx.send(msg)
    else:
        await ctx.send("❌ Nie udało się pobrać kodów 😕")


# ✅ Auto-Check co godzinę
@tasks.loop(hours=1)
async def auto_check():
    if not CHANNEL_ID:
        return

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return

    codes = fetch_daily_codes()
    now = datetime.utcnow().strftime("%H:%M UTC")

    if codes:
        msg = f"⏰ Auto-check {now}\n" + "\n".join(f"✅ Kod #{i+1}: `{code}`" for i, code in enumerate(codes))
        await channel.send(msg)
    else:
        await channel.send(f"⚠️ Auto-check {now} — błąd pobierania!")


@bot.event
async def on_ready():
    print(f"✅ Bot zalogowany jako: {bot.user}")
    auto_check.start()


bot.run(TOKEN)










