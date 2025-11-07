# Używamy oficjalnego obrazu Playwright z Pythonem + przeglądarkami
FROM mcr.microsoft.com/playwright/python:latest

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# Kopiuj pliki projektu
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# COPY reszty
COPY . /app

# Ustaw port (Railway)
ENV PORT 8080

# Uruchomienie
CMD ["python", "bot.py"]
