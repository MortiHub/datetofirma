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
    elif state == COMMENT:
        await process_comment(bot, message, user_states, user_data)
    elif state == AWAITING_ROUTE_LIST:  # Добавляем новый обработчик
        await process_route_list_input(bot, message, user_states, user_data)

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
    bot_message_id = data.get('bot_message_id')
    current_index = data['actual_current_index']
    selected_sizes = data['actual_selected_sizes']
    ordered_sizes_dict = data['ordered_sizes_dict']

    # Если пользователь ввел 0 или пропустил размер, просто переходим к следующему
    user_input = message.text.strip()
    if user_input == "" or user_input == "0":
        # Пропускаем этот размер, не записывая 0
        current_index += 1
        data['actual_current_index'] = current_index

        if current_index < len(selected_sizes):
            next_size = selected_sizes[current_index]
            next_ordered_qty = ordered_sizes_dict.get(next_size, 0)

            # Вычисляем остаток для следующего размера
            existing_actual = data['actual_sizes_dict'].get(next_size, 0)
            remaining_qty = next_ordered_qty - existing_actual

            keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
            reply_markup = types.InlineKeyboardMarkup(keyboard)

            message_text = (
                f"⏭️ Размер пропущен\n\n"
                f"➡️ Введите фактическое количество для размера {next_size} (остаток: {remaining_qty}):\n"
                f"💡 *Подсказка:* Если не выполняли этот размер, введите 0 или оставьте пустым"
            )

            # Редактируем сообщение бота если есть его ID
            if bot_message_id:
                await bot.edit_message_text(
                    message_text,
                    message.chat.id,
                    bot_message_id,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            else:
                # Если нет ID сообщения бота, отправляем новое и сохраняем ID
                sent_message = await bot.send_message(message.chat.id, message_text, reply_markup=reply_markup, parse_mode="Markdown")
                data['bot_message_id'] = sent_message.message_id
            return
        else:
            # Все размеры обработаны (пропущены или введены)
            await finish_actual_input(bot, message, user_states, user_data, data, request_id)
            return

    try:
        quantity = int(user_input)
        if quantity < 0:
            # Отправляем сообщение об ошибке как новое сообщение
            await bot.send_message(message.chat.id, "❌ Количество не может быть отрицательным. Попробуйте снова:")
            return

        # Проверяем, не превышает ли введенное количество остаток
        current_size = selected_sizes[current_index]
        ordered_qty = ordered_sizes_dict.get(current_size, 0)
        existing_actual = data['actual_sizes_dict'].get(current_size, 0)
        remaining_before = ordered_qty - existing_actual

        if quantity > remaining_before:
            # Отправляем сообщение об ошибке как новое сообщение
            await bot.send_message(message.chat.id, f"❌ Нельзя ввести больше {remaining_before} шт. (остаток для размера {current_size}). Попробуйте снова:")
            return

        # Сохраняем введенное количество (добавляем к существующему)
        data['actual_sizes_dict'][current_size] = existing_actual + quantity

    except ValueError:
        # Отправляем сообщение об ошибке как новое сообщение
        await bot.send_message(message.chat.id, "❌ Пожалуйста, введите число. Для пропуска размера введите 0 или оставьте пустым:")
        return

    current_index += 1
    data['actual_current_index'] = current_index

    if current_index < len(selected_sizes):
        next_size = selected_sizes[current_index]
        next_ordered_qty = ordered_sizes_dict.get(next_size, 0)

        # Вычисляем остаток для следующего размера
        existing_actual = data['actual_sizes_dict'].get(next_size, 0)
        remaining_qty = next_ordered_qty - existing_actual

        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)

        message_text = (
            f"➡️ Введите фактическое количество для размера {next_size} (остаток: {remaining_qty}):\n"
            f"💡 *Подсказка:* Если не выполняли этот размер, введите 0 или оставьте пустым"
        )

        # Редактируем сообщение бота если есть его ID
        if bot_message_id:
            await bot.edit_message_text(
                message_text,
                message.chat.id,
                bot_message_id,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            # Если нет ID сообщения бота, отправляем новое и сохраняем ID
            sent_message = await bot.send_message(message.chat.id, message_text, reply_markup=reply_markup, parse_mode="Markdown")
            data['bot_message_id'] = sent_message.message_id
        return
    else:
        await finish_actual_input(bot, message, user_states, user_data, data, request_id)

async def finish_actual_input(bot, message, user_states, user_data, data, request_id):
    """Завершает ввод фактических количеств и переходит к стопкам ТОЛЬКО для размеров с выполненной работой"""
    data['actual_quantity'] = sum(data['actual_sizes_dict'].values())
    user_id = message.from_user.id
    bot_message_id = data.get('bot_message_id')

    # ФИЛЬТРУЕМ: находим только размеры, для которых есть фактические данные (> 0)
    sizes_with_work = []
    for size in data['actual_selected_sizes']:
        if data['actual_sizes_dict'].get(size, 0) > 0:
            sizes_with_work.append(size)

    # Если нет размеров с выполненной работой, сразу переходим к расходу ткани
    if not sizes_with_work:
        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)

        # Редактируем сообщение бота если есть его ID
        if bot_message_id:
            await bot.edit_message_text(
                "Введите расход ткани (в метрах):",
                message.chat.id,
                bot_message_id,
                reply_markup=reply_markup
            )
        else:
            # Если нет ID сообщения бота, отправляем новое и сохраняем ID
            sent_message = await bot.send_message(message.chat.id, "Введите расход ткани (в метрах):",
                                                  reply_markup=reply_markup)
            data['bot_message_id'] = sent_message.message_id

        user_states[user_id] = FABRIC_USED
        return

    # Сохраняем отфильтрованный список размеров для стопок
    data['stacks_selected_sizes'] = sizes_with_work
    data['stacks_current_index'] = 0

    # Берем первый размер с выполненной работой
    first_size_with_data = sizes_with_work[0]

    # Проверяем есть ли уже данные о стопках для этого размера
    existing_stacks = data['stacks_dict'].get(first_size_with_data, 0)
    stack_info = f"\n💾 Сохранено стопок: {existing_stacks}" if existing_stacks > 0 else ""

    keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
    reply_markup = types.InlineKeyboardMarkup(keyboard)

    message_text = (
        f"➡️ Теперь введите количество стопок для размера {first_size_with_data}:"
        f"{stack_info}\n\n"
        f"💡 Совет: Если количество стопок не изменилось, введите 0 или оставьте пустым"
    )

    # Редактируем сообщение бота если есть его ID
    if bot_message_id:
        await bot.edit_message_text(
            message_text,
            message.chat.id,
            bot_message_id,
            reply_markup=reply_markup
        )
    else:
        # Если нет ID сообщения бота, отправляем новое и сохраняем ID
        sent_message = await bot.send_message(message.chat.id, message_text, reply_markup=reply_markup)
        data['bot_message_id'] = sent_message.message_id

    data['actual_current_index'] = 0  # Сброс индекса для стопок
    user_states[user_id] = SIZE_STACKS

async def process_size_stacks(bot, message, user_states, user_data):
    user_id = message.from_user.id
    request_id = user_data[user_id].get('current_request_id')
    if not request_id or request_id not in user_data[user_id]['requests']:
        await bot.send_message(message.chat.id, "❌ Ошибка: данные заявки не найдены.")
        return

    data = user_data[user_id]['requests'][request_id]
    bot_message_id = data.get('bot_message_id')

    # ИСПРАВЛЕНИЕ: используем отдельные переменные для стопок
    current_index = data.get('stacks_current_index', 0)
    selected_sizes = data.get('stacks_selected_sizes', [])  # Только размеры с выполненной работой

    # Если нет размеров для ввода стопок, переходим к расходу ткани
    if not selected_sizes:
        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)

        if bot_message_id:
            await bot.edit_message_text(
                "Введите расход ткани (в метрах):",
                message.chat.id,
                bot_message_id,
                reply_markup=reply_markup
            )
        else:
            sent_message = await bot.send_message(message.chat.id, "Введите расход ткани (в метрах):",
                                                  reply_markup=reply_markup)
            data['bot_message_id'] = sent_message.message_id

        user_states[user_id] = FABRIC_USED
        return

    # Получаем текущий размер
    current_size = selected_sizes[current_index]

    # Если пользователь пропускает ввод стопок (пустой ввод или 0)
    user_input = message.text.strip()
    if user_input == "" or user_input == "0":
        # Пропускаем этот размер, НЕ сохраняя 0 в стопки
        current_index += 1
        data['stacks_current_index'] = current_index

        if current_index < len(selected_sizes):
            next_size = selected_sizes[current_index]
            existing_stacks = data['stacks_dict'].get(next_size, 0)
            stack_info = f"\n💾 Сохранено стопок: {existing_stacks}" if existing_stacks > 0 else ""

            keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
            reply_markup = types.InlineKeyboardMarkup(keyboard)

            message_text = (
                f"⏭️ Стопки для размера пропущены\n\n"
                f"➡️ Введите количество стопок для размера {next_size}:"
                f"{stack_info}\n\n"
                f"💡 *Совет:* Если количество стопок не изменилось, введите 0 или оставьте пустым"
            )

            if bot_message_id:
                await bot.edit_message_text(
                    message_text,
                    message.chat.id,
                    bot_message_id,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            else:
                sent_message = await bot.send_message(message.chat.id, message_text, reply_markup=reply_markup,
                                                      parse_mode="Markdown")
                data['bot_message_id'] = sent_message.message_id
            return
        else:
            # Все стопки обработаны
            keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
            reply_markup = types.InlineKeyboardMarkup(keyboard)

            if bot_message_id:
                await bot.edit_message_text(
                    "Введите расход ткани (в метрах):",
                    message.chat.id,
                    bot_message_id,
                    reply_markup=reply_markup
                )
            else:
                sent_message = await bot.send_message(message.chat.id, "Введите расход ткани (в метрах):",
                                                      reply_markup=reply_markup)
                data['bot_message_id'] = sent_message.message_id

            user_states[user_id] = FABRIC_USED
            return

    try:
        stacks = int(user_input)
        if stacks < 0:
            await bot.send_message(message.chat.id,
                                   "❌ Количество стопок не может быть отрицательным. Попробуйте снова:")
            return

        # Сохраняем стопки только если введено положительное число
        if stacks > 0:
            data['stacks_dict'][current_size] = stacks
        # Если введен 0, НЕ перезаписываем существующие стопки

    except ValueError:
        await bot.send_message(message.chat.id,
                               "❌ Пожалуйста, введите число. Для пропуска введите 0 или оставьте пустым:")
        return

    current_index += 1
    data['stacks_current_index'] = current_index

    if current_index < len(selected_sizes):
        next_size = selected_sizes[current_index]
        existing_stacks = data['stacks_dict'].get(next_size, 0)
        stack_info = f"\n💾 Сохранено стопок: {existing_stacks}" if existing_stacks > 0 else ""

        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)

        message_text = (
            f"➡️ Введите количество стопок для размера {next_size}:"
            f"{stack_info}\n\n"
            f"💡 *Совет:* Если количество стопок не изменилось, введите 0 или оставьте пустым"
        )

        if bot_message_id:
            await bot.edit_message_text(
                message_text,
                message.chat.id,
                bot_message_id,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            sent_message = await bot.send_message(message.chat.id, message_text, reply_markup=reply_markup,
                                                  parse_mode="Markdown")
            data['bot_message_id'] = sent_message.message_id
        return
    else:
        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)

        if bot_message_id:
            await bot.edit_message_text(
                "Введите расход ткани (в метрах):",
                message.chat.id,
                bot_message_id,
                reply_markup=reply_markup
            )
        else:
            sent_message = await bot.send_message(message.chat.id, "Введите расход ткани (в метрах):",
                                                  reply_markup=reply_markup)
            data['bot_message_id'] = sent_message.message_id

        user_states[user_id] = FABRIC_USED


async def process_fabric_used(bot, message, user_states, user_data):
    user_id = message.from_user.id
    request_id = user_data[user_id].get('current_request_id')
    if not request_id:
        await bot.send_message(message.chat.id, "❌ Ошибка: ID заявки не найден.")
        return

    try:
        fabric_used = float(message.text.strip().replace(',', '.'))
        if fabric_used < 0:
            await bot.send_message(message.chat.id, "❌ Расход ткани не может быть отрицательным. Попробуйте снова:")
            return
    except ValueError:
        await bot.send_message(message.chat.id, "❌ Пожалуйста, введите число (например, 5.5). Попробуйте снова:")
        return

    # Сохраняем расход ткани
    user_data[user_id]['requests'][request_id]['fabric_used'] = fabric_used

    # Получаем список раскройщиков
    users_sheet = bot._sheets_data["users_sheet"]
    users = users_sheet.get_all_records()
    cutters = [user for user in users if user.get("Role", "").strip() == "Cutter"]

    if not cutters:
        await bot.send_message(message.chat.id, "❌ Нет доступных раскройщиков. Перейдите к комментарию:")
        user_data[user_id]['requests'][request_id]['participants'] = ""
        await bot.send_message(message.chat.id, "Комментарий (опционально, или нажмите /skip):")
        user_states[user_id] = COMMENT
        return

    # Инициализируем selected_participants
    user_data[user_id]['requests'][request_id]['selected_participants'] = []

    # Создаём клавиатуру для выбора участников
    keyboard = []
    row = []
    for cutter in cutters:
        name = cutter.get("Name", "Unknown")
        user_id_cutter = cutter.get("ID", "")
        row.append(types.InlineKeyboardButton(name, callback_data=f"participant_{user_id_cutter}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([types.InlineKeyboardButton("✅ Готово", callback_data=f"participants_done_{request_id}")])
    keyboard.append([types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")])

    reply_markup = types.InlineKeyboardMarkup(keyboard)

    # Проверяем маршрутный лист в таблице
    data = user_data[user_id]['requests'][request_id]
    try:
        from main import bot as global_bot
        cutting_requests_sheet = global_bot._sheets_data["cutting_requests_sheet"]
        row_idx = data['row_idx']
        current_route_list = cutting_requests_sheet.cell(row_idx, 15).value

        if current_route_list and current_route_list.strip():
            user_data[user_id]['requests'][request_id]['route_list_number'] = current_route_list.strip()

            # ВАЖНО: Показываем участников ДО подтверждения
            await bot.send_message(message.chat.id, "Выберите участников раскройки (можно выбрать несколько):",
                                   reply_markup=reply_markup)
            user_states[user_id] = SELECT_PARTICIPANTS
            return

    except Exception as e:
        logger.error(f"Ошибка при проверке маршрутного листа: {e}")

    # Если маршрутного листа нет в таблице, все равно переходим к выбору участников
    await bot.send_message(message.chat.id, "Выберите участников раскройки (можно выбрать несколько):",
                           reply_markup=reply_markup)
    user_states[user_id] = SELECT_PARTICIPANTS




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

    data = user_data[user_id]['requests'][request_id]

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

    # Если маршрутного листа нет в таблице, запрашиваем у пользователя
    keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
    reply_markup = types.InlineKeyboardMarkup(keyboard)

    # Отправляем новое сообщение с запросом номера заявки
    await bot.send_message(
        message.chat.id,
        "📝 Введите номер маршрутного листа:",
        reply_markup=reply_markup
    )

    # Устанавливаем состояние ожидания ввода номера маршрутного листа
    user_states[user_id] = AWAITING_ROUTE_LIST


async def process_route_list_input(bot, message, user_states, user_data):
    user_id = message.from_user.id
    request_id = user_data[user_id].get('current_request_id')

    if not request_id or request_id not in user_data[user_id]['requests']:
        await bot.send_message(message.chat.id, "❌ Ошибка: данные заявки не найдены.")
        return

    route_list_number = message.text.strip()
    if not route_list_number:
        await bot.send_message(message.chat.id, "❌ Номер заявки не может быть пустым. Попробуйте снова:")
        return

    # Сохраняем номер маршрутного листа
    user_data[user_id]['requests'][request_id]['route_list_number'] = route_list_number
    data = user_data[user_id]['requests'][request_id]

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

async def generate_partial_confirmation(data, route_list_number):
    """Генерирует текст подтверждения для partial закрытия"""
    text = "✅ Подтвердите частичное закрытие:\n\n"
    text += f"Номер заявки: {route_list_number}\n"
    text += "Фактические количества:\n"

    for size, qty in data.get('actual_sizes_dict', {}).items():
        text += f"  Размер {size}: {qty} шт.\n"

    # Добавляем информацию о стопках
    if data.get('stacks_dict'):
        text += "\n📦 Количество стопок:\n"
        for size, stacks in data.get('stacks_dict', {}).items():
            if stacks > 0:
                text += f"  Размер {size}: {stacks} стопок\n"

    text += f"\nРасход ткани: {data.get('fabric_used', 0)} м"
    text += f"\nУчастники: {data.get('participants', '')}"

    return text



async def generate_completion_confirmation(data, route_list_number, completion_type):
    """Генерирует текст подтверждения"""
    text = f"✅ Подтвердите {completion_type} закрытие:\n\n"
    text += f"Номер заявки: {route_list_number}\n"

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