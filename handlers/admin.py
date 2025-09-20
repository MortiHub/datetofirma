from datetime import datetime

from telebot import types

from config import PRODUCT_NAME
from sheets.users import is_authorized, get_user_role
import logging

logger = logging.getLogger(__name__)

async def handle_admin_callbacks(bot, call, user_states, user_data, users_sheet, requests_sheet, cutting_requests_sheet):
    callback_data = call.data
    user_id = call.from_user.id

    if callback_data == "view_requests":
        await view_requests(bot, call, user_states, user_data, cutting_requests_sheet)
        return

    if callback_data == "requests":
        requests = requests_sheet.get_all_records()
        pending_requests = [r for r in requests if r.get("Status", "").lower() == "pending"]

        if not pending_requests:
            await bot.answer_callback_query(call.id, "Нет активных заявок.", show_alert=True)
            return

        keyboard = []
        for req in pending_requests:
            req_id = req.get("ID", "Unknown")
            keyboard.append([types.InlineKeyboardButton(
                f"{req.get('Name', 'Unknown')} ({req.get('RequestedRole', 'Unknown')})",
                callback_data=f"select_{req_id}"
            )])
        keyboard.append([types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")])

        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.edit_message_text("Список заявок:", call.message.chat.id, call.message.message_id, reply_markup=reply_markup)

    elif callback_data.startswith("select_"):
        req_id = callback_data.replace("select_", "")
        requests = requests_sheet.get_all_records()
        req = next((r for r in requests if str(r.get("ID", "")).strip() == str(req_id)), None)
        if not req:
            await bot.edit_message_text("Заявка не найдена.", call.message.chat.id, call.message.message_id)
            return

        keyboard = [
            [
                types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{req_id}"),
                types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{req_id}")
            ],
            [types.InlineKeyboardButton("🔙 Назад", callback_data="requests")]
        ]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.edit_message_text(
            f"Заявка: {req.get('Name', 'Unknown')} ({req.get('RequestedRole', 'Unknown')})",
            call.message.chat.id, call.message.message_id, reply_markup=reply_markup
        )

    elif callback_data.startswith(("approve_", "reject_")):
        action, req_id = callback_data.split("_", 1)
        requests = requests_sheet.get_all_records()
        row_idx = None
        for idx, req in enumerate(requests, 2):
            if str(req.get("ID", "")).strip() == str(req_id):
                row_idx = idx
                break
        if not row_idx:
            await bot.edit_message_text("Заявка не найдена.", call.message.chat.id, call.message.message_id)
            return

        try:
            if action == "approve":
                requests_sheet.update_cell(row_idx, 4, "Approved")
                role = requests[row_idx - 2].get("RequestedRole", "")
                role_en = "Cutter" if role == "Раскройщик" else "Seamstress"
                users_sheet.append_row([req_id, requests[row_idx - 2].get("Name", "Unknown"), role_en,
                                       datetime.now().strftime("%Y-%m-%d")])
                requests_sheet.delete_rows(row_idx)
                await bot.answer_callback_query(call.id, f"Заявка от {requests[row_idx - 2].get('Name', 'Unknown')} одобрена и удалена!",
                                               show_alert=True)
            else:
                requests_sheet.delete_rows(row_idx)
                await bot.answer_callback_query(call.id, f"Заявка от {requests[row_idx - 2].get('Name', 'Unknown')} отклонена и удалена!",
                                               show_alert=True)
        except Exception as e:
            logger.error(f"Ошибка при {action} заявки ID {req_id}: {e}")
            await bot.edit_message_text(f"Ошибка при обработке заявки: {str(e)}", call.message.chat.id, call.message.message_id)
            return

        requests = requests_sheet.get_all_records()
        pending_requests = [r for r in requests if r.get("Status", "").lower() == "pending"]
        keyboard = []
        if pending_requests:
            for req in pending_requests:
                req_id = req.get("ID", "Unknown")
                keyboard.append([types.InlineKeyboardButton(
                    f"{req.get('Name', 'Unknown')} ({req.get('RequestedRole', 'Unknown')})",
                    callback_data=f"select_{req_id}"
                )])
        else:
            keyboard.append([types.InlineKeyboardButton("Нет активных заявок", callback_data="none")])
        keyboard.append([types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")])

        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.edit_message_text("Список заявок:", call.message.chat.id, call.message.message_id, reply_markup=reply_markup)

    elif callback_data == "back_to_admin":
        keyboard = [
            [types.InlineKeyboardButton("👥 Просмотр заявок на роли", callback_data="requests")],
            [types.InlineKeyboardButton("✂️ Создать заявку на раскрой", callback_data="new_cutting_request")],
            [types.InlineKeyboardButton("📋 Просмотреть заявки на раскрой", callback_data="view_requests")]
        ]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.edit_message_text("Главное меню администратора:", call.message.chat.id, call.message.message_id, reply_markup=reply_markup)

    elif callback_data == "new_cutting_request":
        await start_cutting_request(bot, call, user_states, user_data, users_sheet)

async def start_cutting_request(bot, call, user_states, user_data, users_sheet):
    user_id = call.from_user.id
    logger.info(f"Попытка создания новой заявки на раскрой пользователем {user_id}")

    if not is_authorized(user_id, users_sheet):
        logger.warning(f"Пользователь {user_id} не авторизован")
        await bot.answer_callback_query(call.id, "❌ Вы не авторизованы для создания заявок.", show_alert=True)
        return

    keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")]]
    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.send_message(call.message.chat.id, "Введите название изделия:", reply_markup=reply_markup)
    if user_id not in user_data:
        user_data[user_id] = {}

    user_states[user_id] = PRODUCT_NAME

async def view_requests(bot, call, user_states, user_data, cutting_requests_sheet):
    user_id = call.from_user.id

    try:
        requests = cutting_requests_sheet.get_all_records()
        available_requests = [r for r in requests if r.get("Статус") in ["Новая", "В работе"]]

        if not available_requests:
            await bot.answer_callback_query(call.id, "Нет доступных заявок.", show_alert=True)
            await bot.edit_message_text("Нет доступных заявок.", call.message.chat.id, call.message.message_id)
            return

        keyboard = []
        for req in available_requests:
            req_id = req.get("ID заявки", "Unknown")
            product_name = req.get("Название изделия", "Unknown")
            quantity = req.get("Количество", "Unknown")
            color = req.get("Цвет ткани", "Unknown")
            status = req.get("Статус")
            button_text = f"{product_name} (Цвет: {color}, Кол-во: {quantity}) - {status}"
            callback = f"accept_{req_id}" if status == "Новая" else f"continue_request_{req_id}"
            keyboard.append([
                types.InlineKeyboardButton(text=button_text, callback_data=callback)
            ])

        keyboard.append([types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")])
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.edit_message_text(
            "📋 Доступные заявки на раскрой:",
            call.message.chat.id, call.message.message_id,
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Ошибка при получении заявок: {e}")
        await bot.answer_callback_query(call.id, "Произошла ошибка при загрузке заявок.", show_alert=True)