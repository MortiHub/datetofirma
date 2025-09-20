from telebot import types
from sheets.users import is_authorized, get_user_role
import logging

logger = logging.getLogger(__name__)

async def handle_common_callbacks(bot, call, user_states, user_data):
    callback_data = call.data
    user_id = call.from_user.id

    if callback_data == "view_requests":
        await bot.answer_callback_query(call.id, "❌ У вас нет доступа к этой функции.", show_alert=True)
        return

    elif callback_data == "new_cutting_request":
        await bot.answer_callback_query(call.id, "❌ Только администраторы могут создавать заявки.", show_alert=True)
        return

    elif callback_data == "back_to_admin":
        await bot.answer_callback_query(call.id, "❌ У вас нет доступа к этой функции.", show_alert=True)
        return

    elif callback_data == "back_to_cutter":
        await bot.answer_callback_query(call.id, "❌ У вас нет доступа к этой функции.", show_alert=True)
        return