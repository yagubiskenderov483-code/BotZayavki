import asyncio
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = "8403901930:AAEBh5zM33tsOC9a4KzDZ5CQ_YaiHp6O9-o"
ADMIN_ID = 8541316053

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class Application(StatesGroup):
    captcha = State()
    source = State()
    experience = State()
    time = State()

user_captcha = {}

@dp.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    user_captcha[message.from_user.id] = num1 + num2
    await state.set_state(Application.captcha)
    await message.answer(f"👋 Добро пожаловать!\n\nДля подачи заявки сначала пройдите капчу:\n\n🔢 Сколько будет {num1} + {num2}?")

@dp.message(Application.captcha)
async def check_captcha(message: Message, state: FSMContext):
    correct = user_captcha.get(message.from_user.id)
    if not message.text.isdigit() or int(message.text) != correct:
        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        user_captcha[message.from_user.id] = num1 + num2
        await message.answer(f"❌ Неверно! Попробуйте ещё раз:\n\n🔢 Сколько будет {num1} + {num2}?")
        return
    await state.set_state(Application.source)
    await message.answer("✅ Капча пройдена!\n\n📌 Откуда вы о нас узнали?")

@dp.message(Application.source)
async def get_source(message: Message, state: FSMContext):
    await state.update_data(source=message.text)
    await state.set_state(Application.experience)
    await message.answer("💼 Какой у вас опыт в данной сфере?")

@dp.message(Application.experience)
async def get_experience(message: Message, state: FSMContext):
    await state.update_data(experience=message.text)
    await state.set_state(Application.time)
    await message.answer("⏰ Сколько часов в день вы готовы уделять данной работе?")

@dp.message(Application.time)
async def get_time(message: Message, state: FSMContext):
    await state.update_data(time=message.text)
    data = await state.get_data()
    user = message.from_user
    username = f"@{user.username}" if user.username else f"ID: {user.id}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_{user.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user.id}")
        ]
    ])

    await bot.send_message(
        ADMIN_ID,
        f"📋 <b>Новая заявка!</b>\n\n"
        f"👤 Пользователь: {username}\n"
        f"🆔 ID: {user.id}\n"
        f"📌 Откуда узнал: {data['source']}\n"
        f"💼 Опыт: {data['experience']}\n"
        f"⏰ Время в день: {data['time']}",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await message.answer("📨 Ваша заявка отправлена! Ожидайте решения.")
    await state.clear()

@dp.callback_query(F.data.startswith("accept_"))
async def accept(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await bot.send_message(user_id, "🎉 Ваша заявка принята!\n\nДержите ссылку: https://t.me/+uJb5tX3evGhiNzM6")
    await callback.message.edit_text(callback.message.text + "\n\n✅ <b>Принято</b>", parse_mode="HTML")
    await callback.answer("Пользователь принят!")

@dp.callback_query(F.data.startswith("reject_"))
async def reject(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await bot.send_message(user_id, "❌ К сожалению, ваша заявка отклонена.")
    await callback.message.edit_text(callback.message.text + "\n\n❌ <b>Отклонено</b>", parse_mode="HTML")
    await callback.answer("Пользователь отклонён!")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
