import os
import discord
import asyncio
import requests
import re
from bs4 import BeautifulSoup
from discord.ext import commands, tasks
from datetime import datetime
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot działa ✅"

def run_web():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))


TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

last_codes = []

def fetch_daily_codes():
    try:
        response = requests.get("https://deltaforcetools.gg", timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        codes = []
        for span in soup.find_all("span", class_="greenText"):
            text = span.get_text(strip=True)
            if text.isdigit() and len(text) == 4:
                codes.append(text)

        return codes if codes else None

    except Exception as e:
        print("❌ fetch_daily_codes ERROR:", e)
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

# Włączamy webserver, aby Railway nie ubijał kontenera
Thread(target=run_web).start()
bot.run(TOKEN)












