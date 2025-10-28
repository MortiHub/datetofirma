import asyncio
import logging
from telebot.async_telebot import AsyncTeleBot
from telebot import types

from config import TELEGRAM_TOKEN
from utils.logging import setup_logging
from sheets.auth import init_sheets
from handlers.start import start_handler
from handlers.callback import callback_handler
from handlers.text import text_handler

# Настройка логирования
logger = setup_logging()

# Инициализация бота
bot = AsyncTeleBot(TELEGRAM_TOKEN)

# Инициализация Google Sheets
try:
    sheets_data = init_sheets()
    users_sheet = sheets_data["users_sheet"]
    requests_sheet = sheets_data["requests_sheet"]
    cutting_requests_sheet = sheets_data["cutting_requests_sheet"]
    products_sheet = sheets_data["products_sheet"]

    # Сохраняем данные sheets в объекте бота для доступа из обработчиков
    bot._sheets_data = sheets_data
except Exception as e:
    logger.error(f"Ошибка инициализации: {e}")
    raise

# Глобальные переменные
user_states = {}
user_data = {}


# Регистрация обработчиков
@bot.message_handler(commands=['start'])
async def start_wrapper(message):
    await start_handler(bot, message, users_sheet)


@bot.callback_query_handler(func=lambda call: True)
async def callback_wrapper(call):
    await callback_handler(bot, call, user_states, user_data,
                           users_sheet, requests_sheet, cutting_requests_sheet, products_sheet)


@bot.message_handler(func=lambda message: True)
async def text_wrapper(message):
    await text_handler(bot, message, user_states, user_data, cutting_requests_sheet, products_sheet)
@bot.message_handler(content_types=["photo"])
async def handle_qc_photos(message):
    from handlers.quality_control import qc_states  # импортируем состояние
    user_id = message.from_user.id
    state = qc_states.get(user_id, {})

    if state.get("state") == "qc_sending_photos":
        file_id = message.photo[-1].file_id
        state["photos"].append(file_id)
        qc_states[user_id] = state
        await bot.send_message(message.chat.id, f"📸 Фото добавлено ({len(state['photos'])})")

if __name__ == "__main__":
    logger.info("Бот запущен")
    asyncio.run(bot.infinity_polling())