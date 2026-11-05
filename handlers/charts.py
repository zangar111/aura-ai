"""График прогресса (/chart, кнопка под сводкой) и Mini App (/app)."""

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from database import DatabaseError
from grades_service import UnknownSubject, send_grade_chart, user_language
from webapp_server import public_url

router = Router(name="charts")
router.message.filter(F.chat.type == "private")

CHART_FAILED = "Не удалось построить график. Попробуй позже."


@router.message(Command("chart"))
async def chart_command(message: Message, command: CommandObject):
    if message.from_user is None:
        return

    # «/chart блокчейн» — график одного предмета.
    try:
        await send_grade_chart(
            message.bot,
            message.chat.id,
            message.from_user.id,
            command.args,
        )
    except UnknownSubject as error:
        await message.answer(
            "Такого предмета не нашёл. Есть:\n"
            + "\n".join(f"• {subject}" for subject in error.subjects)
        )
    except (DatabaseError, TelegramAPIError, ValueError):
        await message.answer(CHART_FAILED)


APP_TEXTS = {
    "kk": ("📱 Aura журналы: бағалар, өзгерістер мен жазбалар.", "Ашу"),
    "ru": ("📱 Журнал Aura: оценки, изменения и заметки.", "Открыть"),
}


@router.message(Command("app"))
async def app_command(message: Message):
    if message.from_user is None:
        return

    url = public_url()

    if not url:
        await message.answer("Mini App сейчас недоступен. Попробуй позже.")
        return

    text, button = APP_TEXTS[await user_language(message.from_user.id)]
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=button, web_app=WebAppInfo(url=url))]
            ]
        ),
    )


@router.callback_query(F.data == "chart")
async def chart_button_pressed(callback: CallbackQuery):
    await callback.answer()

    if callback.message is None:
        return

    try:
        await send_grade_chart(
            callback.bot,
            callback.message.chat.id,
            callback.from_user.id,
        )
    except (DatabaseError, TelegramAPIError, ValueError):
        await callback.message.answer(CHART_FAILED)
