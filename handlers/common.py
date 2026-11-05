"""Приветствие и служебные команды."""

import asyncio

from aiogram import F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from blocked_users import mark_active, mark_blocked
from database import DatabaseError, create_profile, set_language
from grades_service import show_grades

router = Router(name="common")
router.message.filter(F.chat.type == "private")


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user is None:
        return

    await asyncio.to_thread(create_profile, message.from_user.id)

    await message.answer(
        "Привет! Я Aura 👋\n\n"
        "Твой личный ИИ-помощник для жизни и учёбы.\n\n"
        "Общайся со мной обычными сообщениями: "
        "задавай вопросы, проси помочь разобраться в теме, "
        "показать оценки или разобрать их "
        "(«где у меня всё плохо?», «сколько нужно на экзамене?»).\n\n"
        "Могу запомнить ссылку или заметку и напомнить о ней "
        "в нужное время: «напомни завтра в 9 про лабу».\n\n"
        "Каждое утро пришлю пары на день, а за 15 минут до пары — напомню.\n\n"
        "Подключить Platonus: /connect\n"
        "Расписание: /schedule · дайджест: /digest\n"
        "Язык сводки по оценкам: /lang\n\n"
        "С чем помочь?"
    )


@router.message(Command("id"))
async def show_id(message: Message):
    await message.answer(f"Твой Telegram ID: {message.chat.id}")


@router.message(Command("grades"))
async def grades_command(message: Message):
    await show_grades(message)


LANGUAGES = {"kk": "🇰🇿 Қазақша", "ru": "🇷🇺 Русский"}

LANGUAGE_SAVED = {
    "kk": "Дайын ✅ Бағалар бойынша шолу енді қазақ тілінде келеді.",
    "ru": "Готово ✅ Сводки по оценкам теперь будут на русском.",
}


@router.message(Command("lang"))
async def choose_language(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=title, callback_data=f"lang:{code}")
                for code, title in LANGUAGES.items()
            ]
        ]
    )
    await message.answer(
        "Бағалар шолуының тілін таңдаңыз:\n"
        "Выбери язык сводки по оценкам:",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("lang:"))
async def language_chosen(callback: CallbackQuery):
    code = callback.data.removeprefix("lang:")

    if code not in LANGUAGES:
        await callback.answer()
        return

    try:
        await asyncio.to_thread(set_language, callback.from_user.id, code)
    except DatabaseError:
        await callback.answer("Не удалось сохранить. Попробуй позже.", show_alert=True)
        return

    await callback.answer()

    if callback.message is not None:
        await callback.message.edit_text(LANGUAGE_SAVED[code])


@router.my_chat_member(F.chat.type == "private")
async def bot_status_changed(event: ChatMemberUpdated):
    # Telegram сам сообщает, когда пользователь блокирует
    # или разблокирует бота.
    status = event.new_chat_member.status

    if status == ChatMemberStatus.KICKED:
        mark_blocked(event.from_user.id)
    elif status == ChatMemberStatus.MEMBER:
        mark_active(event.from_user.id)
