from telebot import types
from config import *
from sheets.users import is_authorized, get_user_role, has_pending_request
from handlers.admin import handle_admin_callbacks
from handlers.cutter import handle_cutter_callbacks
from handlers.common import handle_common_callbacks
import logging
import json
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


async def callback_handler(bot, call, user_states, user_data, users_sheet, requests_sheet, cutting_requests_sheet,products_sheet):
    await bot.answer_callback_query(call.id)
    callback_data = call.data
    user_id = call.from_user.id
    logger.info(f"Обработка callback для пользователя {user_id}, данные: {callback_data}")

    state = user_states.get(user_id, None)

    if state in [SELECT_COLORS, SIZES_TYPE, SELECT_SIZES, CONFIRM_SIZES] and (
            callback_data in ["sizes_adult", "sizes_child", "sizes_done", "colors_done", "confirm_sizes",
                              "cancel_request"] or
            callback_data.startswith("color_") or
            callback_data.startswith("size_")
    ):
        if callback_data.startswith("color_") or callback_data == "colors_done":
            await select_colors(bot, call, user_states, user_data, products_sheet)
        elif callback_data in ["sizes_adult", "sizes_child"]:
            await process_sizes_type(bot, call, user_states, user_data)
        elif callback_data.startswith("size_") or callback_data == "sizes_done":
            await select_sizes(bot, call, user_states, user_data)
        elif callback_data == "confirm_sizes":
            await confirm_sizes(bot, call, user_states, user_data, cutting_requests_sheet, users_sheet)
        elif callback_data == "cancel_request":
            await cancel_request(bot, call, user_states, user_data, users_sheet)
        return

    if state in [ACTUAL_SIZES_QUANTITY, SIZE_STACKS, FABRIC_USED, PARTICIPANTS, COMMENT, CONFIRM_COMPLETION,
                 PARTIAL_OR_FULL, FINAL_SUM_INPUT] and (
            callback_data.startswith("confirmcomplete_") or
            callback_data.startswith("edit_completion_") or
            callback_data.startswith("cancel_completion_") or
            callback_data.startswith("proceed_completion_") or
            callback_data.startswith("complete_without_data_") or
            callback_data.startswith("partial_complete_") or
            callback_data.startswith("final_complete_") or
            callback_data.startswith("partial_start_") or
            callback_data.startswith("full_start_")
    ):
        if callback_data.startswith("confirmcomplete_"):
            await confirm_completion(bot, call, user_states, user_data, cutting_requests_sheet)
        elif callback_data.startswith("edit_completion_"):
            await edit_completion(bot, call, user_states, user_data, cutting_requests_sheet)
        elif callback_data.startswith("cancel_completion_"):
            await cancel_completion(bot, call, user_states, user_data)
        elif callback_data.startswith("proceed_completion_"):
            request_id = callback_data.replace("proceed_completion_", "")
            if user_id not in user_data or 'requests' not in user_data[user_id] or request_id not in user_data[user_id][
                'requests']:
                await bot.edit_message_text("❌ Ошибка: данные заявки не найдены.", call.message.chat.id,
                                            call.message.message_id)
                return
            actual_selected_sizes = user_data[user_id]['requests'][request_id]['actual_selected_sizes']
            if not actual_selected_sizes:
                await bot.edit_message_text("❌ В заявке нет размеров для ввода.", call.message.chat.id,
                                            call.message.message_id)
                return
            first_size = actual_selected_sizes[0]
            keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
            reply_markup = types.InlineKeyboardMarkup(keyboard)
            await bot.edit_message_text(
                f"Введите фактическое количество для размера {first_size}:",
                call.message.chat.id, call.message.message_id,
                reply_markup=reply_markup
            )
            user_states[user_id] = ACTUAL_SIZES_QUANTITY
        elif callback_data.startswith("complete_without_data_"):
            request_id = callback_data.replace("complete_without_data_", "")
            await complete_without_data(bot, call, user_states, user_data, cutting_requests_sheet, request_id)
        elif callback_data.startswith("partial_complete_"):
            await partial_complete(bot, call, user_states, user_data, cutting_requests_sheet)
        elif callback_data.startswith("final_complete_"):
            await final_complete(bot, call, user_states, user_data, cutting_requests_sheet)
        elif callback_data.startswith("partial_start_"):
            await start_partial_completion(bot, call, user_states, user_data, cutting_requests_sheet)
        elif callback_data.startswith("full_start_"):
            await start_full_completion(bot, call, user_states, user_data, cutting_requests_sheet)
        return

    if not is_authorized(user_id, users_sheet):
        if callback_data == "submit_request":
            if has_pending_request(user_id, requests_sheet):
                await bot.answer_callback_query(call.id,
                                                "У вас уже есть активная заявка! Ожидайте решения администратора.",
                                                show_alert=True)
                return

            keyboard = [
                [
                    types.InlineKeyboardButton("Раскройщик", callback_data="request_cutter"),
                    types.InlineKeyboardButton("Швея", callback_data="request_seamstress")
                ],
                [types.InlineKeyboardButton("Назад", callback_data="start_callback")]
            ]
            reply_markup = types.InlineKeyboardMarkup(keyboard)
            await bot.edit_message_text("Выберите роль:", call.message.chat.id, call.message.message_id,
                                        reply_markup=reply_markup)

        elif callback_data in ["request_cutter", "request_seamstress"]:
            role = "Раскройщик" if callback_data == "request_cutter" else "Швея"
            name = call.from_user.full_name or "Unknown"
            requests_sheet.append_row([str(user_id), name, role, "Pending"])
            await bot.answer_callback_query(call.id, "Ваша заявка отправлена администратору!", show_alert=True)
        elif callback_data == "start_callback":
            await start_callback(bot, call, users_sheet)
        return

    role = get_user_role(user_id, users_sheet)
    if role == "Admin":
        await handle_admin_callbacks(bot, call, user_states, user_data, users_sheet, requests_sheet, cutting_requests_sheet)
    elif role in ["Cutter", "Seamstress"]:
        await handle_cutter_callbacks(bot, call, user_states, user_data, cutting_requests_sheet)
    else:
        await handle_common_callbacks(bot, call, user_states, user_data)

async def select_colors(bot, call, user_states, user_data, products_sheet):
    user_id = call.from_user.id
    callback_data = call.data

    if callback_data == "colors_done":
        if not user_data[user_id].get('selected_colors'):
            await bot.send_message(call.message.chat.id, "❌ Выберите хотя бы один цвет!")
            return
        user_data[user_id]['current_color_index'] = 0
        first_color = user_data[user_id]['selected_colors'][0]
        user_data[user_id]['sizes_dict_per_color'][first_color] = {
            'sizes_type': None,
            'selected_sizes': [],
            'sizes_dict': {},
            'current_size_index': 0
        }
        keyboard = [
            [types.InlineKeyboardButton("Взрослые (34-64)", callback_data="sizes_adult")],
            [types.InlineKeyboardButton("Детские (122-158)", callback_data="sizes_child")],
            [types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")]
        ]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.edit_message_text(f"Выберите тип размеров для цвета '{first_color}':", call.message.chat.id,
                                    call.message.message_id, reply_markup=reply_markup)
        user_states[user_id] = SIZES_TYPE
        return

    elif callback_data.startswith("color_"):
        color = callback_data.replace("color_", "")
        selected_colors = user_data[user_id]['selected_colors']
        if color in selected_colors:
            selected_colors.remove(color)
            user_data[user_id]['sizes_dict_per_color'].pop(color, None)
            await bot.answer_callback_query(call.id, f"Цвет {color} убран из выбора")
        else:
            selected_colors.append(color)
            await bot.answer_callback_query(call.id, f"Цвет {color} добавлен")

        try:
            products = products_sheet.get_all_records()
            colors_list = []
            for prod in products:
                if prod.get("ProductName", "").strip().lower() == user_data[user_id]['product_name'].lower():
                    colors_str = prod.get("Colors", "")
                    if colors_str:
                        colors_list = [c.strip() for c in colors_str.split(",")]
                    break

            keyboard = []
            row = []
            for color in colors_list:
                text = f"✅{color} " if color in selected_colors else color
                row.append(types.InlineKeyboardButton(text, callback_data=f"color_{color}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            keyboard.append([types.InlineKeyboardButton("✅ Готово", callback_data="colors_done")])
            keyboard.append([types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")])
            reply_markup = types.InlineKeyboardMarkup(keyboard)
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка при обновлении выбора цветов: {e}")
            await bot.edit_message_text("❌ Произошла ошибка при выборе цветов.", call.message.chat.id,
                                        call.message.message_id)

async def process_sizes_type(bot, call, user_states, user_data):
    user_id = call.from_user.id
    current_color_index = user_data[user_id]['current_color_index']
    current_color = user_data[user_id]['selected_colors'][current_color_index]
    sizes_type = "adult" if call.data == "sizes_adult" else "child"

    user_data[user_id]['sizes_dict_per_color'][current_color]['sizes_type'] = sizes_type
    user_data[user_id]['sizes_dict_per_color'][current_color]['selected_sizes'] = []
    user_data[user_id]['sizes_dict_per_color'][current_color]['sizes_dict'] = {}

    start, end, step = (34, 64, 2) if sizes_type == "adult" else (122, 158, 6)
    valid_sizes = list(range(start, end + 1, step))

    keyboard = []
    row = []
    for size in valid_sizes:
        row.append(types.InlineKeyboardButton(str(size), callback_data=f"size_{size}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([types.InlineKeyboardButton("✅ Готово", callback_data="sizes_done")])
    keyboard.append([types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")])

    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.edit_message_text(
        f"Выберите размеры для цвета '{current_color}' (нажмите на нужные размеры, затем 'Готово'):",
        call.message.chat.id, call.message.message_id,
        reply_markup=reply_markup
    )
    user_states[user_id] = SELECT_SIZES

async def select_sizes(bot, call, user_states, user_data):
    user_id = call.from_user.id
    callback_data = call.data
    current_color_index = user_data[user_id]['current_color_index']
    current_color = user_data[user_id]['selected_colors'][current_color_index]

    if callback_data == "sizes_done":
        if not user_data[user_id]['sizes_dict_per_color'][current_color].get('selected_sizes'):
            await bot.send_message(call.message.chat.id, "❌ Выберите хотя бы один размер!")
            return

        user_data[user_id]['sizes_dict_per_color'][current_color]['current_size_index'] = 0
        size = user_data[user_id]['sizes_dict_per_color'][current_color]['selected_sizes'][0]
        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(call.message.chat.id, f"Введите количество для размера {size} (цвет: {current_color}):",
                               reply_markup=reply_markup)
        user_states[user_id] = SIZES_QUANTITY
        return

    elif callback_data.startswith("size_"):
        size = int(callback_data.replace("size_", ""))
        selected_sizes = user_data[user_id]['sizes_dict_per_color'][current_color]['selected_sizes']
        if size in selected_sizes:
            selected_sizes.remove(size)
            await bot.answer_callback_query(call.id, f"Размер {size} убран из выбора")
        else:
            selected_sizes.append(size)
            await bot.answer_callback_query(call.id, f"Размер {size} добавлен")

        sizes_type = user_data[user_id]['sizes_dict_per_color'][current_color]['sizes_type']
        start, end, step = (34, 64, 2) if sizes_type == "adult" else (122, 158, 6)
        valid_sizes = list(range(start, end + 1, step))

        keyboard = []
        row = []
        for size in valid_sizes:
            text = f"{size} ✅" if size in selected_sizes else str(size)
            row.append(types.InlineKeyboardButton(text, callback_data=f"size_{size}"))
            if len(row) == 5:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([types.InlineKeyboardButton("✅ Готово", callback_data="sizes_done")])
        keyboard.append([types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")])

        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=reply_markup)

async def confirm_sizes(bot, call, user_states, user_data, cutting_requests_sheet, users_sheet):
    user_id = call.from_user.id

    try:
        data = user_data[user_id]
        product_name = data.get('product_name', 'Не указано')
        colors = data.get('selected_colors', ['Не указан'])
        admin_id = user_id
        admin_name = call.from_user.full_name
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

        request_ids = []
        for color in colors:
            sizes_type = data['sizes_dict_per_color'][color]['sizes_type']
            sizes_dict = data['sizes_dict_per_color'][color]['sizes_dict']
            sizes_type_ru = "Взрослые" if sizes_type == "adult" else "Детские"
            sizes_json = json.dumps(sizes_dict)
            total_quantity = sum(sizes_dict.values())
            request_id = f"CR-{datetime.now().strftime('%Y%m%d%H%M%S')}-{color[:3]}-{str(uuid.uuid4())[:8]}"
            cutting_requests_sheet.append_row([
                request_id, created_at, product_name, color, total_quantity, "Новая",
                admin_id, admin_name, "", "", "", "", "", "", "", "", sizes_type_ru, sizes_json, ""
            ])
            request_ids.append(request_id)
            await notify_cutters(bot, request_id, created_at, product_name, sizes_dict, users_sheet)

        confirmation_text = "✅ Заявки на раскрой созданы!\n\n"
        confirmation_text += f"ID заявок: {', '.join(request_ids)}\n"
        confirmation_text += f"Изделие: {product_name}\n"
        for color in colors:
            sizes_type = data['sizes_dict_per_color'][color]['sizes_type']
            confirmation_text += f"\nЦвет: {color}\n"
            confirmation_text += f"Тип размеров: {'Взрослые' if sizes_type == 'adult' else 'Детские'}\n"
            confirmation_text += "Размеры и количества:\n"
            for size, qty in sorted(data['sizes_dict_per_color'][color]['sizes_dict'].items()):
                confirmation_text += f"  {size}: {qty}\n"
        confirmation_text += f"\nДата: {created_at}"

        keyboard = [[types.InlineKeyboardButton("➕ Создать новую заявку", callback_data="new_cutting_request")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(call.message.chat.id, confirmation_text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка при создании заявки: {e}")
        await bot.send_message(call.message.chat.id, f"❌ Произошла ошибка: {str(e)}. Попробуйте снова.")
    finally:
        user_data.pop(user_id, None)
        user_states.pop(user_id, None)


async def start_partial_completion(bot, call, user_states, user_data, cutting_requests_sheet):
    request_id = call.data.replace("partial_start_", "")
    user_id = call.from_user.id
    if user_id not in user_data or 'requests' not in user_data[user_id] or request_id not in user_data[user_id][
        'requests']:
        await bot.edit_message_text("❌ Ошибка: данные заявки не найдены.", call.message.chat.id,
                                    call.message.message_id)
        return

    data = user_data[user_id]['requests'][request_id]
    actual_selected_sizes = data.get('actual_selected_sizes', [])
    ordered_sizes_dict = data.get('ordered_sizes_dict', {})

    if not actual_selected_sizes:
        await bot.edit_message_text("❌ Нет размеров для ввода. Свяжитесь с администратором.", call.message.chat.id,
                                    call.message.message_id)
        return

    first_size = actual_selected_sizes[0]
    ordered_qty = ordered_sizes_dict.get(first_size, 0)  # Заказанное количество для этого размера

    user_data[user_id]['requests'][request_id]['completion_type'] = 'partial'

    # Формируем динамический текст с размером и количеством
    message_text = f"Начато частичное закрытие заявки {request_id}.\nВведите фактическое количество для размера {first_size} (заказано: {ordered_qty}):"

    # Добавляем клавиатуру для отмены, если нужно (как в других местах кода)
    keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
    reply_markup = types.InlineKeyboardMarkup(keyboard)

    await bot.edit_message_text(message_text, call.message.chat.id, call.message.message_id, reply_markup=reply_markup)
    user_states[user_id] = ACTUAL_SIZES_QUANTITY
    data['actual_current_index'] = 0  # Убедимся, что индекс сброшен для ввода
async def start_full_completion(bot, call, user_states, user_data, cutting_requests_sheet):
    request_id = call.data.replace("full_start_", "")
    user_id = call.from_user.id
    if user_id not in user_data or 'requests' not in user_data[user_id] or request_id not in user_data[user_id]['requests']:
        await bot.edit_message_text("❌ Ошибка: данные заявки не найдены.", call.message.chat.id, call.message.message_id)
        return

    user_data[user_id]['requests'][request_id]['completion_type'] = 'full'
    await bot.edit_message_text("Начато полное закрытие. Введите данные...", call.message.chat.id, call.message.message_id)
    user_states[user_id] = ACTUAL_SIZES_QUANTITY

async def confirm_completion(bot, call, user_states, user_data, cutting_requests_sheet):
    request_id = call.data.replace("confirmcomplete_", "")  # Вычисляем здесь один раз
    user_id = call.from_user.id
    if user_id not in user_data or 'requests' not in user_data[user_id] or request_id not in user_data[user_id]['requests']:
        await bot.edit_message_text("❌ Ошибка: данные заявки не найдены.", call.message.chat.id, call.message.message_id)
        return

    data = user_data[user_id]['requests'][request_id]
    row_idx = data['row_idx']
    completion_type = data.get('completion_type', 'full')  # По умолчанию full

    if completion_type == 'partial':
        await partial_complete(bot, call, user_states, user_data, cutting_requests_sheet, request_id)  # Передаём request_id
    else:
        await final_complete(bot, call, user_states, user_data, cutting_requests_sheet, request_id)  # Передаём request_id

async def final_complete(bot, call, user_states, user_data, cutting_requests_sheet, request_id):  # Добавили request_id как параметр
    user_id = call.from_user.id
    keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.edit_message_text("Введите финальную сумму для полного закрытия:", call.message.chat.id, call.message.message_id, reply_markup=reply_markup)
    user_states[user_id] = FINAL_SUM_INPUT


async def partial_complete(bot, call, user_states, user_data, cutting_requests_sheet,
                           request_id):  # request_id как параметр (из confirm_completion)
    user_id = call.from_user.id
    if user_id not in user_data or 'requests' not in user_data[user_id] or request_id not in user_data[user_id][
        'requests']:
        await bot.edit_message_text("❌ Ошибка: данные заявки не найдены.", call.message.chat.id,
                                    call.message.message_id)
        return

    data = user_data[user_id]['requests'][request_id]
    row_idx = data['row_idx']

    # Вычитаем actual из ordered (остатки)
    ordered_dict = data['ordered_sizes_dict']
    actual_dict = data['actual_sizes_dict']
    for size, qty in actual_dict.items():
        if size in ordered_dict:
            ordered_dict[size] -= qty
            if ordered_dict[size] <= 0:
                del ordered_dict[size]

    # Обновляем JSON остатков (ячейка 18)
    sizes_json = json.dumps(ordered_dict)
    cutting_requests_sheet.update_cell(row_idx, 18, sizes_json)

    # Увеличиваем actual quantity (ячейка 11)
    current_actual = int(cutting_requests_sheet.cell(row_idx, 11).value or 0)
    new_actual = current_actual + sum(actual_dict.values())
    cutting_requests_sheet.update_cell(row_idx, 11, new_actual)

    # Обновляем стопки (ячейка 12, сумма)
    current_stacks = int(cutting_requests_sheet.cell(row_idx, 12).value or 0)
    new_stacks = current_stacks + sum(data['stacks_dict'].values())
    cutting_requests_sheet.update_cell(row_idx, 12, new_stacks)

    # Обновляем расход ткани (ячейка 13, сумма)
    current_fabric = float(cutting_requests_sheet.cell(row_idx, 13).value or 0)
    new_fabric = current_fabric + data.get('fabric_used', 0)
    cutting_requests_sheet.update_cell(row_idx, 13, new_fabric)

    # Обновляем участников (ячейка 14, аппенд через запятую)
    current_part = cutting_requests_sheet.cell(row_idx, 14).value or ""
    new_part = current_part + (", " if current_part else "") + data.get('participants', '')
    cutting_requests_sheet.update_cell(row_idx, 14, new_part)

    # Обновляем номер маршрутного листа (ячейка 15, аппенд через запятую)
    current_route = cutting_requests_sheet.cell(row_idx, 15).value or ""
    new_route = current_route + (", " if current_route else "") + data.get('route_list_number', '')
    cutting_requests_sheet.update_cell(row_idx, 15, new_route)

    # Обновляем фактические детали размеров (ячейка 19, JSON с накоплением)
    current_actual_json = cutting_requests_sheet.cell(row_idx, 19).value
    current_actual_dict = json.loads(current_actual_json) if current_actual_json else {}
    for size, qty in actual_dict.items():
        current_actual_dict[size] = current_actual_dict.get(size, 0) + qty
    new_actual_json = json.dumps(current_actual_dict)
    cutting_requests_sheet.update_cell(row_idx, 19, new_actual_json)

    # Пересчёт расхода на единицу (ячейка 16, optional: total_fabric / total_actual)
    if new_actual > 0:
        fabric_per_unit = round(new_fabric / new_actual, 2)
        cutting_requests_sheet.update_cell(row_idx, 16, fabric_per_unit)

    # НЕ меняем статус! Оставляем "В работе"

    # Уведомление админа о partial с деталями
    admin_id = cutting_requests_sheet.cell(row_idx, 7).value
    product_name = cutting_requests_sheet.cell(row_idx, 3).value
    color = cutting_requests_sheet.cell(row_idx, 4).value
    admin_message = (
        f"✅ Заявка {request_id} частично завершена!\n"
        f"Изделие: {product_name}\n"
        f"Цвет: {color}\n"
        f"Фактическое количество: {sum(actual_dict.values())} (всего: {new_actual})\n"
        f"Стопки: {sum(data['stacks_dict'].values())} (всего: {new_stacks})\n"
        f"Расход ткани: {data.get('fabric_used', 0)} м (всего: {new_fabric})\n"
        f"Участники: {data.get('participants', '')}\n"
        f"Маршрутный лист: {data.get('route_list_number', '')}\n"
        f"Остатки размеров: {sizes_json}"
    )
    await bot.send_message(admin_id, admin_message)

    await bot.edit_message_text(f"✅ Заявка {request_id} частично завершена! Остатки и данные обновлены.",
                                call.message.chat.id, call.message.message_id)

    del user_data[user_id]['requests'][request_id]
    user_data[user_id].pop('current_request_id', None)
    user_states.pop(user_id, None)

async def complete_without_data(bot, call, user_states, user_data, cutting_requests_sheet, request_id):
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
        admin_id = cutting_requests_sheet.cell(row_idx, 7).value

        cutting_requests_sheet.update_cell(row_idx, 6, "Выполнена")

        admin_message = (
            f"✅ Заявка {request_id} завершена без ввода фактических данных!\n"
            f"Раскройщик: {call.from_user.full_name}\n"
            f"Изделие: {product_name}\n"
            f"Цвет ткани: {color}\n"
            f"Заказано:\n"
        )
        for size, qty in sorted(ordered_sizes_dict.items()):
            admin_message += f"  {size}: {qty}\n"

        try:
            await bot.send_message(admin_id, admin_message)
        except Exception as e:
            logger.error(f"Ошибка уведомления администратора: {e}")

        keyboard = [
            [types.InlineKeyboardButton("📋 Посмотреть другие заявки", callback_data="view_requests")]
        ]
        reply_markup = types.InlineKeyboardMarkup(keyboard)

        await bot.edit_message_text(
            "✅ Заявка завершена без ввода фактических данных!",
            call.message.chat.id, call.message.message_id,
            reply_markup=reply_markup
        )

        if 'requests' in user_data[user_id] and request_id in user_data[user_id]['requests']:
            del user_data[user_id]['requests'][request_id]
        if user_data[user_id].get('current_request_id') == request_id:
            user_data[user_id].pop('current_request_id', None)
        user_states.pop(user_id, None)

    except Exception as e:
        logger.error(f"Ошибка завершения заявки {request_id} без данных: {e}")
        await bot.edit_message_text("❌ Произошла ошибка при завершении заявки.", call.message.chat.id,
                                    call.message.message_id)

async def edit_completion(bot, call, user_states, user_data, cutting_requests_sheet):
    request_id = call.data.replace("edit_completion_", "")
    user_id = call.from_user.id
    if user_id not in user_data or 'requests' not in user_data[user_id] or request_id not in user_data[user_id]['requests']:
        await bot.edit_message_text("❌ Ошибка: данные заявки не найдены.", call.message.chat.id, call.message.message_id)
        return

    data = user_data[user_id]['requests'][request_id]
    data['actual_sizes_dict'] = {}
    data['stacks_dict'] = {}
    data['actual_current_index'] = 0

    first_size = data['actual_selected_sizes'][0]
    keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.edit_message_text(
        f"Редактирование заявки {request_id}:\n\nВведите фактическое количество для размера {first_size}:",
        call.message.chat.id, call.message.message_id,
        reply_markup=reply_markup
    )
    user_states[user_id] = ACTUAL_SIZES_QUANTITY

async def cancel_completion(bot, call, user_states, user_data):
    request_id = call.data.replace("cancel_completion_", "")
    user_id = call.from_user.id

    if user_id not in user_data or 'requests' not in user_data[user_id] or request_id not in user_data[user_id]['requests']:
        await bot.edit_message_text("❌ Ошибка: данные заявки не найдены.", call.message.chat.id,
                                    call.message.message_id)
        return

    if 'requests' in user_data[user_id] and request_id in user_data[user_id]['requests']:
        del user_data[user_id]['requests'][request_id]
    if user_data[user_id].get('current_request_id') == request_id:
        user_data[user_id].pop('current_request_id', None)
    user_states.pop(user_id, None)

    keyboard = [
        [types.InlineKeyboardButton("📋 Просмотреть заявки", callback_data="view_requests")]
    ]
    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.edit_message_text(
        f"❌ Завершение заявки {request_id} отменено.",
        call.message.chat.id, call.message.message_id,
        reply_markup=reply_markup
    )

async def cancel_request(bot, call, user_states, user_data, users_sheet):
    user_id = call.from_user.id
    logger.info(f"Обработка cancel_request для пользователя {user_id}")

    user_data.pop(user_id, None)
    user_states.pop(user_id, None)

    if not is_authorized(user_id, users_sheet):
        try:
            await bot.edit_message_text(
                "❌ Доступ запрещен. Подайте заявку на роль.",
                call.message.chat.id,
                call.message.message_id
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения 'Доступ запрещен': {e}")
        return

    role = get_user_role(user_id, users_sheet)
    if not role:
        try:
            await bot.edit_message_text(
                "❌ Ошибка: ваша роль не определена. Свяжитесь с администратором.",
                call.message.chat.id,
                call.message.message_id
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения об ошибке роли: {e}")
        return

    keyboard = []
    if role == "Admin":
        keyboard = [
            [types.InlineKeyboardButton("👥 Просмотр заявок на роли", callback_data="requests")],
            [types.InlineKeyboardButton("✂️ Создать заявку на раскрой", callback_data="new_cutting_request")],
            [types.InlineKeyboardButton("📋 Просмотреть заявки на раскрой", callback_data="view_requests")]
        ]
    elif role in ["Cutter", "Seamstress"]:
        keyboard = [
            [types.InlineKeyboardButton("📋 Просмотреть заявки", callback_data="view_requests")]
        ]
    else:
        try:
            await bot.edit_message_text(
                "❌ Ошибка: неизвестная роль. Свяжитесь с администратором.",
                call.message.chat.id,
                call.message.message_id
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения о неизвестной роли: {e}")
        return

    try:
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.edit_message_text(
            "❌ Создание заявки отменено. Выберите действие:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке меню пользователю {user_id}: {e}")
        try:
            await bot.send_message(
                call.message.chat.id,
                "❌ Создание заявки отменено. Выберите действие:",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке нового сообщения пользователю {user_id}: {e}")

async def start_callback(bot, call, users_sheet):
    user_id = call.from_user.id
    keyboard = []
    if is_authorized(user_id, users_sheet):
        role = get_user_role(user_id, users_sheet)
        if role == "Admin":
            keyboard = [
                [types.InlineKeyboardButton("👥 Просмотр заявок на роли", callback_data="requests")],
                [types.InlineKeyboardButton("✂️ Создать заявку на раскрой", callback_data="new_cutting_request")]
            ]
        elif role in ["Cutter", "Seamstress"]:
            keyboard = [
                [types.InlineKeyboardButton("📋 Просмотреть заявки", callback_data="view_requests")]
            ]
    else:
        keyboard = [
            [types.InlineKeyboardButton("Подать заявку", callback_data="submit_request")]
        ]

    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.edit_message_text("Добро пожаловать! Выберите действие:", call.message.chat.id, call.message.message_id,
                                reply_markup=reply_markup)
async def notify_cutters(bot, request_id, created_at, product_name, sizes_dict, users_sheet):
    try:
        users = users_sheet.get_all_records()
        for user in users:
            if user["Role"].strip() in ["Cutter", "Seamstress"]:
                try:
                    keyboard = [[types.InlineKeyboardButton("📋 Просмотреть заявки", callback_data="view_requests")]]
                    reply_markup = types.InlineKeyboardMarkup(keyboard)
                    message_text = (
                        f"📢 Новая заявка на раскрой!\n"
                        f"ID: {request_id}\n"
                        f"Изделие: {product_name}\n"
                        f"Дата: {created_at}\n"
                        f"Размеры и количества:\n"
                    )
                    for size, qty in sorted(sizes_dict.items()):
                        message_text += f"  {size}: {qty}\n"
                    await bot.send_message(
                        user["ID"],
                        message_text,
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Ошибка при уведомлении пользователя {user['ID']}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}")
