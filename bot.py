# bot.py (final)
import os
import asyncio
import tempfile
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

# ---------------- Helpers ----------------
async def delete_old_bot_messages(channel, limit=50):
    try:
        async for msg in channel.history(limit=limit):
            if msg.author == bot.user:
                await msg.delete()
    except Exception as e:
        print("Błąd podczas usuwania starych wiadomości:", e)

# ---------------- Playwright scraper + screenshots ----------------
# returns list of temp file paths (screenshots) or None
import asyncio
from playwright.async_api import async_playwright

async def fetch_and_screenshot_tiles():
    url = "https://deltaforcetools.gg"
    output_file = "daily_codes.png"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1600, "height": 1200})

        print("🌍 Otwieram stronę...")
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(5)  # pozwól stronie się załadować

        # przewiń trochę w dół żeby sekcja się pojawiła
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await asyncio.sleep(2)

        print("🔎 Szukam sekcji 'Daily Codes'...")
        # znajdź sekcję po nagłówku tekstowym
        section = await page.query_selector("text=Daily Codes")

        if not section:
            print("❌ Nie znaleziono sekcji 'Daily Codes'")
            await browser.close()
            return None

        # znajdź nadrzędny kontener sekcji (czyli div, w którym jest ten nagłówek)
        container = await section.evaluate_handle("node => node.closest('section') || node.parentElement")

        if not container:
            print("❌ Nie znaleziono kontenera sekcji.")
            await browser.close()
            return None

        # przewiń do widoku i zrób screenshot tylko tej sekcji
        await container.scroll_into_view_if_needed()
        await asyncio.sleep(1)
        await container.screenshot(path=output_file)

        print(f"✅ Zrzut sekcji zapisany jako {output_file}")
        await browser.close()
        return [output_file]



# ---------------- Commands ----------------
@bot.command(name="sprawdz")
async def cmd_sprawdz(ctx):
    import asyncio
    from playwright.async_api import async_playwright
    import discord
    import re
    import os

    # ==========================
    # 🔧 USTAWIENIA SCREENA
    # ==========================
    SCREEN_X = 270         # przesunięcie w poziomie (lewo-prawo)
    SCREEN_Y = 900         # przesunięcie w pionie (góra-dół)
    SCREEN_WIDTH = 1920    # szerokość zrzutu
    SCREEN_HEIGHT = 350    # wysokość zrzutu
    SCROLL_Y = 900         # pozycja scrolla strony
    WAIT_BEFORE_SCREEN = 3 # czas oczekiwania po przewinięciu (sekundy)
    # ==========================

    # Teksty które chcemy usuwać (dokładnie, bez gwiazdek)
    TARGETS = {
        "✅ Oto aktualne Daily Codes 👇",
        "🔄 Pobieram sekcję Daily Codes..."
    }

    # helper: normalizuje zawartość wiadomości (usuwa '*', trim)
    def normalize(s: str) -> str:
        if s is None:
            return ""
        return re.sub(r"\*", "", s).strip()

    # 1) usuń poprzednie wiadomości bota o podanych treściach
    try:
        async for message in ctx.channel.history(limit=100):
            if message.author == bot.user:
                norm = normalize(message.content)
                if norm in TARGETS:
                    try:
                        await message.delete()
                    except discord.NotFound:
                        pass
                    except Exception:
                        # nie przerywamy pętli, ale logujemy na konsoli
                        print("Błąd podczas usuwania starej wiadomości:", exc_info=True)
    except Exception as e:
        print("Błąd podczas przeglądania historii kanału:", e)

    # 2) wyślij komunikat pobierania (dokładnie taki, który potem chcemy usuwać)
    fetch_msg = None
    screenshot_path = "daily_codes_section.png"
    browser = None
    try:
        fetch_msg = await ctx.send("🔄 Pobieram sekcję Daily Codes...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1920, "height": 2000})

            await page.goto("https://deltaforcetools.gg", wait_until="networkidle")
            await asyncio.sleep(10)  # czekamy aż wszystko się załaduje

            # przewiń w okolice sekcji Daily Codes
            await page.evaluate(f"window.scrollTo(0, {SCROLL_Y})")
            await asyncio.sleep(WAIT_BEFORE_SCREEN)

            # zrób screenshot z wybranego obszaru
            await page.screenshot(
                path=screenshot_path,
                clip={
                    "x": SCREEN_X,
                    "y": SCREEN_Y,
                    "width": SCREEN_WIDTH,
                    "height": SCREEN_HEIGHT,
                },
            )

            # zamknij przeglądarkę
            await browser.close()
            browser = None

        # usuń komunikat "pobieram"
        try:
            if fetch_msg:
                await fetch_msg.delete()
        except discord.NotFound:
            pass
        except Exception:
            print("Błąd przy usuwaniu komunikatu pobierania.", exc_info=True)

        # wyślij rezultat (dokładny tekst, który będzie można potem usunąć)
        await ctx.send("✅ Oto aktualne Daily Codes 👇", file=discord.File(screenshot_path))

    except Exception as e:
        # jeśli coś się posypało — spróbuj usunąć komunikat pobierania i poinformuj użytkownika
        try:
            if fetch_msg:
                await fetch_msg.delete()
        except discord.NotFound:
            pass
        except Exception:
            print("Błąd przy usuwaniu komunikatu po wyjątku.", exc_info=True)

        await ctx.send(f"❌ Błąd: `{e}`")
        import traceback
        traceback.print_exc()

    finally:
        # cleanup: zamknij browser jeśli nadal otwarty
        try:
            if browser is not None:
                await browser.close()
        except Exception:
            pass

        # usuń plik screena z dysku, jeśli istnieje
        try:
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
        except Exception:
            print("Nie udało się usunąć pliku screena.", exc_info=True)


# ---------------- Keepalive webserver (Flask) ----------------
app = Flask("df_bot_keepalive")

@app.route("/")
def home():
    return "DeltaForceDailyCodes bot is running."

def run_web():
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, threaded=True)

def start_web_thread():
    Thread(target=run_web, daemon=True).start()

# ---------------- Async keepalive ping ----------------
async def keepalive_ping():
    await bot.wait_until_ready()
    # ping PUBLIC_URL to keep Railway happy
    async with aiohttp.ClientSession() as session:
        while not bot.is_closed():
            try:
                await session.get(PUBLIC_URL, timeout=10)
            except Exception:
                pass
            await asyncio.sleep(30)

# ---------------- Setup hook -> start web + keepalive + scheduler ----------------
@bot.event
async def setup_hook():
    # start keep-alive webserver thread
    start_web_thread()
    print("✅ Keepalive webserver started (Flask thread).")

    # start async keepalive pinger
    asyncio.create_task(keepalive_ping())
    print("✅ Keepalive pinger started.")

TARGET_CHANNEL_ID = 1436296685788729415  

@tasks.loop(minutes=1)
async def daily_codes_task():
    now = datetime.now()  # poprawione
    # log co minutę, żeby widzieć że działa
    print(f"[{now.strftime('%H:%M:%S')}] ⏱️ Sprawdzanie czasu dla auto-wysyłki...")

    # sprawdza czy jest 00:10
    if now.hour == 0 and now.minute == 10:
        print("🕛 Wysyłam automatycznie Daily Codes...")
        channel = bot.get_channel(TARGET_CHANNEL_ID)
        if channel:
            SCREEN_X = 270
            SCREEN_Y = 900
            SCREEN_WIDTH = 1920
            SCREEN_HEIGHT = 350
            SCROLL_Y = 900
            WAIT_BEFORE_SCREEN = 3

            await channel.send("🔄 Pobieram sekcję Daily Codes...")

            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page(viewport={"width": 1920, "height": 2000})
                    await page.goto("https://deltaforcetools.gg", wait_until="networkidle")
                    await asyncio.sleep(10)
                    await page.evaluate(f"window.scrollTo(0, {SCROLL_Y})")
                    await asyncio.sleep(WAIT_BEFORE_SCREEN)

                    screenshot_path = "daily_codes_section.png"
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
                    await channel.send("✅ Oto aktualne Daily Codes 👇", file=discord.File(screenshot_path))
                    os.remove(screenshot_path)
            except Exception as e:
                await channel.send(f"❌ Błąd: `{e}`")
                import traceback
                traceback.print_exc()


@daily_codes_task.before_loop
async def before_task():
    await bot.wait_until_ready()
    print("🕒 Uruchamiam automatyczne wysyłanie codziennych kodów...")

# start zadania po starcie bota
daily_codes_task.start()

# ---------------- Run bot ----------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)































