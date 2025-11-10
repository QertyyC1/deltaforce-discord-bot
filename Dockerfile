# ===============================
# 1️⃣  Bazowy obraz z Pythonem
# ===============================
FROM python:3.11-slim

# ===============================
# 2️⃣  Instalacja zależności systemowych dla Playwright + Chromium
# ===============================
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg curl xvfb \
    libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxkbcommon0 libxcomposite1 libxrandr2 libxdamage1 libxext6 \
    libxfixes3 libpango-1.0-0 libcairo2 libasound2 fonts-liberation \
    libgbm1 libgtk-3-0 fonts-unifont \
    && rm -rf /var/lib/apt/lists/*

# ===============================
# 3️⃣  Ustawienie katalogu roboczego
# ===============================
WORKDIR /app

# ===============================
# 4️⃣  Instalacja zależności Pythona
# ===============================
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ===============================
# 5️⃣  Instalacja Playwrighta + Chromium
# ===============================
RUN pip install playwright && \
    python -m playwright install-deps chromium && \
    playwright install chromium

# ===============================
# 6️⃣  Skopiowanie kodu bota
# ===============================
COPY . .

# ===============================
# 7️⃣  Uruchomienie aplikacji
# ===============================
CMD ["python", "bot.py"]
