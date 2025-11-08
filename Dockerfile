FROM python:3.11-slim

# Instalacja niezbędnych zależności systemowych dla Playwright / Chromium
RUN apt-get update && apt-get install -y \
    wget gnupg curl \
    libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxkbcommon0 libxcomposite1 libxrandr2 libxdamage1 libxext6 libxfixes3 \
    libpango-1.0-0 libcairo2 libasound2 fonts-liberation libgbm1 libgtk-3-0 \
    xvfb fonts-liberation fonts-unifont && \
    rm -rf /var/lib/apt/lists/*

# Instalacja zależności projektu
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalacja Chromium przez Playwright (bez --with-deps)
RUN playwright install chromium

COPY . .

CMD ["python", "bot.py"]
