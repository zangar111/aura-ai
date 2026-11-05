"""Расписание (/schedule) и настройки дайджеста (/digest)."""

import asyncio
from datetime import datetime, time, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import DatabaseError, get_digest_settings, update_digest_settings
from formatting import split_message
from schedule import format_day, format_week
from schedule_service import load_schedule, texts_for, user_settings

router = Router(name="schedule")
router.message.filter(F.chat.type == "private")

DIGEST_TIMES = ["06:30", "07:00", "07:30", "08:00", "08:30"]

TEXTS = {
    "kk": {
        "today": "Бүгін",
        "tomorrow": "Ертең",
        "week": "📅 Апта",
        "refresh": "🔄 Жаңарту",
        "settings_title": "⚙️ <b>Дайджест баптаулары</b>",
        "settings_body": (
            "Таңертең бот бүгінгі сабақтарды, еске салуларды "
            "және жаңа бағаларды жібереді.\n"
            "Сабақ басталардан 15 минут бұрын да еске салады."
        ),
        "digest": "Таңғы дайджест",
        "lessons": "Сабақ алдында еске салу",
        "time": "Уақыты",
        "saved": "Сақталды ✅",
    },
    "ru": {
        "today": "Сегодня",
        "tomorrow": "Завтра",
        "week": "📅 Неделя",
        "refresh": "🔄 Обновить",
        "settings_title": "⚙️ <b>Настройки дайджеста</b>",
        "settings_body": (
            "Утром бот присылает пары на сегодня, напоминания "
            "и новые оценки.\n"
            "Ещё он напоминает о паре за 15 минут до начала."
        ),
        "digest": "Утренний дайджест",
        "lessons": "Напоминание перед парой",
        "time": "Время",
        "saved": "Сохранено ✅",
    },
}


def schedule_keyboard(language: str) -> InlineKeyboardMarkup:
    texts = TEXTS[language]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=texts["week"], callback_data="schedule:week"),
                InlineKeyboardButton(text=texts["refresh"], callback_data="schedule:refresh"),
            ]
        ]
    )


async def schedule_text(telegram_id: int, *, refresh: bool = False) -> tuple[str | None, str]:
    """Пары на сегодня и завтра. Текст None — Platonus не подключён."""
    language, tz = await user_settings(telegram_id)
    schedule = await load_schedule(telegram_id, refresh=refresh)

    if schedule is None:
        return None, language

    texts = TEXTS[language]
    today = datetime.now(tz).date()
    text = (
        format_day(schedule, today, language, texts["today"])
        + "\n\n"
        + format_day(schedule, today + timedelta(days=1), language, texts["tomorrow"])
    )
    return text, language


@router.message(Command("schedule"))
async def schedule_command(message: Message):
    if message.from_user is None:
        return

    language, _ = await user_settings(message.from_user.id)
    progress = await message.answer(texts_for(language)["loading"])

    try:
        text, language = await schedule_text(message.from_user.id)
    except Exception:
        await progress.edit_text(texts_for(language)["failed"])
        return

    if text is None:
        await progress.edit_text(texts_for(language)["not_connected"])
        return

    await progress.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=schedule_keyboard(language),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "schedule:week")
async def week_pressed(callback: CallbackQuery):
    await callback.answer()

    if callback.message is None:
        return

    language, tz = await user_settings(callback.from_user.id)

    try:
        schedule = await load_schedule(callback.from_user.id)
    except Exception:
        await callback.message.answer(texts_for(language)["failed"])
        return

    if schedule is None:
        await callback.message.answer(texts_for(language)["not_connected"])
        return

    today = datetime.now(tz).date()
    monday = today - timedelta(days=today.weekday())

    # В выходные полезнее следующая неделя.
    if today.weekday() >= 5:
        monday += timedelta(days=7)

    for chunk in split_message(format_week(schedule, monday, language), limit=4000):
        await callback.message.answer(chunk, parse_mode="HTML", disable_web_page_preview=True)


@router.callback_query(F.data == "schedule:refresh")
async def refresh_pressed(callback: CallbackQuery):
    language, _ = await user_settings(callback.from_user.id)
    await callback.answer(texts_for(language)["loading"])

    if callback.message is None:
        return

    try:
        text, language = await schedule_text(callback.from_user.id, refresh=True)
    except Exception:
        await callback.message.answer(texts_for(language)["failed"])
        return

    if text is None:
        await callback.message.answer(texts_for(language)["not_connected"])
        return

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=schedule_keyboard(language),
            disable_web_page_preview=True,
        )
    except TelegramBadRequest:
        # Расписание не изменилось — Telegram не даёт «изменить» на то же.
        pass


# ---------- Настройки дайджеста ----------

def settings_view(settings: dict, language: str) -> tuple[str, InlineKeyboardMarkup]:
    texts = TEXTS[language]
    chosen = settings["digest_time"].strftime("%H:%M")

    def mark(enabled: bool) -> str:
        return "✅" if enabled else "⬜️"

    text = (
        f"{texts['settings_title']}\n\n{texts['settings_body']}\n\n"
        f"{mark(settings['digest_enabled'])} {texts['digest']} — {chosen}\n"
        f"{mark(settings['lesson_reminders'])} {texts['lessons']}"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{mark(settings['digest_enabled'])} {texts['digest']}",
                    callback_data="digest:toggle",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"• {value} •" if value == chosen else value,
                    callback_data=f"digest:time:{value}",
                )
                for value in DIGEST_TIMES
            ],
            [
                InlineKeyboardButton(
                    text=f"{mark(settings['lesson_reminders'])} {texts['lessons']}",
                    callback_data="digest:lessons",
                )
            ],
        ]
    )
    return text, keyboard


@router.message(Command("digest"))
async def digest_command(message: Message):
    if message.from_user is None:
        return

    language, _ = await user_settings(message.from_user.id)

    try:
        settings = await asyncio.to_thread(get_digest_settings, message.from_user.id)
    except DatabaseError:
        await message.answer(texts_for(language)["failed"])
        return

    text, keyboard = settings_view(settings, language)
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("digest:"))
async def digest_changed(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    language, _ = await user_settings(telegram_id)
    action = callback.data.removeprefix("digest:")

    try:
        settings = await asyncio.to_thread(get_digest_settings, telegram_id)

        if action == "toggle":
            changes = {"digest_enabled": not settings["digest_enabled"]}
        elif action == "lessons":
            changes = {"lesson_reminders": not settings["lesson_reminders"]}
        elif action.startswith("time:") and action[5:] in DIGEST_TIMES:
            hours, minutes = action[5:].split(":")
            changes = {"digest_time": time(int(hours), int(minutes)), "digest_enabled": True}
        else:
            await callback.answer()
            return

        await asyncio.to_thread(update_digest_settings, telegram_id, **changes)
        settings.update(changes)
    except DatabaseError:
        await callback.answer(texts_for(language)["failed"], show_alert=True)
        return

    await callback.answer(TEXTS[language]["saved"])

    if callback.message is not None:
        text, keyboard = settings_view(settings, language)

        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        except (TelegramBadRequest, TelegramAPIError):
            pass
