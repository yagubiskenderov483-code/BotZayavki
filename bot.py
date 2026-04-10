import asyncio
import logging
import json
import os
from telethon import TelegramClient
from telethon.tl.functions.payments import GetResaleStarGiftsRequest, GetStarGiftsRequest
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========================
API_ID = 28687552
API_HASH = "1abf9a58d0c22f62437bec89bd6b27a3"
BOT_TOKEN = "8620670750:AAFtDzSKPb2nlnZH7ogM6EHdKyIrtdYnu6M"
ADMIN_ID = 174415647
SESSION_NAME = "nft_session"
SETTINGS_FILE = "bot_settings.json"
USERS_FILE = "users.json"
# ========================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
tg_client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

stats = {"checks": 0, "found": 0}
is_searching = False
NFT_COLLECTIONS = {}


# ===================== SETTINGS =====================
def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"custom_link": None, "custom_link_text": "🔗 Открыть"}

def save_settings(data: dict):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_users() -> list:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_users(users: list):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f)

def add_user(user_id: int):
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        save_users(users)


# ===================== STATES =====================
class Auth(StatesGroup):
    phone = State()
    code = State()
    password = State()

class AdminState(StatesGroup):
    waiting_link = State()
    waiting_link_text = State()
    waiting_broadcast = State()


# ===================== KEYBOARDS =====================
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Маркет — все NFT на продаже", callback_data="market_all")],
        [InlineKeyboardButton(text="🗂 Выбрать коллекцию", callback_data="market_col")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
    ])

def stop_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏹ Стоп", callback_data="stop_search")],
    ])

def menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Ещё", callback_data="market_all")],
        [InlineKeyboardButton(text="📱 Меню", callback_data="menu")],
    ])

def admin_kb():
    settings = load_settings()
    link = settings.get("custom_link")
    link_status = f"✅ {link[:30]}..." if link and len(link) > 30 else (f"✅ {link}" if link else "❌ Не задана")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔗 Кастомная ссылка: {link_status}", callback_data="admin_set_link")],
        [InlineKeyboardButton(text="✏️ Текст кнопки ссылки", callback_data="admin_set_link_text")],
        [InlineKeyboardButton(text="🗑 Удалить кастомную ссылку", callback_data="admin_del_link")],
        [InlineKeyboardButton(text="📢 Рассылка всем пользователям", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="👥 Кол-во пользователей", callback_data="admin_users_count")],
        [InlineKeyboardButton(text="📊 Статистика бота", callback_data="stats")],
        [InlineKeyboardButton(text="◀️ В меню", callback_data="menu")],
    ])

def user_nft_kb(username: str, slug: str):
    settings = load_settings()
    buttons = []
    if username:
        buttons.append([InlineKeyboardButton(text=f"👤 @{username}", url=f"https://t.me/{username}")])
    buttons.append([InlineKeyboardButton(text="🎁 Открыть NFT", url=f"https://t.me/nft/{slug}")])
    # Кастомная ссылка — ВСЕГДА добавляется если задана
    if settings.get("custom_link"):
        link_text = settings.get("custom_link_text") or "🔗 Открыть"
        buttons.append([InlineKeyboardButton(text=link_text, url=settings["custom_link"])])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ===================== COLLECTIONS =====================
async def load_collections():
    global NFT_COLLECTIONS
    try:
        result = await tg_client(GetStarGiftsRequest(hash=0))
        for gift in result.gifts:
            title = getattr(gift, 'title', None)
            gift_id = getattr(gift, 'id', None)
            if title and gift_id:
                NFT_COLLECTIONS[title] = gift_id
        logger.info(f"Загружено коллекций: {len(NFT_COLLECTIONS)}")
    except Exception as e:
        logger.error(f"Ошибка загрузки коллекций: {e}")


# ===================== MARKET =====================
async def fetch_market_gifts(gift_id: int = None, offset: str = "", limit: int = 50) -> tuple:
    try:
        result = await tg_client(GetResaleStarGiftsRequest(
            gift_id=gift_id,
            offset=offset,
            limit=limit,
        ))
        items = []
        users_map = {u.id: u for u in (result.users or [])}

        for gift in (result.gifts or []):
            owner_id = getattr(gift, 'owner_id', None)
            owner_peer_id = getattr(owner_id, 'user_id', None) if owner_id else None
            owner = users_map.get(owner_peer_id) if owner_peer_id else None
            username = getattr(owner, 'username', None) if owner else None
            name = ""
            if owner:
                name = f"{owner.first_name or ''} {owner.last_name or ''}".strip()

            title = getattr(gift, 'title', '?')
            slug = getattr(gift, 'slug', None) or getattr(gift, 'unique_id', None) or str(getattr(gift, 'num', ''))
            num = getattr(gift, 'num', '?')
            price = getattr(gift, 'resell_stars', None) or getattr(gift, 'availability_resale_stars', None)

            items.append({
                "username": username,
                "name": name,
                "title": title,
                "slug": slug,
                "num": num,
                "price": price,
            })

        next_offset = getattr(result, 'next_offset', "")
        return items, next_offset

    except FloodWaitError as e:
        logger.warning(f"FloodWait {e.seconds}s")
        await asyncio.sleep(e.seconds + 1)
        return [], ""
    except Exception as e:
        logger.error(f"getResaleStarGifts error: {e}")
        return [], ""


async def search_market(status_msg: Message, gift_id: int = None, max_results: int = 30):
    global is_searching
    is_searching = True
    found = 0

    if gift_id is not None:
        gift_ids = [gift_id]
    else:
        if not NFT_COLLECTIONS:
            await load_collections()
        gift_ids = list(NFT_COLLECTIONS.values())

    try:
        for gid in gift_ids:
            if not is_searching or found >= max_results:
                break
            offset = ""
            while is_searching and found < max_results:
                items, next_offset = await fetch_market_gifts(gift_id=gid, offset=offset)
                if not items:
                    break

                for item in items:
                    if not is_searching or found >= max_results:
                        break

                    found += 1
                    stats["found"] += 1

                    price_text = f"⭐️ {item['price']}" if item['price'] else "цена неизвестна"
                    owner_text = f"@{item['username']}" if item['username'] else f"👤 {item['name'] or 'Скрыт'}"
                    slug = item['slug'] or f"{item['title']}-{item['num']}".replace(" ", "")

                    await status_msg.bot.send_message(
                        chat_id=status_msg.chat.id,
                        text=f"🎁 <b>{item['title']} #{item['num']}</b>\n"
                             f"👤 {owner_text}\n"
                             f"💰 {price_text}",
                        parse_mode="HTML",
                        reply_markup=user_nft_kb(item['username'], slug)
                    )
                    await asyncio.sleep(0.2)

                try:
                    await status_msg.edit_text(
                        f"🛒 Парсю маркет...\n🎁 Найдено: <b>{found}</b>",
                        parse_mode="HTML",
                        reply_markup=stop_kb()
                    )
                except Exception:
                    pass

                if not next_offset:
                    break
                offset = next_offset
                await asyncio.sleep(0.5)
    finally:
        is_searching = False

    return found


# ===================== /START =====================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    add_user(message.from_user.id)
    uid = message.from_user.id

    authorized = False
    try:
        if tg_client.is_connected():
            authorized = await tg_client.is_user_authorized()
    except Exception:
        pass

    if not authorized:
        if uid == ADMIN_ID:
            await message.answer(
                "⚙️ <b>Первый запуск — нужна авторизация</b>\n\n"
                "📱 Введи номер: <code>+79001234567</code>",
                parse_mode="HTML"
            )
            await state.set_state(Auth.phone)
        else:
            await message.answer("⏳ Бот настраивается. Попробуй позже.")
        return

    await message.answer(
        "🎁 <b>NFT Market Parser</b>\n\n"
        "Парсю маркет Telegram — NFT которые сейчас продаются\n"
        "Получаю юзернейм продавца + ссылку на NFT\n\n"
        "👇 Выбери действие:",
        parse_mode="HTML",
        reply_markup=main_kb()
    )


# ===================== AUTH =====================
@dp.message(Auth.phone)
async def auth_phone(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    phone = message.text.strip()
    if not phone.startswith("+"):
        await message.answer("❌ Формат: <code>+79001234567</code>", parse_mode="HTML")
        return
    try:
        if not tg_client.is_connected():
            await tg_client.connect()
        result = await tg_client.send_code_request(phone)
        await state.update_data(phone=phone, phone_code_hash=result.phone_code_hash)
        await state.set_state(Auth.code)
        await message.answer("📨 Введи код: <code>1 2 3 4 5</code> (с пробелами)", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Auth.code)
async def auth_code(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    code = message.text.strip().replace(" ", "")
    data = await state.get_data()
    try:
        await tg_client.sign_in(phone=data["phone"], code=code, phone_code_hash=data["phone_code_hash"])
        me = await tg_client.get_me()
        await state.clear()
        await load_collections()
        await message.answer(f"✅ Авторизован как @{me.username}", reply_markup=main_kb())
    except SessionPasswordNeededError:
        await state.set_state(Auth.password)
        await message.answer("🔐 Введи пароль 2FA:")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        await state.clear()


@dp.message(Auth.password)
async def auth_password(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        await tg_client.sign_in(password=message.text.strip())
        me = await tg_client.get_me()
        await state.clear()
        await load_collections()
        await message.answer(f"✅ Авторизован как @{me.username}", reply_markup=main_kb())
    except Exception as e:
        await message.answer(f"❌ Неверный пароль: {e}")


@dp.message(Command("auth"))
async def cmd_auth(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("📱 Введи номер: <code>+79001234567</code>", parse_mode="HTML")
    await state.set_state(Auth.phone)


# ===================== ADMIN PANEL =====================
@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Нет доступа.")
        return
    await state.clear()
    await message.answer(
        "⚙️ <b>Панель администратора</b>\n\n"
        "Здесь ты можешь настроить кастомную ссылку, которая будет показываться под каждым NFT, "
        "а также сделать рассылку всем пользователям.",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )


@dp.callback_query(F.data == "admin_set_link")
async def cb_admin_set_link(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminState.waiting_link)
    await callback.message.answer(
        "🔗 <b>Введи ссылку</b> которая будет добавляться под каждым NFT:\n\n"
        "Пример: <code>https://t.me/yourchannel</code>",
        parse_mode="HTML"
    )
    await callback.answer()


@dp.message(AdminState.waiting_link)
async def admin_get_link(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    link = message.text.strip()
    if not link.startswith("http"):
        await message.answer("❌ Ссылка должна начинаться с http:// или https://")
        return
    settings = load_settings()
    settings["custom_link"] = link
    save_settings(settings)
    await state.clear()
    await message.answer(
        f"✅ <b>Ссылка сохранена!</b>\n\n{link}\n\nТеперь она будет добавляться под каждым NFT.",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )


@dp.callback_query(F.data == "admin_set_link_text")
async def cb_admin_set_link_text(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminState.waiting_link_text)
    await callback.message.answer(
        "✏️ <b>Введи текст кнопки</b> для кастомной ссылки:\n\n"
        "Пример: <code>🔥 Наш канал</code>",
        parse_mode="HTML"
    )
    await callback.answer()


@dp.message(AdminState.waiting_link_text)
async def admin_get_link_text(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text.strip()
    settings = load_settings()
    settings["custom_link_text"] = text
    save_settings(settings)
    await state.clear()
    await message.answer(
        f"✅ <b>Текст кнопки сохранён:</b> {text}",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )


@dp.callback_query(F.data == "admin_del_link")
async def cb_admin_del_link(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    settings = load_settings()
    settings["custom_link"] = None
    save_settings(settings)
    await callback.answer("🗑 Ссылка удалена!", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=admin_kb())
    except Exception:
        await callback.message.answer("✅ Ссылка удалена.", reply_markup=admin_kb())


@dp.callback_query(F.data == "admin_users_count")
async def cb_admin_users_count(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    users = load_users()
    await callback.answer(f"👥 Пользователей: {len(users)}", show_alert=True)


# ===================== BROADCAST =====================
@dp.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminState.waiting_broadcast)
    users = load_users()
    await callback.message.answer(
        f"📢 <b>Рассылка</b>\n\n"
        f"👥 Получателей: <b>{len(users)}</b>\n\n"
        f"Напиши сообщение для рассылки.\n"
        f"Поддерживается HTML-форматирование: <code>&lt;b&gt;жирный&lt;/b&gt;</code>, <code>&lt;i&gt;курсив&lt;/i&gt;</code>\n\n"
        f"Или отправь /cancel для отмены.",
        parse_mode="HTML"
    )
    await callback.answer()


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=admin_kb() if message.from_user.id == ADMIN_ID else main_kb())


@dp.message(AdminState.waiting_broadcast)
async def admin_do_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()

    users = load_users()
    if not users:
        await message.answer("❌ Нет пользователей для рассылки.")
        return

    status_msg = await message.answer(f"📢 Начинаю рассылку... (0/{len(users)})")

    sent = 0
    failed = 0
    for i, uid in enumerate(users):
        try:
            await bot.send_message(
                chat_id=uid,
                text=message.text or message.caption or "",
                parse_mode="HTML"
            )
            sent += 1
        except Exception as e:
            logger.warning(f"Не удалось отправить {uid}: {e}")
            failed += 1

        if (i + 1) % 10 == 0:
            try:
                await status_msg.edit_text(f"📢 Рассылка... ({i+1}/{len(users)})")
            except Exception:
                pass
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📤 Отправлено: <b>{sent}</b>\n"
        f"❌ Ошибок: <b>{failed}</b>",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )


# ===================== MENU =====================
@dp.callback_query(F.data == "menu")
async def cb_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "🎁 <b>NFT Market Parser</b>\n\n👇 Выбери действие:",
        parse_mode="HTML",
        reply_markup=main_kb()
    )
    await callback.answer()


@dp.callback_query(F.data == "stats")
async def cb_stats(callback: CallbackQuery):
    users = load_users()
    await callback.message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"🔍 Поисков: <b>{stats['checks']}</b>\n"
        f"🎁 Найдено NFT: <b>{stats['found']}</b>\n"
        f"👥 Пользователей: <b>{len(users)}</b>",
        parse_mode="HTML"
    )
    await callback.answer()


# ===================== MARKET =====================
@dp.callback_query(F.data == "market_all")
async def cb_market_all(callback: CallbackQuery):
    global is_searching
    if is_searching:
        await callback.answer("⏳ Поиск уже идёт!", show_alert=True)
        return
    await callback.answer("🛒 Загружаю маркет...")
    stats["checks"] += 1

    status = await callback.message.answer(
        "🛒 Парсю маркет Telegram...\n🎁 Найдено: 0",
        parse_mode="HTML",
        reply_markup=stop_kb()
    )
    found = await search_market(status, max_results=30)

    try:
        await status.edit_text(
            f"✅ <b>Готово!</b>\n\n🎁 Показано NFT: <b>{found}</b>",
            parse_mode="HTML",
            reply_markup=menu_kb()
        )
    except Exception:
        pass


@dp.callback_query(F.data == "market_col")
async def cb_market_col(callback: CallbackQuery):
    if not NFT_COLLECTIONS:
        await callback.answer("⏳ Загружаю коллекции...", show_alert=False)
        await load_collections()

    if not NFT_COLLECTIONS:
        await callback.message.answer("❌ Не удалось загрузить коллекции", reply_markup=menu_kb())
        await callback.answer()
        return

    items = list(NFT_COLLECTIONS.keys())
    rows = []
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(text=items[i], callback_data=f"mcol_{i}")]
        if i + 1 < len(items):
            row.append(InlineKeyboardButton(text=items[i+1], callback_data=f"mcol_{i+1}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="📱 Меню", callback_data="menu")])

    await callback.message.answer(
        "🗂 <b>Выбери коллекцию:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("mcol_"))
async def cb_mcol(callback: CallbackQuery):
    global is_searching
    if is_searching:
        await callback.answer("⏳ Поиск уже идёт!", show_alert=True)
        return

    idx = int(callback.data[5:])
    items = list(NFT_COLLECTIONS.items())
    if idx >= len(items):
        await callback.answer("❌ Коллекция не найдена", show_alert=True)
        return
    col_name, gift_id = items[idx]

    await callback.answer(f"🔍 {col_name}")
    stats["checks"] += 1

    status = await callback.message.answer(
        f"🛒 Ищу <b>{col_name}</b> на маркете...\n🎁 Найдено: 0",
        parse_mode="HTML",
        reply_markup=stop_kb()
    )
    found = await search_market(status, gift_id=gift_id, max_results=30)

    try:
        await status.edit_text(
            f"✅ <b>{col_name}</b>\n\n🎁 Показано: <b>{found}</b>",
            parse_mode="HTML",
            reply_markup=menu_kb()
        )
    except Exception:
        pass


@dp.callback_query(F.data == "stop_search")
async def cb_stop(callback: CallbackQuery):
    global is_searching
    is_searching = False
    await callback.answer("⏹ Останавливаю...")
    try:
        await callback.message.edit_reply_markup(reply_markup=menu_kb())
    except Exception:
        pass


# ===================== MAIN =====================
async def main():
    await tg_client.connect()
    logger.info("🎁 NFT Market Parser запущен!")
    try:
        if await tg_client.is_user_authorized():
            await load_collections()
    except Exception:
        pass
    try:
        await dp.start_polling(bot)
    finally:
        await tg_client.disconnect()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
