"""Настройки бота из .env — загружаются один раз для всех модулей."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent

load_dotenv(
    ROOT / ".env",
    encoding="utf-8-sig",
    interpolate=False,
)

SECRETS_DIR = ROOT / ".secrets"
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Almaty")

# Язык сводок оценок, если пользователь не выбрал свой: kk или ru.
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "kk")

# Mini App: порт локального сервера (0 — не запускать).
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "8080") or 0)
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "127.0.0.1")
# Постоянный https-адрес Mini App (на сервере). Если пусто — см. WEBAPP_TUNNEL.
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()
# 1 — поднять временный Cloudflare Tunnel для теста с этого компьютера.
WEBAPP_TUNNEL = os.getenv("WEBAPP_TUNNEL", "0") == "1"


def db_settings() -> dict:
    return {
        "host": os.environ["DB_HOST"],
        "port": int(os.environ["DB_PORT"]),
        "dbname": os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "connect_timeout": 5,
    }


def ai_settings() -> dict:
    return {
        "api_key": os.environ["AI_API_KEY"],
        "base_url": os.environ["AI_BASE_URL"],
        "model": os.environ["AI_MODEL"],
    }


LOG_DIR = ROOT / "logs"


def setup_logging():
    """Лог в консоль и в logs/bot.log (до 4 файлов по 2 МБ).

    Файл остаётся после перезапуска — по нему можно разобрать,
    что случилось, когда консоль уже закрыта.
    """
    LOG_DIR.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_DIR / "bot.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), file_handler],
    )
    # Без этого httpx пишет в лог каждый запрос к ИИ.
    logging.getLogger("httpx").setLevel(logging.WARNING)
