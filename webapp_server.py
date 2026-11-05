"""Веб-сервер Mini App: страница и API с данными пользователя.

Кто открыл Mini App, сервер узнаёт по initData — строке, которую
Telegram подписывает токеном бота. Подделать её без токена нельзя,
поэтому каждый видит только свои данные.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiohttp import web

from config import ROOT

logger = logging.getLogger(__name__)

STATIC_DIR = ROOT / "webapp"

# Старше этого initData не принимаем — защита от повторного использования.
MAX_INIT_DATA_AGE = timedelta(hours=24)

# Адрес, по которому Mini App доступен из интернета (https).
_public_url: str | None = None
# Постоянный ли адрес. Адрес временного туннеля меняется
# при каждом перезапуске бота.
_url_is_stable = False


def public_url() -> str | None:
    return _public_url


def public_url_is_stable() -> bool:
    return _public_url is not None and _url_is_stable


def set_public_url(url: str | None, *, stable: bool = False):
    global _public_url, _url_is_stable
    _public_url = url
    _url_is_stable = stable


def telegram_user_id(bot_token: str, init_data: str) -> int:
    """ID пользователя из проверенного initData. ValueError — если подделка."""
    data = safe_parse_webapp_init_data(bot_token, init_data)

    if data.user is None:
        raise ValueError("В initData нет пользователя.")

    age = datetime.now(timezone.utc) - data.auth_date.astimezone(timezone.utc)

    if age > MAX_INIT_DATA_AGE:
        raise ValueError("initData устарел.")

    return data.user.id


def create_app(
    bot_token: str,
    load_dashboard: Callable[[int], Awaitable[dict]],
) -> web.Application:
    no_cache = {"Cache-Control": "no-cache"}

    async def index(request: web.Request) -> web.Response:
        # Версия в ссылках на файлы: после правок Telegram не покажет старые.
        version = int(max(path.stat().st_mtime for path in STATIC_DIR.iterdir()))
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        return web.Response(
            text=html.replace("{{version}}", str(version)),
            content_type="text/html",
            headers=no_cache,
        )

    async def me(request: web.Request) -> web.Response:
        header = request.headers.get("Authorization", "")

        if not header.startswith("tma "):
            raise web.HTTPUnauthorized(text="Нет данных Telegram.")

        try:
            user_id = telegram_user_id(bot_token, header.removeprefix("tma "))
        except ValueError:
            raise web.HTTPUnauthorized(text="Неверные данные Telegram.")

        try:
            dashboard = await load_dashboard(user_id)
        except Exception:
            logger.exception("Mini App: не удалось загрузить данные %s", user_id)
            raise web.HTTPInternalServerError(text="Не удалось загрузить данные.")

        return web.json_response(
            dashboard,
            dumps=lambda value: json.dumps(value, ensure_ascii=False, default=str),
            headers=no_cache,
        )

    @web.middleware
    async def security_headers(request: web.Request, handler):
        response = await handler(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    app = web.Application(middlewares=[security_headers])
    app.router.add_get("/", index)
    app.router.add_get("/api/me", me)
    app.router.add_static("/static/", STATIC_DIR)
    return app


async def start_server(
    app: web.Application,
    port: int,
    host: str = "127.0.0.1",
) -> web.AppRunner:
    """Запускает сервер. По умолчанию — только на этом компьютере.

    Снаружи к нему ходят через туннель или прокси с https.
    В Docker нужен host 0.0.0.0 (WEBAPP_HOST).
    """
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, host, port).start()
    logger.info("Mini App: сервер запущен на http://%s:%s", host, port)
    return runner
