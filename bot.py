import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.types import MenuButtonDefault, MenuButtonWebApp, Message, WebAppInfo

from blocked_users import mark_active
from config import WEBAPP_HOST, WEBAPP_PORT, WEBAPP_TUNNEL, WEBAPP_URL, setup_logging
from dashboard import load_dashboard
from database import check_schema, close_pool
from grades_service import monitor_grades
from handlers import routers
from parser import browser_holder
from reminders import send_due_reminders
from schedule_service import run_schedule_notifications
from tunnel import QuickTunnel
from webapp_server import create_app, set_public_url, start_server

logger = logging.getLogger(__name__)


async def start_webapp(bot: Bot, token: str):
    """Запускает сервер Mini App и, если нужно, туннель.

    Возвращает (runner, tunnel) для остановки. Ошибки Mini App
    не мешают работе бота — он просто запустится без него.
    """
    if not WEBAPP_PORT:
        return None, None

    try:
        runner = await start_server(
            create_app(token, load_dashboard), WEBAPP_PORT, WEBAPP_HOST
        )
    except OSError as error:
        logger.warning("Mini App: порт %s занят или недоступен: %s", WEBAPP_PORT, error)
        return None, None

    url = WEBAPP_URL
    tunnel = None

    if not url and WEBAPP_TUNNEL:
        tunnel = QuickTunnel(WEBAPP_PORT)

        try:
            url = await tunnel.start()
        except (OSError, RuntimeError) as error:
            logger.warning("Mini App: туннель не запущен: %s", error)
            tunnel = None

    if not url:
        logger.info(
            "Mini App: нет https-адреса. Укажи WEBAPP_URL "
            "или WEBAPP_TUNNEL=1 в .env."
        )
        return runner, tunnel

    set_public_url(url, stable=tunnel is None)

    try:
        # Кнопка «Aura» слева от поля ввода во всех чатах с ботом.
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Aura", web_app=WebAppInfo(url=url))
        )
    except TelegramAPIError as error:
        logger.warning("Mini App: кнопку меню не установить: %s", error)

    logger.info("Mini App: %s", url)
    return runner, tunnel


async def stop_webapp(bot: Bot, runner, tunnel):
    if tunnel is not None:
        # Адрес туннеля больше не работает — убираем кнопку.
        try:
            await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
        except TelegramAPIError:
            pass

        await tunnel.stop()

    set_public_url(None)

    if runner is not None:
        await runner.cleanup()


async def unblock_on_message(handler, event: Message, data: dict):
    # Кто пишет боту, тот его точно не блокирует.
    if event.from_user is not None:
        mark_active(event.from_user.id)

    return await handler(event, data)


async def main():
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Укажи BOT_TOKEN перед запуском.")

    try:
        interval_minutes = int(
            os.getenv("GRADE_CHECK_INTERVAL_MINUTES", "15")
        )
    except ValueError:
        raise SystemExit(
            "GRADE_CHECK_INTERVAL_MINUTES должно быть целым числом."
        )

    if interval_minutes <= 0:
        raise SystemExit(
            "GRADE_CHECK_INTERVAL_MINUTES должно быть больше нуля."
        )

    missing = await asyncio.to_thread(check_schema)

    if missing:
        raise SystemExit(
            "База данных не обновлена. Выполни от имени postgres:\n"
            + "\n".join(
                f'& "C:\\Program Files\\PostgreSQL\\18\\bin\\psql.exe" '
                f"-U postgres -p 5433 -d aura_ai -f {path}"
                for path in missing
            )
        )

    dp = Dispatcher()
    dp.message.outer_middleware(unblock_on_message)
    dp.include_routers(*routers)

    async with Bot(token=token) as bot:
        webapp_runner, webapp_tunnel = await start_webapp(bot, token)
        stop_event = asyncio.Event()
        background_tasks = [
            asyncio.create_task(
                monitor_grades(bot, interval_minutes * 60, stop_event)
            ),
            asyncio.create_task(send_due_reminders(bot, stop_event)),
            asyncio.create_task(run_schedule_notifications(bot, stop_event)),
        ]

        logger.info(
            "Автопроверка оценок запущена: каждые %s мин.", interval_minutes
        )

        try:
            await dp.start_polling(bot, close_bot_session=False)
        finally:
            stop_event.set()
            await asyncio.gather(*background_tasks)
            await stop_webapp(bot, webapp_runner, webapp_tunnel)
            await browser_holder.close()
            close_pool()


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
