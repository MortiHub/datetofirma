from datetime import datetime

from telebot import types

from config import PRODUCT_NAME
from sheets.users import is_authorized, get_user_role
import logging

logger = logging.getLogger(__name__)

async def handle_admin_callbacks(bot, call, user_states, user_data, users_sheet, requests_sheet, cutting_requests_sheet, products_sheet):
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
        await start_cutting_request(bot, call, user_states, user_data, users_sheet, products_sheet)

async def start_cutting_request(bot, call, user_states, user_data, users_sheet, products_sheet):
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


async def notify_admin(bot, request_id, event_type, details, users_sheet):
    """
    Уведомляет администратора о событиях с заявками на раскрой

    Args:
        bot: бот для отправки сообщений
        request_id: ID заявки
        event_type: тип события ('accepted', 'partial_complete', 'full_complete')
        details: словарь с деталями события
        users_sheet: таблица пользователей
    """
    try:
        # Получаем список администраторов
        users = users_sheet.get_all_records()
        admins = [user for user in users if user["Role"].strip() == "Admin"]

        if not admins:
            logger.warning("Не найдено администраторов для уведомления")
            return

        # Формируем сообщение в зависимости от типа события
        if event_type == 'accepted':
            message_text = await generate_accepted_notification(request_id, details)
        elif event_type == 'partial_complete':
            message_text = await generate_partial_complete_notification(request_id, details)
        elif event_type == 'full_complete':
            message_text = await generate_full_complete_notification(request_id, details)
        else:
            return

        # Отправляем сообщение всем администраторам
        for admin in admins:
            try:
                keyboard = [
                    [types.InlineKeyboardButton("📋 Просмотреть заявки", callback_data="view_requests")]
                ]
                reply_markup = types.InlineKeyboardMarkup(keyboard)

                await bot.send_message(
                    admin["ID"],
                    message_text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
                logger.info(f"Уведомление отправлено администратору {admin['ID']}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления администратору {admin['ID']}: {e}")

    except Exception as e:
        logger.error(f"Ошибка в функции уведомления администратора: {e}")


async def generate_accepted_notification(request_id, details):
    """Генерирует текст уведомления о взятии заявки"""
    text = (
        "✅ *Заявка взята в работу*\n\n"
        f"*ID заявки:* {request_id}\n"
        f"*Изделие:* {details.get('product_name', 'N/A')}\n"
        f"*Цвет:* {details.get('color', 'N/A')}\n"
        f"*Раскройщик:* {details.get('cutter_name', 'N/A')}\n"
        f"*ID раскройщика:* {details.get('cutter_id', 'N/A')}\n"
        f"*Дата принятия:* {details.get('accepted_at', 'N/A')}\n\n"
    )

    # Добавляем информацию о заказанных количествах
    if details.get('ordered_sizes'):
        text += "*Заказанные количества:*\n"
        for size, qty in sorted(details['ordered_sizes'].items()):
            text += f"  • Размер {size}: {qty} шт.\n"

    text += "\n📋 Заявка переведена в статус 'В работе'"
    return text


async def generate_partial_complete_notification(request_id, details):
    """Генерирует текст уведомления о частичном закрытии"""
    text = (
        "🔄 *Частичное закрытие заявки*\n\n"
        f"*ID заявки:* {request_id}\n"
        f"*Изделие:* {details.get('product_name', 'N/A')}\n"
        f"*Цвет:* {details.get('color', 'N/A')}\n"
        f"*Раскройщик:* {details.get('cutter_name', 'N/A')}\n"
        f"*Номер заявки:* {details.get('route_list', 'N/A')}\n\n"
    )

    # Добавляем информацию о выполненной работе
    if details.get('completed_sizes'):
        text += "*Выполнено в этом закрытии:*\n"
        for size, qty in sorted(details['completed_sizes'].items()):
            text += f"  • Размер {size}: {qty} шт.\n"

    # Добавляем информацию о стопках
    if details.get('stacks_data'):
        text += "\n*Количество стопок:*\n"
        for size, stacks in sorted(details['stacks_data'].items()):
            if stacks > 0:
                text += f"  • Размер {size}: {stacks} стопок\n"

    # Добавляем общую информацию
    text += f"\n*Общее выполнено:* {details.get('total_completed', 0)}/{details.get('total_ordered', 0)} шт."
    text += f"\n*Расход ткани:* {details.get('fabric_used', 0)} м"
    text += f"\n*Участники:* {details.get('participants', 'N/A')}"

    # Добавляем информацию об остатках
    if details.get('remaining_sizes'):
        text += "\n\n*Остатки по заказу:*\n"
        for size, qty in sorted(details['remaining_sizes'].items()):
            if qty > 0:
                text += f"  • Размер {size}: {qty} шт.\n"

    return text


async def generate_full_complete_notification(request_id, details):
    """Генерирует текст уведомления о полном закрытии"""
    text = (
        "🏁 *Заявка полностью завершена!*\n\n"
        f"*ID заявки:* {request_id}\n"
        f"*Изделие:* {details.get('product_name', 'N/A')}\n"
        f"*Цвет:* {details.get('color', 'N/A')}\n"
        f"*Раскройщик:* {details.get('cutter_name', 'N/A')}\n"
        f"*Номер заявки:* {details.get('route_list', 'N/A')}\n\n"
    )

    # Добавляем итоговую информацию
    text += "*Итоговые выполнения:*\n"
    for size, data in sorted(details.get('final_data', {}).items()):
        ordered = data.get('ordered', 0)
        actual = data.get('actual', 0)
        stacks = data.get('stacks', 0)

        stack_info = f", стопок: {stacks}" if stacks > 0 else ""
        text += f"  • Размер {size}: {actual}/{ordered} шт.{stack_info}\n"

    # Общие итоги
    total_ordered = details.get('total_ordered', 0)
    total_actual = details.get('total_actual', 0)
    total_stacks = details.get('total_stacks', 0)

    text += f"\n*Итого заказано:* {total_ordered} шт."
    text += f"\n*Итого выполнено:* {total_actual} шт."

    if total_stacks > 0:
        text += f"\n*Итого стопок:* {total_stacks}"

    text += f"\n*Общий расход ткани:* {details.get('total_fabric', 0)} м"
    text += f"\n*Участники:* {details.get('participants', 'N/A')}"

    return text