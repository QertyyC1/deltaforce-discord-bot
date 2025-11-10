FROM python:3.11-slim

# Instalacja zależności systemowych
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

# ✅ Instalacja Playwrighta i Chromium z poprawnymi zależnościami
RUN pip install playwright && \
    python -m playwright install-deps chromium && \
    playwright install chromium

COPY . .

CMD ["python", "bot.py"]
