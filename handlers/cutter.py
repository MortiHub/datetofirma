from telebot import types

from config import PARTIAL_OR_FULL, ACTUAL_SIZES_QUANTITY
from sheets.users import is_authorized, get_user_role
import json
import logging

logger = logging.getLogger(__name__)


async def handle_cutter_callbacks(bot, call, user_states, user_data, cutting_requests_sheet):
    callback_data = call.data
    user_id = call.from_user.id

    if callback_data == "view_requests":
        await view_requests(bot, call, user_states, user_data, cutting_requests_sheet)
        return

    elif callback_data.startswith("accept_"):
        request_id = callback_data.replace("accept_", "")
        await accept_request(bot, call, user_states, user_data, cutting_requests_sheet, request_id)

    elif callback_data.startswith("continue_request_"):
        request_id = callback_data.replace("continue_request_", "")
        await continue_request(bot, call, user_states, user_data, cutting_requests_sheet, request_id)

    elif callback_data == "back_to_cutter":
        await back_to_cutter(bot, call, user_states, user_data)

    elif callback_data.startswith("complete_"):
        await complete_request(bot, call, user_states, user_data, cutting_requests_sheet)


async def view_requests(bot, call, user_states, user_data, cutting_requests_sheet):
    user_id = call.from_user.id
    role = get_user_role(user_id, cutting_requests_sheet._spreadsheet.worksheet("Users"))
    if role not in ["Cutter", "Seamstress"]:
        await bot.answer_callback_query(call.id, "❌ Только раскройщики и швеи могут просматривать заявки.",
                                        show_alert=True)
        return

    try:
        requests = cutting_requests_sheet.get_all_records()
        available_requests = [r for r in requests if r.get("Статус") in ["Новая", "В работе"] and (
                    r.get("Статус") == "Новая" or str(r.get("ID раскройщика")) == str(user_id))]

        if not available_requests:
            await bot.answer_callback_query(call.id, "Нет доступных заявок.", show_alert=True)
            await bot.edit_message_text("Нет доступных заявки.", call.message.chat.id, call.message.message_id)
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

        keyboard.append([types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_cutter")])
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.edit_message_text(
            "📋 Доступные заявки на раскрой:",
            call.message.chat.id, call.message.message_id,
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Ошибка при получении заявок: {e}")
        await bot.answer_callback_query(call.id, "Произошла ошибка при загрузке заявок.", show_alert=True)


async def continue_request(bot, call, user_states, user_data, cutting_requests_sheet, request_id):
    user_id = call.from_user.id

    try:
        requests = cutting_requests_sheet.get_all_records()
        row_idx = None
        for idx, req in enumerate(requests, 2):
            if req.get("ID заявки") == request_id:
                row_idx = idx
                break

        if not row_idx:
            await bot.answer_callback_query(call.id, "Заявка не найдена.", show_alert=True)
            return

        current_status = cutting_requests_sheet.cell(row_idx, 6).value
        if current_status != "В работе":
            await bot.answer_callback_query(call.id, "Эта заявка не в работе.", show_alert=True)
            return


        cutter_id = cutting_requests_sheet.cell(row_idx, 9).value
        if str(cutter_id) != str(user_id):
            await bot.answer_callback_query(call.id, "Эта заявка назначена другому пользователю.", show_alert=True)
            return

        sizes_json = cutting_requests_sheet.cell(row_idx, 18).value
        sizes_dict = json.loads(sizes_json) if sizes_json else {}

        if not sizes_dict:
            await bot.edit_message_text(
                "❌ В заявке не указаны размеры. Свяжитесь с администратором.",
                call.message.chat.id, call.message.message_id
            )
            return

        sizes_text = "\nОставшиеся размеры и количества:\n"
        for size, qty in sorted(sizes_dict.items()):
            sizes_text += f"  {size}: {qty}\n"

        if user_id not in user_data:
            user_data[user_id] = {}
        if 'requests' not in user_data[user_id]:
            user_data[user_id]['requests'] = {}
        user_data[user_id]['requests'][request_id] = {
            'row_idx': row_idx,
            'ordered_sizes_dict': sizes_dict,
            'actual_sizes_dict': {},
            'stacks_dict': {},
            'actual_selected_sizes': sorted(sizes_dict.keys()),
            'actual_current_index': 0
        }
        user_data[user_id]['current_request_id'] = request_id

        product_name = cutting_requests_sheet.cell(row_idx, 3).value
        color = cutting_requests_sheet.cell(row_idx, 4).value
        current_actual = int(cutting_requests_sheet.cell(row_idx, 11).value or 0)
        ordered_quantity = sum(sizes_dict.values())
        show_partial = True  # Изменено для всегда доступного partial

        confirmation_text = (
            f"Продолжение заявки {request_id}:\n\n"
            f"Изделие: {product_name}\n"
            f"Цвет ткани: {color}\n"
            f"Оставшиеся:\n{sizes_text}\n\n"
            f"Выберите тип закрытия:"
        )
        keyboard = []
        if show_partial:
            keyboard.append(
                [types.InlineKeyboardButton("Частичное закрытие", callback_data=f"partial_start_{request_id}")])
        keyboard.append([types.InlineKeyboardButton("Полное закрытие", callback_data=f"full_start_{request_id}")])
        keyboard.append([types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")])
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.edit_message_text(
            confirmation_text,
            call.message.chat.id, call.message.message_id,
            reply_markup=reply_markup
        )
        user_states[user_id] = PARTIAL_OR_FULL

    except Exception as e:
        logger.error(f"Ошибка при продолжении заявки {request_id}: {e}")
        await bot.edit_message_text("❌ Произошла ошибка при продолжении заявки.", call.message.chat.id,
                                    call.message.message_id)


async def accept_request(bot, call, user_states, user_data, cutting_requests_sheet, request_id):
    user_id = call.from_user.id

    try:
        requests = cutting_requests_sheet.get_all_records()
        row_idx = None
        for idx, req in enumerate(requests, 2):
            if req.get("ID заявки") == request_id:
                row_idx = idx
                break

        if not row_idx:
            await bot.answer_callback_query(call.id, "Заявка не найдена.", show_alert=True)
            return

        current_status = cutting_requests_sheet.cell(row_idx, 6).value
        if current_status != "Новая":
            await bot.answer_callback_query(call.id, "Эта заявка уже взята в работу.", show_alert=True)
            return

        cutter_id = user_id
        cutter_name = call.from_user.full_name

        cutting_requests_sheet.update_cell(row_idx, 6, "В работе")
        cutting_requests_sheet.update_cell(row_idx, 9, cutter_id)
        cutting_requests_sheet.update_cell(row_idx, 10, cutter_name)

        sizes_json = cutting_requests_sheet.cell(row_idx, 18).value
        sizes_dict = json.loads(sizes_json) if sizes_json else {}

        if not sizes_dict:
            await bot.edit_message_text(
                "❌ В заявке не указаны размеры. Свяжитесь с администратором.",
                call.message.chat.id, call.message.message_id
            )
            return

        sizes_text = "\nРазмеры и количества:\n"
        for size, qty in sorted(sizes_dict.items()):
            sizes_text += f"  {size}: {qty}\n"

        if user_id not in user_data:
            user_data[user_id] = {}
        if 'requests' not in user_data[user_id]:
            user_data[user_id]['requests'] = {}
        user_data[user_id]['requests'][request_id] = {
            'row_idx': row_idx,
            'ordered_sizes_dict': sizes_dict,
            'actual_sizes_dict': {},
            'stacks_dict': {},
            'actual_selected_sizes': sorted(sizes_dict.keys()),
            'actual_current_index': 0
        }
        user_data[user_id]['current_request_id'] = request_id

        product_name = cutting_requests_sheet.cell(row_idx, 3).value
        color = cutting_requests_sheet.cell(row_idx, 4).value
        current_actual = int(cutting_requests_sheet.cell(row_idx, 11).value or 0)
        ordered_quantity = sum(sizes_dict.values())
        show_partial = True  # Изменено для всегда доступного partial

        confirmation_text = (
            f"Заявка {request_id} принята!\n\n"
            f"Изделие: {product_name}\n"
            f"Цвет ткани: {color}\n"
            f"Заказано:\n{sizes_text}\n\n"
            f"Выберите тип закрытия:"
        )
        keyboard = []
        if show_partial:
            keyboard.append(
                [types.InlineKeyboardButton("Частичное закрытие", callback_data=f"partial_start_{request_id}")])
        keyboard.append([types.InlineKeyboardButton("Полное закрытие", callback_data=f"full_start_{request_id}")])
        keyboard.append([types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")])
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.edit_message_text(
            confirmation_text,
            call.message.chat.id, call.message.message_id,
            reply_markup=reply_markup
        )
        user_states[user_id] = PARTIAL_OR_FULL

    except Exception as e:
        logger.error(f"Ошибка при принятии заявки {request_id}: {e}")
        await bot.edit_message_text("❌ Произошла ошибка при принятии заявки.", call.message.chat.id,
                                    call.message.message_id)


async def back_to_cutter(bot, call, user_states, user_data):
    user_id = call.from_user.id
    role = get_user_role(user_id, call.message._bot._sheets_data["users_sheet"])
    keyboard = [
        [types.InlineKeyboardButton("📋 Просмотреть заявки", callback_data="view_requests")]
    ]
    reply_markup = types.InlineKeyboardMarkup(keyboard)

    await bot.edit_message_text(
        f"Главное меню {'раскройщика' if role == 'Cutter' else 'швеи'}:",
        call.message.chat.id, call.message.message_id, reply_markup=reply_markup
    )


async def complete_request(bot, call, user_states, user_data, cutting_requests_sheet):
    request_id = call.data.replace("complete_", "")
    user_id = call.from_user.id

    if user_id not in user_data or 'requests' not in user_data[user_id] or request_id not in user_data[user_id][
        'requests']:
        await bot.edit_message_text("❌ Ошибка: данные заявки не найдены.", call.message.chat.id,
                                    call.message.message_id)
        return

    try:
        row_idx = user_data[user_id]['requests'][request_id]['row_idx']
        current_status = cutting_requests_sheet.cell(row_idx, 6).value
        if current_status == "Выполнена":
            await bot.edit_message_text("❌ Эта заявка уже выполнена.", call.message.chat.id, call.message.message_id)
            return

        cutter_id = cutting_requests_sheet.cell(row_idx, 9).value
        if str(cutter_id) != str(user_id):
            await bot.edit_message_text("❌ Вы не можете завершить эту заявку.", call.message.chat.id,
                                        call.message.message_id)
            return

        product_name = cutting_requests_sheet.cell(row_idx, 3).value
        color = cutting_requests_sheet.cell(row_idx, 4).value
        sizes_json = cutting_requests_sheet.cell(row_idx, 18).value
        ordered_sizes_dict = json.loads(sizes_json) if sizes_json else {}

        keyboard = [
            [types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_completion_{request_id}")],
            [types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]
        ]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.edit_message_text(
            f"Завершение заявки {request_id}:\n\nВведите фактическое количество для размера {sorted(ordered_sizes_dict.keys())[0]}:",
            call.message.chat.id, call.message.message_id,
            reply_markup=reply_markup
        )
        user_data[user_id]['requests'][request_id] = {
            'row_idx': row_idx,
            'ordered_sizes_dict': ordered_sizes_dict,
            'actual_sizes_dict': {},
            'stacks_dict': {},
            'actual_selected_sizes': sorted(ordered_sizes_dict.keys()),
            'actual_current_index': 0
        }
        user_data[user_id]['current_request_id'] = request_id
        user_states[user_id] = ACTUAL_SIZES_QUANTITY

    except Exception as e:
        logger.error(f"Ошибка при проверке заявки {request_id}: {e}")
        await bot.edit_message_text("❌ Произошла ошибка.", call.message.chat.id, call.message.message_id)