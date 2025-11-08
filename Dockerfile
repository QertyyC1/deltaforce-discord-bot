FROM python:3.11-slim

# Instalacja systemowych zależności (dla Playwright)
RUN apt-get update && apt-get install -y wget gnupg libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 libxcomposite1 libxrandr2 libxdamage1 libxext6 libxfixes3 libpango-1.0-0 libcairo2 libasound2 fonts-liberation libgbm1 libgtk-3-0 curl xvfb

# Instalacja zależności projektu
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pobranie Chromium przez Playwright
RUN playwright install --with-deps chromium

COPY . .

CMD ["python", "bot.py"]
