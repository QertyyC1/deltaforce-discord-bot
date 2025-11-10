# ================================
# Stage 1: Python + Playwright Bot
# ================================
FROM python:3.11-slim

# Instalacja zależności systemowych potrzebnych do działania Chromium i Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg curl xvfb \
    libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxkbcommon0 libxcomposite1 libxrandr2 libxdamage1 libxext6 \
    libxfixes3 libpango-1.0-0 libcairo2 libasound2 fonts-liberation \
    libgbm1 libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ✅ Zainstaluj Playwright z poprawnymi zależnościami (bez błędnych czcionek)
RUN pip install playwright && \
    npx playwright install-deps chromium && \
    playwright install chromium

# Skopiuj cały projekt
COPY . .

# Domyślna komenda uruchomienia bota
CMD ["python", "bot.py"]
