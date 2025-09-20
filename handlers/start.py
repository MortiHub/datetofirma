from telebot import types
from sheets.users import is_authorized, get_user_role
import logging

logger = logging.getLogger(__name__)

async def start_handler(bot, message, users_sheet):
    user_id = message.from_user.id
    logger.info(f"Обработка /start для пользователя {user_id}")
    keyboard = []

    if is_authorized(user_id, users_sheet):
        role = get_user_role(user_id, users_sheet)
        logger.info(f"Роль пользователя {user_id}: {role}")
        if role == "Admin":
            keyboard = [
                [types.InlineKeyboardButton("👥 Просмотр заявок на роли", callback_data="requests")],
                [types.InlineKeyboardButton("✂️ Создать заявку на раскрой", callback_data="new_cutting_request")],
                [types.InlineKeyboardButton("📋 Просмотреть заявки на раскрой", callback_data="view_requests")]
            ]
        elif role == "Cutter":
            keyboard = [
                [types.InlineKeyboardButton("📋 Просмотреть заявки", callback_data="view_requests")]
            ]
        elif role == "Seamstress":
            keyboard = [
                [types.InlineKeyboardButton("📋 Просмотреть заявки", callback_data="view_requests")]
            ]
    else:
        keyboard = [
            [types.InlineKeyboardButton("Подать заявку", callback_data="submit_request")]
        ]

    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.send_message(message.chat.id, "Добро пожаловать! Выберите действие:", reply_markup=reply_markup)