# Образ с Python и Chromium нужной версии Playwright.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    PLATONUS_SHOW_BROWSER=0

CMD ["python", "bot.py"]
