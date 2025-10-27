# handlers/assistant.py
from telebot import types
import logging

logger = logging.getLogger(__name__)


async def notify_assistant(bot, request_id, product_name, color, route_list_number, completion_type, sizes_data,
                           total_data=None, stacks_data=None):  # Добавили stacks_data
    """
    Уведомляет помощницу о необходимости печати штрих-кодов

    Args:
        bot: бот для отправки сообщений
        request_id: ID заявки
        product_name: наименование изделия
        color: цвет изделия
        route_list_number: номер маршрутного листа
        completion_type: тип закрытия ('partial' или 'complete')
        sizes_data: словарь с размерами и количествами
        total_data: общие данные (только для полного закрытия)
        stacks_data: данные о стопках (только для частичного закрытия)
    """
    try:
        # Получаем список помощниц из базы данных
        from main import bot as global_bot
        users_sheet = global_bot._sheets_data["users_sheet"]
        users = users_sheet.get_all_records()

        assistants = [user for user in users if user["Role"].strip() == "Assistant"]

        if not assistants:
            logger.warning("Не найдено помощниц для уведомления")
            return

        # Формируем сообщение в зависимости от типа закрытия
        if completion_type == 'partial':
            message_text = await generate_partial_notification(
                request_id, product_name, color, route_list_number, sizes_data, stacks_data
            )
        else:
            message_text = await generate_complete_notification(
                request_id, product_name, color, route_list_number, total_data
            )

        # Отправляем сообщение всем помощницам
        for assistant in assistants:
            try:
                keyboard = [
                    [types.InlineKeyboardButton("✅ Подтвердить печать", callback_data=f"confirm_print_{request_id}")]
                ]
                reply_markup = types.InlineKeyboardMarkup(keyboard)

                await bot.send_message(
                    assistant["ID"],
                    message_text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
                logger.info(f"Уведомление отправлено помощнице {assistant['ID']}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления помощнице {assistant['ID']}: {e}")

    except Exception as e:
        logger.error(f"Ошибка в функции уведомления помощницы: {e}")

async def generate_partial_notification(request_id, product_name, color, route_list_number, sizes_data, stacks_data=None):
    """Генерирует текст уведомления для частичного закрытия"""
    # Формируем product_color в формате "Изделие (Цвет)"
    product_color = f"{product_name} ({color})"

    text = (
        "🖨️ *Требуется печать штрих-кодов (Частичное закрытие)*\n\n"
        f"*Заявка:* {request_id}\n"
        f"*Номер заявки:* {route_list_number}\n"
        f"*Изделие:* {product_color}\n"
        f"*Тип:* Частичное закрытие\n\n"
        "*Выполненные размеры:*\n"
    )

    for size, quantity in sorted(sizes_data.items()):
        text += f"  • Размер {size}: {quantity} шт.\n"

    # Добавляем информацию о стопках если есть
    if stacks_data:
        text += "\n*Количество стопок:*\n"
        for size, stacks in sorted(stacks_data.items()):
            if stacks > 0:
                text += f"  • Размер {size}: {stacks} стопок\n"

    text += f"\n*Всего в этом закрытии:* {sum(sizes_data.values())} шт."
    text += "\n\n⚠️ Подготовьте штрих-коды для указанных размеров и количеств."

    return text


async def generate_complete_notification(request_id, product_name, color, route_list_number, total_data):
    """Генерирует текст уведомления для полного закрытия"""
    # Формируем product_color в формате "Изделие (Цвет)"
    product_color = f"{product_name} ({color})"

    text = (
        "🖨️ *Требуется печать штрих-кодов (Полное закрытие)*\n\n"
        f"*Заявка:* {request_id}\n"
        f"*Номер заявки:* {route_list_number}\n"
        f"*Изделие:* {product_color}\n"
        f"*Тип:* Полное закрытие\n\n"
        "*Итоговые количества:*\n"
    )

    for size, data in total_data.items():
        # Добавляем информацию о стопках если есть
        stacks_info = f", стопок: {data.get('stacks', 0)}" if data.get('stacks', 0) > 0 else ""
        text += f"  • Размер {size}: {data['actual']} шт. (из {data['ordered']} заказано){stacks_info}\n"

    total_ordered = sum(data['ordered'] for data in total_data.values())
    total_actual = sum(data['actual'] for data in total_data.values())

    text += f"\n*Итого заказано:* {total_ordered} шт."
    text += f"\n*Итого выполнено:* {total_actual} шт."

    # Добавляем общее количество стопок если есть
    total_stacks = sum(data.get('stacks', 0) for data in total_data.values())
    if total_stacks > 0:
        text += f"\n*Итого стопок:* {total_stacks}"

    text += "\n\n⚠️ Подготовьте итоговые штрих-коды для всего заказа."

    return text

async def handle_assistant_callbacks(bot, call, user_states, user_data):
    """Обрабатывает callback'и от помощницы"""
    callback_data = call.data
    user_id = call.from_user.id

    if callback_data.startswith("confirm_print_"):
        request_id = callback_data.replace("confirm_print_", "")
        await confirm_print(bot, call, request_id)

    elif callback_data.startswith("delay_print_"):
        request_id = callback_data.replace("delay_print_", "")
        await delay_print(bot, call, request_id)

    elif callback_data == "print_status":
        await show_print_status(bot, call)

    elif callback_data == "active_requests":
        await show_active_requests(bot, call)


async def confirm_print(bot, call, request_id):
    """Подтверждение печати помощницей"""
    try:
        await bot.answer_callback_query(call.id, "✅ Печать подтверждена")

        # Обновляем сообщение
        keyboard = [[types.InlineKeyboardButton("✅ Напечатано", callback_data="none")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)

        original_text = call.message.text
        new_text = original_text + "\n\n---\n✅ *Печать подтверждена*"

        await bot.edit_message_text(
            new_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        logger.info(f"Помощница подтвердила печать для заявки {request_id}")

    except Exception as e:
        logger.error(f"Ошибка при подтверждении печати: {e}")
        await bot.answer_callback_query(call.id, "❌ Ошибка при подтверждении")


async def delay_print(bot, call, request_id):
    """Отложить печать"""
    try:
        await bot.answer_callback_query(call.id, "🔄 Печать отложена")

        keyboard = [
            [types.InlineKeyboardButton("✅ Подтвердить печать", callback_data=f"confirm_print_{request_id}")],
            [types.InlineKeyboardButton("⏰ Напомнить через час", callback_data=f"remind_print_{request_id}")]
        ]
        reply_markup = types.InlineKeyboardMarkup(keyboard)

        original_text = call.message.text
        new_text = original_text + "\n\n---\n🔄 *Печать отложена*"

        await bot.edit_message_text(
            new_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        logger.info(f"Помощница отложила печать для заявки {request_id}")

    except Exception as e:
        logger.error(f"Ошибка при откладывании печати: {e}")
        await bot.answer_callback_query(call.id, "❌ Ошибка при откладывании")


async def show_print_status(bot, call):
    """Показывает статус печати для помощницы"""
    try:
        from main import bot as global_bot
        cutting_requests_sheet = global_bot._sheets_data["cutting_requests_sheet"]

        requests = cutting_requests_sheet.get_all_records()

        # Фильтруем заявки, требующие печати (в работе или выполненные недавно)
        active_requests = [r for r in requests if r.get("Статус") in ["В работе", "Выполнена"]]

        if not active_requests:
            await bot.edit_message_text(
                "📊 Нет активных заявок, требующих печати.",
                call.message.chat.id,
                call.message.message_id
            )
            return

        status_text = "📊 *Статус печати штрих-кодов:*\n\n"

        for req in active_requests:
            status_icon = "🟢" if req.get("Статус") == "В работе" else "🔵"
            status_text += f"{status_icon} *{req.get('ID заявки', 'N/A')}* - {req.get('Название изделия', 'N/A')}\n"
            status_text += f"   Статус: {req.get('Статус', 'N/A')}\n"
            status_text += f"   Выполнено: {req.get('Фактическое количество', 0)}/{req.get('Количество', 0)}\n\n"

        keyboard = [
            [types.InlineKeyboardButton("🔄 Обновить", callback_data="print_status")],
            [types.InlineKeyboardButton("📋 Активные заявки", callback_data="active_requests")]
        ]
        reply_markup = types.InlineKeyboardMarkup(keyboard)

        await bot.edit_message_text(
            status_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка при показе статуса печати: {e}")
        await bot.answer_callback_query(call.id, "❌ Ошибка при загрузке статуса")


async def show_active_requests(bot, call):
    """Показывает активные заявки для помощницы"""
    try:
        from main import bot as global_bot
        cutting_requests_sheet = global_bot._sheets_data["cutting_requests_sheet"]

        requests = cutting_requests_sheet.get_all_records()
        active_requests = [r for r in requests if r.get("Статус") in ["Новая", "В работе"]]

        if not active_requests:
            await bot.edit_message_text(
                "📋 Нет активных заявок.",
                call.message.chat.id,
                call.message.message_id
            )
            return

        requests_text = "📋 *Активные заявки:*\n\n"

        for req in active_requests:
            status_icon = "🟡" if req.get("Статус") == "Новая" else "🟢"
            requests_text += f"{status_icon} *{req.get('ID заявки', 'N/A')}*\n"
            requests_text += f"   Изделие: {req.get('Название изделия', 'N/A')}\n"
            requests_text += f"   Цвет: {req.get('Цвет ткани', 'N/A')}\n"
            requests_text += f"   Статус: {req.get('Статус', 'N/A')}\n\n"

        keyboard = [
            [types.InlineKeyboardButton("🔄 Обновить", callback_data="active_requests")],
            [types.InlineKeyboardButton("📊 Статус печати", callback_data="print_status")]
        ]
        reply_markup = types.InlineKeyboardMarkup(keyboard)

        await bot.edit_message_text(
            requests_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка при показе активных заявок: {e}")
        await bot.answer_callback_query(call.id, "❌ Ошибка при загрузке заявок")