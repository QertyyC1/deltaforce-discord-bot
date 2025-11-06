FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/
RUN pip install -r requirements.txt

# ✅ Instalacja Playwright
RUN playwright install chromium

COPY . /app/

CMD ["python", "bot.py"]
