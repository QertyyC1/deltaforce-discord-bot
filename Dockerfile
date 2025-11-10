# ===============================
# 🐍 Python + Chromium + Playwright
# ===============================
FROM python:3.11-slim

# Instalacja niezbędnych pakietów systemowych
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg curl xvfb \
    libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxkbcommon0 libxcomposite1 libxrandr2 libxdamage1 libxext6 \
    libxfixes3 libpango-1.0-0 libcairo2 libasound2 fonts-liberation \
    libgbm1 libgtk-3-0 fonts-unifont fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Skopiowanie zależności i instalacja Pythona
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ✅ Zainstaluj Playwright i przeglądarki
RUN pip install playwright && \
    playwright install chromium && \
    mkdir -p /root/.cache/ms-playwright && \
    cp -r /usr/local/lib/python3.11/site-packages/playwright/driver/package/.local-browsers/* /root/.cache/ms-playwright/ || true

# Skopiuj resztę kodu aplikacji
COPY . .

# Port (jeśli Railway używa np. Flask)
EXPOSE 8080

CMD ["python", "bot.py"]
