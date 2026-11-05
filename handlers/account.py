"""Подключение Platonus."""

import asyncio

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from database import DatabaseError, save_user

router = Router(name="account")
router.message.filter(F.chat.type == "private")


class ConnectAccount(StatesGroup):
    login = State()
    password = State()


@router.message(Command("connect"))
async def connect_account(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(ConnectAccount.login)
    await message.answer("Введи логин Platonus:")


@router.message(ConnectAccount.login, F.chat.type == "private", F.text)
async def receive_login(message: Message, state: FSMContext):
    login = message.text.strip()

    if not login or login.startswith("/"):
        await message.answer("Введи логин обычным текстом.")
        return

    await state.update_data(login=login)
    await state.set_state(ConnectAccount.password)
    await message.answer("Введи пароль: ")


@router.message(ConnectAccount.password, F.chat.type == "private", F.text)
async def receive_password(message: Message, state: FSMContext):
    if message.from_user is None:
        return

    password = message.text

    # Пароль не должен оставаться в переписке.
    try:
        await message.delete()
    except TelegramAPIError:
        await message.answer(
            "Не удалось удалить сообщение с паролем — "
            "удали его сам, пожалуйста."
        )

    if not password.strip() or password.startswith("/"):
        await message.answer("Введи пароль обычным текстом.")
        return

    data = await state.get_data()

    try:
        await asyncio.to_thread(
            save_user,
            message.from_user.id,
            data["login"],
            password,
        )
    except DatabaseError:
        await state.clear()
        await message.answer(
            "Не удалось сохранить данные. Попробуй /connect позже."
        )
        return

    await state.clear()
    await message.answer(
        "Данные Platonus успешно сохранены ✅\n"
        "Сообщение с паролем я удалил.\n\n"
        "Хочешь посмотреть свои оценки? "
        "Напиши «покажи оценки»."
    )
