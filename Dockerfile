FROM mcr.microsoft.com/playwright/python:latest

# ✅ Dodaj tę linię:
RUN apt-get update && apt-get install -y tzdata

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

CMD ["python", "bot.py"]
