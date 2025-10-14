from telebot import types

from config import *
from handlers.callback import notify_seamstresses
from sheets.users import is_authorized, get_user_role
import logging
import json

logger = logging.getLogger(__name__)

async def text_handler(bot, message, user_states, user_data, cutting_requests_sheet, products_sheet):
    user_id = message.from_user.id
    state = user_states.get(user_id, None)

    if state == PRODUCT_NAME:
        await process_product_name(bot, message, user_states, user_data, products_sheet)
    elif state == COLOR:
        await process_color(bot, message, user_states, user_data)
    elif state == SIZES_QUANTITY:
        await process_sizes_quantity(bot, message, user_states, user_data)
    elif state == ACTUAL_SIZES_QUANTITY:
        await process_actual_sizes_quantity(bot, message, user_states, user_data)
    elif state == SIZE_STACKS:
        await process_size_stacks(bot, message, user_states, user_data)
    elif state == FABRIC_USED:
        await process_fabric_used(bot, message, user_states, user_data)
    elif state == PARTICIPANTS:
        await process_participants(bot, message, user_states, user_data)
    elif state == COMMENT:
        await process_comment(bot, message, user_states, user_data)

async def process_product_name(bot, message, user_states, user_data, products_sheet):
    user_id = message.from_user.id
    product_name = message.text.strip()

    if not product_name:
        await bot.send_message(message.chat.id, "❌ Название изделия не может быть пустым. Попробуйте снова:")
        return

    # Получаем доступные цвета для этого изделия из базы данных
    products = products_sheet.get_all_records()
    colors_list = []
    for prod in products:
        if prod.get("ProductName", "").strip().lower() == product_name.lower():
            colors_str = prod.get("Colors", "")
            if colors_str:
                colors_list = [c.strip() for c in colors_str.split(",")]
            break

    if not colors_list:
        await bot.send_message(message.chat.id, "❌ Для этого изделия нет доступных цветов. Попробуйте другое изделие:")
        return

    user_data[user_id] = {
        'product_name': product_name,
        'selected_colors': [],
        'sizes_dict_per_color': {},
        'current_color_index': 0
    }

    # Создаем клавиатуру с кнопками цветов
    keyboard = []
    row = []
    for color in colors_list:
        row.append(types.InlineKeyboardButton(color, callback_data=f"color_{color}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([types.InlineKeyboardButton("✅ Готово", callback_data="colors_done")])
    keyboard.append([types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")])

    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.send_message(message.chat.id, "Выберите цвета ткани:", reply_markup=reply_markup)
    user_states[user_id] = SELECT_COLORS

async def process_color(bot, message, user_states, user_data):
    user_id = message.from_user.id
    color = message.text.strip()

    if not color:
        await bot.send_message(message.chat.id, "❌ Цвет ткани не может быть пустым. Попробуйте снова:")
        return

    user_data[user_id]['selected_colors'] = [color]
    user_data[user_id]['sizes_dict_per_color'][color] = {
        'sizes_type': None,
        'selected_sizes': [],
        'sizes_dict': {},
        'current_size_index': 0
    }
    user_data[user_id]['current_color_index'] = 0

    keyboard = [
        [types.InlineKeyboardButton("Взрослые (34-64)", callback_data="sizes_adult")],
        [types.InlineKeyboardButton("Детские (122-158)", callback_data="sizes_child")],
        [types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")]
    ]
    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.send_message(message.chat.id, f"Выберите тип размеров для цвета '{color}':", reply_markup=reply_markup)
    user_states[user_id] = SIZES_TYPE

async def process_sizes_quantity(bot, message, user_states, user_data):
    user_id = message.from_user.id
    current_color_index = user_data[user_id]['current_color_index']
    current_color = user_data[user_id]['selected_colors'][current_color_index]
    current_size_index = user_data[user_id]['sizes_dict_per_color'][current_color]['current_size_index']
    selected_sizes = user_data[user_id]['sizes_dict_per_color'][current_color]['selected_sizes']

    try:
        quantity = int(message.text.strip())
        if quantity < 0:
            await bot.send_message(message.chat.id, "❌ Количество не может быть отрицательным. Попробуйте снова:")
            return
    except ValueError:
        await bot.send_message(message.chat.id, "❌ Пожалуйста, введите число. Попробуйте снова:")
        return

    user_data[user_id]['sizes_dict_per_color'][current_color]['sizes_dict'][
        selected_sizes[current_size_index]] = quantity
    current_size_index += 1
    user_data[user_id]['sizes_dict_per_color'][current_color]['current_size_index'] = current_size_index

    if current_size_index < len(selected_sizes):
        next_size = selected_sizes[current_size_index]
        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(message.chat.id, f"Введите количество для размера {next_size} (цвет: {current_color}):",
                               reply_markup=reply_markup)
        return
    else:
        current_color_index += 1
        user_data[user_id]['current_color_index'] = current_color_index
        if current_color_index < len(user_data[user_id]['selected_colors']):
            next_color = user_data[user_id]['selected_colors'][current_color_index]
            user_data[user_id]['sizes_dict_per_color'][next_color] = {
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
            await bot.send_message(message.chat.id, f"Выберите тип размеров для цвета '{next_color}':",
                                   reply_markup=reply_markup)
            user_states[user_id] = SIZES_TYPE
            return
        else:
            total_quantity = 0
            for color in user_data[user_id]['selected_colors']:
                total_quantity += sum(user_data[user_id]['sizes_dict_per_color'][color]['sizes_dict'].values())

            if total_quantity == 0:
                await bot.send_message(message.chat.id, "❌ Общее количество не может быть нулевым. Начните заново:")
                return

            user_data[user_id]['quantity'] = total_quantity
            confirmation_text = "✅ Подтвердите данные:\n\n"
            confirmation_text += f"Изделие: {user_data[user_id]['product_name']}\n"
            for color in user_data[user_id]['selected_colors']:
                sizes_dict = user_data[user_id]['sizes_dict_per_color'][color]['sizes_dict']
                confirmation_text += f"Цвет: {color}\n"
                for size, qty in sorted(sizes_dict.items()):
                    confirmation_text += f"  {size}: {qty}\n"

            keyboard = [
                [types.InlineKeyboardButton("✔ Подтвердить", callback_data="confirm_sizes")],
                [types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")]
            ]
            reply_markup = types.InlineKeyboardMarkup(keyboard)
            await bot.send_message(message.chat.id, confirmation_text, reply_markup=reply_markup)
            user_states[user_id] = CONFIRM_SIZES

async def process_actual_sizes_quantity(bot, message, user_states, user_data):
    user_id = message.from_user.id
    request_id = user_data[user_id].get('current_request_id')
    if not request_id or request_id not in user_data[user_id]['requests']:
        await bot.send_message(message.chat.id, "❌ Ошибка: данные заявки не найдены.")
        return

    data = user_data[user_id]['requests'][request_id]
    current_index = data['actual_current_index']
    selected_sizes = data['actual_selected_sizes']

    try:
        quantity = int(message.text.strip())
        if quantity < 0:
            await bot.send_message(message.chat.id, "❌ Количество не может быть отрицательным. Попробуйте снова:")
            return
    except ValueError:
        await bot.send_message(message.chat.id, "❌ Пожалуйста, введите число. Попробуйте снова:")
        return

    current_size = selected_sizes[current_index]
    data['actual_sizes_dict'][current_size] = quantity
    current_index += 1
    data['actual_current_index'] = current_index

    if current_index < len(selected_sizes):
        next_size = selected_sizes[current_index]
        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(message.chat.id, f"Введите фактическое количество для размера {next_size}:", reply_markup=reply_markup)
        return
    else:
        data['actual_quantity'] = sum(data['actual_sizes_dict'].values())
        first_size = selected_sizes[0]
        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(message.chat.id, f"Введите количество стопок для размера {first_size}:", reply_markup=reply_markup)
        data['actual_current_index'] = 0  # Сброс индекса для стопок
        user_states[user_id] = SIZE_STACKS

async def process_size_stacks(bot, message, user_states, user_data):
    user_id = message.from_user.id
    request_id = user_data[user_id].get('current_request_id')
    if not request_id or request_id not in user_data[user_id]['requests']:
        await bot.send_message(message.chat.id, "❌ Ошибка: данные заявки не найдены.")
        return

    data = user_data[user_id]['requests'][request_id]
    current_index = data['actual_current_index']
    selected_sizes = data['actual_selected_sizes']

    try:
        stacks = int(message.text.strip())
        if stacks < 0:
            await bot.send_message(message.chat.id, "❌ Количество стопок не может быть отрицательным. Попробуйте снова:")
            return
    except ValueError:
        await bot.send_message(message.chat.id, "❌ Пожалуйста, введите число. Попробуйте снова:")
        return

    current_size = selected_sizes[current_index]
    data['stacks_dict'][current_size] = stacks
    current_index += 1
    data['actual_current_index'] = current_index

    if current_index < len(selected_sizes):
        next_size = selected_sizes[current_index]
        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(message.chat.id, f"Введите количество стопок для размера {next_size}:", reply_markup=reply_markup)
        return
    else:
        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(message.chat.id, "Введите расход ткани (в метрах):", reply_markup=reply_markup)
        user_states[user_id] = FABRIC_USED

async def process_fabric_used(bot, message, user_states, user_data):
    user_id = message.from_user.id
    request_id = user_data[user_id].get('current_request_id')
    if not request_id or request_id not in user_data[user_id]['requests']:
        await bot.send_message(message.chat.id, "❌ Ошибка: данные заявки не найдены.")
        return

    try:
        fabric_used = float(message.text.strip())
        if fabric_used < 0:
            await bot.send_message(message.chat.id, "❌ Расход ткани не может быть отрицательным. Попробуйте снова:")
            return
    except ValueError:
        await bot.send_message(message.chat.id, "❌ Пожалуйста, введите число. Попробуйте снова:")
        return

    user_data[user_id]['requests'][request_id]['fabric_used'] = fabric_used

    keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.send_message(message.chat.id, "Введите участников (через запятую):", reply_markup=reply_markup)
    user_states[user_id] = PARTICIPANTS


async def process_participants(bot, message, user_states, user_data):
    user_id = message.from_user.id
    request_id = user_data[user_id].get('current_request_id')
    if not request_id or request_id not in user_data[user_id]['requests']:
        await bot.send_message(message.chat.id, "❌ Ошибка: данные заявки не найдены.")
        return

    participants = message.text.strip()
    user_data[user_id]['requests'][request_id]['participants'] = participants

    data = user_data[user_id]['requests'][request_id]

    # Проверяем маршрутный лист
    try:
        from main import bot as global_bot
        cutting_requests_sheet = global_bot._sheets_data["cutting_requests_sheet"]
        row_idx = data['row_idx']
        current_route_list = cutting_requests_sheet.cell(row_idx, 15).value

        if current_route_list and current_route_list.strip():
            user_data[user_id]['requests'][request_id]['route_list_number'] = current_route_list.strip()

            # ВАЖНО: Для partial закрытия - сразу подтверждение (финальной суммы нет)
            confirmation_text = await generate_partial_confirmation(data, current_route_list.strip())
            keyboard = [
                [types.InlineKeyboardButton("✔ Подтвердить", callback_data=f"partial_complete_{request_id}")],
                [types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_completion_{request_id}")],
                [types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]
            ]
            reply_markup = types.InlineKeyboardMarkup(keyboard)
            await bot.send_message(message.chat.id, confirmation_text, reply_markup=reply_markup)
            user_states[user_id] = CONFIRM_COMPLETION
            return

    except Exception as e:
        logger.error(f"Ошибка при проверке маршрутного листа: {e}")

    # Если маршрутного листа нет, запрашиваем его
    keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.send_message(message.chat.id, "Введите номер маршрутного листа:", reply_markup=reply_markup)
    user_states[user_id] = COMMENT


async def process_comment(bot, message, user_states, user_data):
    user_id = message.from_user.id
    request_id = user_data[user_id].get('current_request_id')
    if not request_id or request_id not in user_data[user_id]['requests']:
        await bot.send_message(message.chat.id, "❌ Ошибка: данные заявки не найдены.")
        return

    route_list_number = message.text.strip()
    if not route_list_number:
        await bot.send_message(message.chat.id, "❌ Номер маршрутного листа не может быть пустым. Попробуйте снова:")
        return

    user_data[user_id]['requests'][request_id]['route_list_number'] = route_list_number
    data = user_data[user_id]['requests'][request_id]

    # ВАЖНО: Только для partial закрытия (full больше не используется)
    confirmation_text = await generate_partial_confirmation(data, route_list_number)
    keyboard = [
        [types.InlineKeyboardButton("✔ Подтвердить", callback_data=f"partial_complete_{request_id}")],
        [types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_completion_{request_id}")],
        [types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]
    ]
    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.send_message(message.chat.id, confirmation_text, reply_markup=reply_markup)
    user_states[user_id] = CONFIRM_COMPLETION

async def generate_partial_confirmation(data, route_list_number):
    """Генерирует текст подтверждения для partial закрытия"""
    text = "✅ Подтвердите частичное закрытие:\n\n"
    text += f"Маршрутный лист: {route_list_number}\n"
    text += "Фактические количества:\n"

    for size, qty in data.get('actual_sizes_dict', {}).items():
        text += f"  Размер {size}: {qty} шт.\n"

    text += f"\nСтопки: {sum(data.get('stacks_dict', {}).values())}"
    text += f"\nРасход ткани: {data.get('fabric_used', 0)} м"
    text += f"\nУчастники: {data.get('participants', '')}"

    return text


async def process_comment(bot, message, user_states, user_data):
    user_id = message.from_user.id
    request_id = user_data[user_id].get('current_request_id')
    if not request_id or request_id not in user_data[user_id]['requests']:
        await bot.send_message(message.chat.id, "❌ Ошибка: данные заявки не найдены.")
        return

    route_list_number = message.text.strip()
    if not route_list_number:
        await bot.send_message(message.chat.id, "❌ Номер маршрутного листа не может быть пустым. Попробуйте снова:")
        return

    # Сохраняем номер маршрутного листа
    user_data[user_id]['requests'][request_id]['route_list_number'] = route_list_number

    data = user_data[user_id]['requests'][request_id]

    if data.get('completion_type') == 'partial':
        # Для partial закрытия
        confirmation_text = await generate_partial_confirmation(data, route_list_number)
        keyboard = [
            [types.InlineKeyboardButton("✔ Подтвердить", callback_data=f"partial_complete_{request_id}")],
            [types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_completion_{request_id}")],
            [types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]
        ]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(message.chat.id, confirmation_text, reply_markup=reply_markup)
        user_states[user_id] = CONFIRM_COMPLETION
    else:
        # Для full закрытия
        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(message.chat.id, "Введите итоговую сумму выполненного:", reply_markup=reply_markup)


async def generate_completion_confirmation(data, route_list_number, completion_type):
    """Генерирует текст подтверждения"""
    text = f"✅ Подтвердите {completion_type} закрытие:\n\n"
    text += f"Маршрутный лист: {route_list_number}\n"

    if completion_type == "partial":
        text += "Фактические количества:\n"
        for size, qty in data.get('actual_sizes_dict', {}).items():
            text += f"  Размер {size}: {qty} шт.\n"
    else:
        text += f"Итоговая сумма: {data.get('final_sum', 0)}\n"

    text += f"\nСтопки: {sum(data.get('stacks_dict', {}).values())}"
    text += f"\nРасход ткани: {data.get('fabric_used', 0)} м"
    text += f"\nУчастники: {data.get('participants', '')}"

    return text
async def process_final_sum(bot, message, user_states, user_data, cutting_requests_sheet):
    user_id = message.from_user.id
    request_id = user_data[user_id].get('current_request_id')
    if not request_id or request_id not in user_data[user_id]['requests']:
        await bot.send_message(message.chat.id, "❌ Ошибка: данные заявки не найдены.")
        return

    try:
        final_sum = int(message.text.strip())
        if final_sum < 0:
            await bot.send_message(message.chat.id, "❌ Сумма не может быть отрицательной.")
            return
    except ValueError:
        await bot.send_message(message.chat.id, "❌ Введите число.")
        return

    try:
        data = user_data[user_id]['requests'][request_id]

        # Проверяем, можно ли выполнять полное закрытие
        row_idx = data['row_idx']
        current_status = cutting_requests_sheet.cell(row_idx, 6).value
        if current_status == "Выполнена":
            await bot.send_message(message.chat.id, "❌ Эта заявка уже выполнена.")
            return

        cutter_id = cutting_requests_sheet.cell(row_idx, 9).value
        if str(cutter_id) != str(user_id):
            await bot.send_message(message.chat.id, "❌ Вы не можете завершить эту заявку.")
            return

        product_name = cutting_requests_sheet.cell(row_idx, 3).value
        color = cutting_requests_sheet.cell(row_idx, 4).value
        admin_id = cutting_requests_sheet.cell(row_idx, 7).value

        # Обновляем сумму и статус
        cutting_requests_sheet.update_cell(row_idx, 11, final_sum)
        cutting_requests_sheet.update_cell(row_idx, 6, "Выполнена")

        # Получаем полные данные о заказе
        ordered_sizes_json = cutting_requests_sheet.cell(row_idx, 18).value
        ordered_sizes_dict = json.loads(ordered_sizes_json) if ordered_sizes_json else {}

        actual_sizes_json = cutting_requests_sheet.cell(row_idx, 19).value
        actual_sizes_dict = json.loads(actual_sizes_json) if actual_sizes_json else {}

        # Создаем/обновляем лист с полной информацией
        spreadsheet = cutting_requests_sheet._spreadsheet
        route_list_number = data.get('route_list_number', 'unknown')
        sheet_title = f"{route_list_number}-{color}"

        try:
            new_sheet = spreadsheet.worksheet(sheet_title)
        except:
            new_sheet = spreadsheet.add_worksheet(title=sheet_title, rows=50, cols=9)
            new_sheet.append_row([
                "Наименование изделия", "Размер", "Количество (заказано)", "Фактическое количество",
                "Количество стопок", "Цвет ткани", "Расход ткани (м)", "Расход на единицу (м)", "Участники"
            ])
            new_sheet.format("A1:I1",
                             {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}})

        # Добавляем данные по каждому размеру
        for size in sorted(set(list(ordered_sizes_dict.keys()) + list(actual_sizes_dict.keys()))):
            ordered_qty = ordered_sizes_dict.get(size, 0)
            actual_qty = actual_sizes_dict.get(size, 0)
            stacks = data['stacks_dict'].get(size, 0) if data.get('stacks_dict') else 0

            new_sheet.append_row([
                product_name, size, ordered_qty, actual_qty, stacks,
                color, data.get('fabric_used', 0),
                round(data.get('fabric_used', 0) / final_sum, 2) if final_sum > 0 else 0,
                data.get('participants', '')
            ])

        # Добавляем итоговую строку
        fabric_per_unit = data.get('fabric_used', 0) / final_sum if final_sum > 0 else 0
        new_sheet.append_row([
            product_name, "ИТОГО", sum(ordered_sizes_dict.values()), final_sum,
            sum(data.get('stacks_dict', {}).values()) if data.get('stacks_dict') else 0,
            color, data.get('fabric_used', 0), round(fabric_per_unit, 2), data.get('participants', '')
        ])

        logger.info(f"Добавлена полная информация в лист {sheet_title}")

        # Уведомление администратора
        admin_message = (
            f"✅ Заявка {request_id} полностью завершена!\n"
            f"Раскройщик: {message.from_user.full_name}\n"
            f"Изделие: {product_name}\n"
            f"Цвет ткани: {color}\n"
            f"Общая сумма выполненного: {final_sum}\n"
            f"Расход ткани: {data.get('fabric_used', 0)} м\n"
        )

        try:
            await bot.send_message(admin_id, admin_message)
        except Exception as e:
            logger.error(f"Ошибка уведомления администратора: {e}")

        # Уведомление швей
        await notify_seamstresses(bot, request_id, product_name, color, actual_sizes_dict,
                                  cutting_requests_sheet._spreadsheet.worksheet("Users"))

        keyboard = [
            [types.InlineKeyboardButton("📋 Просмотреть заявки", callback_data="view_requests")]
        ]
        reply_markup = types.InlineKeyboardMarkup(keyboard)

        await bot.send_message(message.chat.id, f"✅ Заявка {request_id} полностью завершена с суммой {final_sum}!",
                               reply_markup=reply_markup)

        # Очистка данных
        del user_data[user_id]['requests'][request_id]
        if user_data[user_id].get('current_request_id') == request_id:
            user_data[user_id].pop('current_request_id', None)
        user_states.pop(user_id, None)

    except Exception as e:
        logger.error(f"Ошибка полного завершения заявки {request_id}: {e}")
        await bot.send_message(message.chat.id, "❌ Произошла ошибка при завершении заявки.")


