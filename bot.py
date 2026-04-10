import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========================
BOT_TOKEN = "8620670750:AAFtDzSKPb2nlnZH7ogM6EHdKyIrtdYnu6M"
ADMIN_ID = 8726084830
# ========================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class Form(StatesGroup):
    q1_source = State()
    q2_experience = State()
    q3_hours = State()


def approve_kb(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_{user_id}"),
        ]
    ])


# ===================== /START =====================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 <b>Привет!</b>\n\n"
        "Для подачи заявки ответь на несколько вопросов.\n\n"
        "❓ <b>Вопрос 1 из 3</b>\n"
        "Откуда ты узнал(а) о нас?",
        parse_mode="HTML"
    )
    await state.set_state(Form.q1_source)


# ===================== ВОПРОСЫ =====================
@dp.message(Form.q1_source)
async def q1_answer(message: Message, state: FSMContext):
    await state.update_data(source=message.text)
    await message.answer(
        "❓ <b>Вопрос 2 из 3</b>\n"
        "Есть ли у тебя опыт? Если да — расскажи коротко.",
        parse_mode="HTML"
    )
    await state.set_state(Form.q2_experience)


@dp.message(Form.q2_experience)
async def q2_answer(message: Message, state: FSMContext):
    await state.update_data(experience=message.text)
    await message.answer(
        "❓ <b>Вопрос 3 из 3</b>\n"
        "Сколько часов в день ты готов(а) уделять работе?",
        parse_mode="HTML"
    )
    await state.set_state(Form.q3_hours)


@dp.message(Form.q3_hours)
async def q3_answer(message: Message, state: FSMContext):
    await state.update_data(hours=message.text)
    data = await state.get_data()
    await state.clear()

    user = message.from_user
    username = f"@{user.username}" if user.username else "нет юзернейма"
    full_name = user.full_name

    # Сообщение пользователю
    await message.answer(
        "✅ <b>Заявка отправлена!</b>\n\n"
        "Ожидай ответа от администратора. Мы рассмотрим твою заявку в ближайшее время.",
        parse_mode="HTML"
    )

    # Заявка администратору
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"📋 <b>Новая заявка!</b>\n\n"
            f"👤 <b>Пользователь:</b> {full_name} ({username})\n"
            f"🆔 <b>ID:</b> <code>{user.id}</code>\n\n"
            f"1️⃣ <b>Откуда узнал(а):</b>\n{data['source']}\n\n"
            f"2️⃣ <b>Опыт:</b>\n{data['experience']}\n\n"
            f"3️⃣ <b>Часов в день:</b>\n{data['hours']}"
        ),
        parse_mode="HTML",
        reply_markup=approve_kb(user.id)
    )


# ===================== ОДОБРЕНИЕ / ОТКЛОНЕНИЕ =====================
@dp.callback_query(F.data.startswith("approve_"))
async def cb_approve(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    user_id = int(callback.data.split("_")[1])

    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "🎉 <b>Твоя заявка одобрена!</b>\n\n"
                "Добро пожаловать! Администратор скоро свяжется с тобой."
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>Заявка одобрена</b>",
        parse_mode="HTML"
    )
    await callback.answer("✅ Принято!")


@dp.callback_query(F.data.startswith("decline_"))
async def cb_decline(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    user_id = int(callback.data.split("_")[1])

    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "😔 <b>Твоя заявка отклонена.</b>\n\n"
                "К сожалению, на данный момент мы не можем тебя принять."
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>Заявка отклонена</b>",
        parse_mode="HTML"
    )
    await callback.answer("❌ Отклонено!")


# ===================== MAIN =====================
async def main():
    logger.info("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
