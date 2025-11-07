# Official Playwright image (ma już zainstalowane przeglądarki)
FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

# Skopiuj tylko requirements najpierw (cache build)
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Skopiuj resztę kodu
COPY . /app/

# (Opcjonalnie) ustaw zmienne środowiskowe build-time jeśli potrzebujesz
CMD ["python", "bot.py"]
