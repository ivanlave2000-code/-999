import asyncio
import logging
import sys
from html import escape  # Для экранирования спецсимволов HTML

from aiogram import Bot, Dispatcher, F, html, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from database import generate_auth_code, init_db

# ==========================================
# 📊 НАСТРОЙКА ЛОГИРОВАНИЯ
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ==========================================
# ⚙️ КОНФИГУРАЦИЯ БОТА
# ==========================================
BOT_TOKEN = "8953457596:AAHOBGTQW_nRcQ2ewEW37HJUzbxQrWWb-B8"
ADMIN_ID = 5749863973  # Твой Telegram ID

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class AdminReply(StatesGroup):
    waiting_for_message = State()

def get_main_keyboard():
    kb = [
        [KeyboardButton(text="🔑 Вхід на сайт")],
        [KeyboardButton(text="💬 Написати в підтримку")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    logger.info(f"Пользователь {message.from_user.id} ({message.from_user.first_name}) нажал /start")
    await message.answer(
        f"Вітаємо, {escape(message.from_user.first_name)}!\n\n"
        f"Скористайтеся меню нижче для отримання коду входу або зв'язку з підтримкою.",
        reply_markup=get_main_keyboard()
    )
    
@dp.message(Command("makeadmin"))
async def make_admin_handler(message: types.Message):
    # Разбиваем сообщение по пробелам: /makeadmin secret_password
    args = message.text.split()
    
    SECRET_KEY = "supersecret123"  # Придумай свой пароль
    
    if len(args) < 2 or args[1] != SECRET_KEY:
        await message.answer("❌ Неверный пароль для получения прав администратора.")
        return

    # Если пароль совпал, выдаем админку по telegram_id
    import sqlite3
    from database import DB_NAME

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Проверяем, привязан ли этот Telegram к аккаунту на сайте
    cursor.execute("SELECT username FROM users WHERE telegram_id = ?", (message.from_user.id,))
    user = cursor.fetchone()

    if not user:
        await message.answer("⚠️ Твой Telegram еще не привязан к аккаунту на сайте! Сначала привяжи его в личном кабинете.")
        conn.close()
        return

    # Выдаем права
    cursor.execute("UPDATE users SET is_admin = 1 WHERE telegram_id = ?", (message.from_user.id,))
    conn.commit()
    conn.close()

    await message.answer(f"🎉 Готово! Аккаунт **{user[0]}** теперь имеет права администратора!")

@dp.message(F.text == "🔑 Вхід на сайт")
async def get_login_code(message: types.Message):
    user_id = message.from_user.id
    logger.info(f"Генерация кода авторизации для ID: {user_id}")
    
    code = generate_auth_code(
        telegram_id=user_id,
        first_name=message.from_user.first_name,
        username=message.from_user.username
    )
    await message.answer(
        f"🔑 Ваш код для входу на сайт: <code>{code}</code>\n\n"
        f"Введіть його у формі на сайті.",
        parse_mode="HTML"
    )

@dp.message(F.text == "💬 Написати в підтримку")
async def support_info(message: types.Message):
    await message.answer(
        "📝 <b>Напишіть ваше запитання прямо сюди в чат.</b>\n\n"
        "Оператор підтримки отримає сповіщення та відповість вам найближчим часом!",
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("reply_to_"), F.from_user.id == ADMIN_ID)
async def process_reply_button(callback: types.CallbackQuery, state: FSMContext):
    target_user_id = int(callback.data.split("reply_to_")[1])
    logger.info(f"Администратор нажал кнопку ответа для пользователя ID: {target_user_id}")
    
    await state.update_data(target_user_id=target_user_id)
    await state.set_state(AdminReply.waiting_for_message)
    
    await callback.message.answer(
        f"✍️ <b>Введіть текст відповіді для користувача</b> (ID: <code>{target_user_id}</code>):",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(AdminReply.waiting_for_message, F.from_user.id == ADMIN_ID)
async def send_admin_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    if not target_user_id:
        logger.error("Ошибка FSM: target_user_id не найден")
        await message.answer("❌ Помилка: не знайдено ID отримувача.")
        await state.clear()
        return

    try:
        # Экранируем текст от админа
        clean_text = escape(message.text)
        user_response = (
            f"💬 <b>ВІДПОВІДЬ СЛУЖБИ ПІДТРИМКИ</b>\n\n"
            f"{clean_text}\n\n"
            f"───────────────\n"
            f"Якщо у вас залишилися запитання, ви можете просто написати їх сюди."
        )
        
        await bot.send_message(
            chat_id=target_user_id,
            text=user_response,
            parse_mode="HTML"
        )
        
        logger.info(f"Ответ успешно доставлен пользователю ID: {target_user_id}")
        await message.answer("✅ <b>Відповідь успішно доставлена користувачу!</b>", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа ID {target_user_id}: {e}", exc_info=True)
        await message.answer(f"❌ Не вдалося надіслати відповідь: <code>{escape(str(e))}</code>", parse_mode="HTML")

    await state.clear()

@dp.message(F.chat.type == "private", F.from_user.id != ADMIN_ID)
async def handle_user_message(message: types.Message):
    user = message.from_user
    username_str = f"@{user.username}" if user.username else "немає"
    logger.info(f"Новое обращение в поддержку от ID: {user.id} ({user.first_name})")

    reply_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Відповісти", callback_data=f"reply_to_{user.id}")]
        ]
    )

    # Экранируем имя и текст сообщения от пользователя
    clean_name = escape(user.first_name)
    clean_text = escape(message.text)

    admin_notification = (
        f"🔔 <b>НОВЕ ЗВЕРНЕННЯ В ПІДТРИМКУ!</b>\n\n"
        f"👤 <b>Від кого:</b> {clean_name} ({username_str})\n"
        f"🆔 <b>ID користувача:</b> <code>{user.id}</code>\n\n"
        f"💬 <b>Повідомлення:</b>\n{clean_text}"
    )

    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_notification,
            parse_mode="HTML",
            reply_markup=reply_keyboard
        )
        await message.answer(
            "✅ <b>Ваше звернення успішно надіслано!</b>\n\n"
            "Оператор вже отримав сповіщення. Очікуйте на відповідь у цьому чаті.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка отправки обращения админу ID {ADMIN_ID}: {e}", exc_info=True)
        await message.answer("❌ Виникла помилка при відправці звернення.")

async def main():
    init_db()
    logger.info("🤖 Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())