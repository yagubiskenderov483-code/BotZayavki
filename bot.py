import asyncio
import logging
import json
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========================
BOT_TOKEN = "8620670750:AAFtDzSKPb2nlnZH7ogM6EHdKyIrtdYnu6M"
ADMIN_ID = 8726084830
USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"
# ========================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ===================== ФАЙЛЫ =====================
def load_users() -> list:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return []

def save_users(users: list):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

def add_user(user_id: int):
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        save_users(users)

def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {"invite_link": None}

def save_settings(data: dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False)


# ===================== СОСТОЯНИЯ =====================
class Form(StatesGroup):
    q1_source = State()
    q2_experience = State()
    q3_hours = State()

class AdminState(StatesGroup):
    waiting_link = State()
    waiting_broadcast = State()


# ===================== КЛАВИАТУРЫ =====================
def approve_kb(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_{user_id}"),
        ]
    ])

def admin_kb():
    settings = load_settings()
    link = settings.get("invite_link")
    if link:
        link_preview = link[:35] + "..." if len(link) > 35 else link
        link_btn_text = f"✅ Ссылка: {link_preview}"
    else:
        link_btn_text = "🔗 Задать ссылку для принятых"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=link_btn_text, callback_data="admin_set_link")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="👥 Кол-во пользователей", callback_data="admin_users")],
    ])


# ===================== /START =====================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    add_user(message.from_user.id)

    await message.answer(
        "👋 <b>Привет!</b>\n\n"
        "Для подачи заявки ответь на несколько вопросов.\n\n"
        "❓ <b>Вопрос 1 из 3</b>\n"
        "Откуда ты узнал(а) о нас?",
        parse_mode="HTML"
    )
    await state.set_state(Form.q1_source)


# ===================== АНКЕТА =====================
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

    await message.answer(
        "✅ <b>Заявка отправлена!</b>\n\n"
        "Ожидай ответа от администратора.",
        parse_mode="HTML"
    )

    await bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"📋 <b>Новая заявка!</b>\n\n"
            f"👤 <b>Пользователь:</b> {user.full_name} ({username})\n"
            f"🆔 <b>ID:</b> <code>{user.id}</code>\n\n"
            f"1️⃣ <b>Откуда узнал(а):</b>\n{data['source']}\n\n"
            f"2️⃣ <b>Опыт:</b>\n{data['experience']}\n\n"
            f"3️⃣ <b>Часов в день:</b>\n{data['hours']}"
        ),
        parse_mode="HTML",
        reply_markup=approve_kb(user.id)
    )


# ===================== ПРИНЯТЬ / ОТКЛОНИТЬ =====================
@dp.callback_query(F.data.startswith("approve_"))
async def cb_approve(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    user_id = int(callback.data.split("_")[1])
    settings = load_settings()
    invite_link = settings.get("invite_link")

    if not invite_link:
        msg_text = "🎉 <b>Твоя заявка одобрена!</b>\n\nАдминистратор скоро свяжется с тобой."
    else:
        msg_text = (
            f"🎉 <b>Твоя заявка одобрена!</b>\n\n"
            f"Вступай по ссылке:\n{invite_link}"
        )

    try:
        await bot.send_message(chat_id=user_id, text=msg_text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Не удалось отправить {user_id}: {e}")

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>Одобрено</b>",
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
            text="😔 <b>Твоя заявка отклонена.</b>\n\nК сожалению, на данный момент мы не можем тебя принять.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить {user_id}: {e}")

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>Отклонено</b>",
        parse_mode="HTML"
    )
    await callback.answer("❌ Отклонено!")


# ===================== АДМИН ПАНЕЛЬ =====================
@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Нет доступа.")
        return
    await state.clear()
    await message.answer(
        "⚙️ <b>Панель администратора</b>",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )


@dp.callback_query(F.data == "admin_set_link")
async def cb_set_link(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminState.waiting_link)
    await callback.message.answer(
        "🔗 <b>Введи ссылку</b> которая будет отправляться принятым пользователям:\n\n"
        "Пример: <code>https://t.me/+abcdef123456</code>\n\n"
        "/cancel — отмена",
        parse_mode="HTML"
    )
    await callback.answer()


@dp.message(AdminState.waiting_link)
async def admin_save_link(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    link = message.text.strip()
    if not link.startswith("http"):
        await message.answer("❌ Ссылка должна начинаться с http:// или https://\n\nПопробуй ещё раз или /cancel")
        return
    settings = load_settings()
    settings["invite_link"] = link
    save_settings(settings)
    await state.clear()
    await message.answer(
        f"✅ <b>Ссылка сохранена!</b>\n\n<code>{link}</code>\n\nТеперь она будет отправляться при одобрении заявки.",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )


@dp.callback_query(F.data == "admin_broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    users = load_users()
    await state.set_state(AdminState.waiting_broadcast)
    await callback.message.answer(
        f"📢 <b>Рассылка</b>\n\n"
        f"👥 Получателей: <b>{len(users)}</b>\n\n"
        f"Напиши сообщение для рассылки.\n"
        f"Поддерживается HTML: <b>жирный</b> — <code>&lt;b&gt;текст&lt;/b&gt;</code>\n\n"
        f"/cancel — отмена",
        parse_mode="HTML"
    )
    await callback.answer()


@dp.message(AdminState.waiting_broadcast)
async def admin_do_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()

    users = load_users()
    if not users:
        await message.answer("❌ Нет пользователей для рассылки.")
        return

    status = await message.answer(f"📢 Отправляю... (0/{len(users)})")
    sent = 0
    failed = 0

    for i, uid in enumerate(users):
        try:
            await bot.send_message(chat_id=uid, text=message.text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        if (i + 1) % 10 == 0:
            try:
                await status.edit_text(f"📢 Отправляю... ({i+1}/{len(users)})")
            except Exception:
                pass
        await asyncio.sleep(0.05)

    await status.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📤 Отправлено: <b>{sent}</b>\n"
        f"❌ Ошибок: <b>{failed}</b>",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )


@dp.callback_query(F.data == "admin_users")
async def cb_users_count(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    users = load_users()
    await callback.answer(f"👥 Пользователей в базе: {len(users)}", show_alert=True)


# ===================== CANCEL =====================
@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id == ADMIN_ID:
        await message.answer("❌ Отменено.", reply_markup=admin_kb())
    else:
        await message.answer("❌ Отменено.")


# ===================== MAIN =====================
async def main():
    logger.info("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
