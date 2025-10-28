# handlers/seamstress.py
from telebot import types
from datetime import datetime
import json
import logging
import calendar

logger = logging.getLogger(__name__)

# === Главный обработчик ===

async def handle_seamstress_callbacks(bot, call, user_states, user_data, cutting_requests_sheet):
    callback_data = call.data
    user_id = call.from_user.id

    if callback_data == "view_requests":
        await view_requests(bot, call, cutting_requests_sheet)
        return

    elif callback_data.startswith("select_request_"):
        request_id = callback_data.replace("select_request_", "")
        await show_request_details(bot, call, cutting_requests_sheet, request_id)
        return

    elif callback_data.startswith("choose_stack_"):
        data = callback_data.replace("choose_stack_", "")
        request_id, size = data.rsplit("_", 1)
        await choose_stack(bot, call, request_id, size, cutting_requests_sheet)
        return

    elif callback_data.startswith("confirm_stack_"):
        data = callback_data.replace("confirm_stack_", "")
        request_id, size, stack_num = data.rsplit("_", 2)
        await confirm_stack(bot, call, cutting_requests_sheet, bot._sheets_data["users_sheet"])

        return

    elif callback_data == "back_to_seamstress":
        await back_to_seamstress(bot, call)
        return
    elif callback_data == "done_stack":
        await bot.send_message(call.message.chat.id, "⚠️ Эта стопка уже сшита ✅")
        return


# === Просмотр заявок ===

async def view_requests(bot, call, cutting_requests_sheet):
    """Показать заявки для швеи"""
    try:
        requests = cutting_requests_sheet.get_all_records()
        available = [r for r in requests if r.get("Статус") in ["В работе", "Выполнена", "Частично сшито"]]

        if not available:
            await bot.answer_callback_query(call.id, "Нет доступных заявок.", show_alert=True)
            await bot.edit_message_text("Нет доступных заявок.", call.message.chat.id, call.message.message_id)
            return

        keyboard = []
        for req in available:
            req_id = req.get("ID заявки")
            req_num = req.get("Номер маршрутного листа")
            num = req.get("Номер заявки", req_num)
            color = req.get("Цвет ткани", "—")
            status = req.get("Статус", "")
            keyboard.append([
                types.InlineKeyboardButton(
                    f"{color} ({num}) — {status}",
                    callback_data=f"select_request_{req_id}"
                )
            ])

        keyboard.append([types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_seamstress")])
        await bot.edit_message_text(
            "📋 Заявки для пошива:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=types.InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Ошибка при просмотре заявок: {e}")
        await bot.answer_callback_query(call.id, "Ошибка при загрузке заявок.", show_alert=True)


# === Детали заявки ===

async def show_request_details(bot, call, cutting_requests_sheet, request_id):
    """Показать детали по размерам и стопкам"""
    try:
        requests = cutting_requests_sheet.get_all_records()
        req = next((r for r in requests if r.get("ID заявки") == request_id), None)
        if not req:
            await bot.answer_callback_query(call.id, "Заявка не найдена.", show_alert=True)
            return

        name = req.get("Название изделия", "—")
        color = req.get("Цвет ткани", "—")
        stacks_dict = json.loads(req.get("Детали стопок", "{}") or "{}")

        if not stacks_dict:
            await bot.edit_message_text("❌ Для этой заявки нет информации о стопках.", call.message.chat.id, call.message.message_id)
            return

        text = f"🧵 *Заявка:* {req.get('Номер маршрутного листа')}\n\n"
        text += f"Изделие: {name}\nЦвет: {color}\n\n📦 Остаток стопок по размерам:\n"
        for size, count in sorted(stacks_dict.items(), key=lambda x: int(x[0])):
            text += f"• Размер {size}: {count} стопок\n"

        text += "\nВыберите размер для завершения:"
        keyboard = []
        for size, count in stacks_dict.items():
            if count > 0:
                keyboard.append([types.InlineKeyboardButton(f"Размер {size}", callback_data=f"choose_stack_{request_id}_{size}")])

        keyboard.append([types.InlineKeyboardButton("🔙 Назад", callback_data="view_requests")])
        await bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=types.InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка show_request_details: {e}")
        await bot.answer_callback_query(call.id, "Ошибка при открытии заявки.", show_alert=True)


# === Выбор стопки ===

async def choose_stack(bot, call, request_id, size, cutting_requests_sheet):
    """Показать все стопки, отмечая завершённые галочкой"""
    try:
        requests = cutting_requests_sheet.get_all_records()
        req = next((r for r in requests if r.get("ID заявки") == request_id), None)
        if not req:
            await bot.send_message(call.message.chat.id, "❌ Заявка не найдена.")
            return

        stacks_dict = json.loads(req.get("Детали стопок", "{}") or "{}")

        # 🔥 Читаем актуальные данные по "Завершённые стопки" напрямую из таблицы
        row_idx = next((i + 2 for i, r in enumerate(requests) if r.get("ID заявки") == request_id), None)
        done_cell_value = cutting_requests_sheet.cell(row_idx, 21).value  # столбец U (21)
        done_raw = done_cell_value or "{}"

        try:
            tmp = json.loads(done_raw)
            if isinstance(tmp, str):
                done_stacks = json.loads(tmp)
            else:
                done_stacks = tmp
        except Exception:
            try:
                done_stacks = json.loads(done_raw.replace("'", '"'))
            except Exception:
                done_stacks = {}

        done_list = [int(x) for x in done_stacks.get(size, [])]

        total_stacks = stacks_dict.get(size, 0)
        if total_stacks <= 0:
            await bot.send_message(call.message.chat.id, "❌ Нет стопок для этого размера.")
            return

        text = (
            f"📏 Размер {size}\n\n"
            f"Выберите стопку, которую вы завершили.\n\n"
            f"✅ — уже сшито"
        )

        keyboard = []
        for i in range(1, total_stacks + 1):
            if i in done_list:
                keyboard.append([types.InlineKeyboardButton(f"✅ Стопка №{i} (сшито)", callback_data="done_stack")])
            else:
                keyboard.append([types.InlineKeyboardButton(f"Стопка №{i}", callback_data=f"confirm_stack_{request_id}_{size}_{i}")])

        keyboard.append([types.InlineKeyboardButton("🔙 Назад", callback_data=f"select_request_{request_id}")])

        await bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=types.InlineKeyboardMarkup(keyboard)
        )

        logger.info(f"[Швея] Размер {size} — завершённые стопки: {done_list}")

    except Exception as e:
        logger.error(f"Ошибка choose_stack: {e}")
        await bot.send_message(call.message.chat.id, "⚠️ Ошибка при выборе стопки.")


# === Завершение пошива стопки ===

async def confirm_stack(bot, call, cutting_requests_sheet, users_sheet):
    """
    Обработка завершения стопки швеёй:
    - добавляет номер стопки в 'Завершенные стопки'
    - записывает имя швеи в 'Швеи стопок'
    - обновляет статус заявки
    """
    try:
        user_id = call.from_user.id
        data = call.data.replace("confirm_stack_", "")
        request_id, size, stack_num = data.split("_", 2)
        stack_num = int(stack_num)

        # Загружаем заявку
        requests = cutting_requests_sheet.get_all_records()
        req = next((r for r in requests if r.get("ID заявки") == request_id), None)
        if not req:
            await bot.send_message(call.message.chat.id, "❌ Заявка не найдена.")
            return

        completed_stacks = json.loads(req.get("Завершенные стопки", "{}") or "{}")
        seamstresses = json.loads(req.get("Швеи стопок", "{}") or "{}")

        completed_stacks.setdefault(size, [])
        if stack_num in completed_stacks[size]:
            await bot.send_message(call.message.chat.id, f"⚠️ Стопка №{stack_num} (размер {size}) уже отмечена.")
            return

        completed_stacks[size].append(stack_num)
        completed_stacks[size].sort()

        # Имя швеи
        users = users_sheet.get_all_records()
        seamstress = next((u for u in users if str(u.get("ID")) == str(user_id)), None)
        seamstress_name = seamstress.get("Name", f"ID:{user_id}") if seamstress else f"ID:{user_id}"
        seamstresses.setdefault(size, {})[str(stack_num)] = seamstress_name

        # Обновляем в таблице
        row = requests.index(req) + 2
        headers = cutting_requests_sheet.row_values(1)

        col_completed = headers.index("Завершенные стопки") + 1
        col_seamstress = headers.index("Швеи стопок") + 1
        col_status = headers.index("Статус") + 1

        cutting_requests_sheet.update_cell(row, col_completed, json.dumps(completed_stacks, ensure_ascii=False))
        cutting_requests_sheet.update_cell(row, col_seamstress, json.dumps(seamstresses, ensure_ascii=False))

        # Проверяем — всё ли сшито
        stacks_info = json.loads(req.get("Детали стопок", "{}") or "{}")
        total = sum(stacks_info.values())
        done = sum(len(v) for v in completed_stacks.values())

        if done >= total:
            cutting_requests_sheet.update_cell(row, col_status, "Сшито")
            await bot.send_message(call.message.chat.id, "✅ Все стопки завершены. Заявка полностью сшита.")
        else:
            cutting_requests_sheet.update_cell(row, col_status, "Частично сшито")
            await bot.send_message(call.message.chat.id, f"✅ Стопка №{stack_num} (размер {size}) завершена.")

    except Exception as e:
        logger.error(f"Ошибка confirm_stack: {e}")
        await bot.send_message(call.message.chat.id, "⚠️ Ошибка при завершении стопки.")

# === Отчёт ===

async def append_to_report(bot, req, seamstress_name, size, stack_num, qty_for_stack, status):
    try:
        spreadsheet = bot._sheets_data["cutting_requests_sheet"]._spreadsheet
        month_ru = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }[datetime.now().month]
        sheet_title = f"Швейный отчет — {month_ru} {datetime.now().year}"

        try:
            report = spreadsheet.worksheet(sheet_title)
        except:
            report = spreadsheet.add_worksheet(title=sheet_title, rows=1000, cols=10)
            report.append_row(["Дата", "Месяц", "Швея", "Номер заявки", "Изделие", "Цвет", "Размер", "№ стопки", "Кол-во изделий", "Статус"])

        report.append_row([
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            month_ru,
            seamstress_name,
            req.get("Номер маршрутного листа"),
            req.get("Название изделия"),
            req.get("Цвет ткани"),
            size,
            stack_num,
            qty_for_stack,
            status
        ])
    except Exception as e:
        logger.error(f"Ошибка записи в отчет: {e}")


# === Меню ===

async def back_to_seamstress(bot, call):
    keyboard = [[types.InlineKeyboardButton("📋 Просмотреть заявки", callback_data="view_requests")]]
    await bot.edit_message_text("Главное меню швеи:", call.message.chat.id, call.message.message_id, reply_markup=types.InlineKeyboardMarkup(keyboard))


# === Уведомления ===

async def notify_quality_control(bot, num, product, color, size, stack_num, seamstress_name):
    try:
        users_sheet = bot._sheets_data["users_sheet"]
        qc = [u for u in users_sheet.get_all_records() if u.get("Role", "").strip() == "Контроль качества"]
        text = (
            f"🧵 *Контроль качества*\n\n"
            f"Стопка №{stack_num} (размер {size}) отмечена как сшитая.\n"
            f"Изделие: {product}\nЦвет: {color}\nШвея: {seamstress_name}\n"
            f"Заявка: {num}\n"
            f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        for user in qc:
            await bot.send_message(user["ID"], text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка уведомления контроля качества: {e}")


async def notify_admin(bot, num, product, color, seamstress_name):
    try:
        users_sheet = bot._sheets_data["users_sheet"]
        admins = [u for u in users_sheet.get_all_records() if u.get("Role", "").strip() == "Admin"]
        text = (
            f"✅ *Заявка полностью сшита!*\n\n"
            f"Изделие: {product}\nЦвет: {color}\n"
            f"Швея: {seamstress_name}\n"
            f"Заявка: {num}\n"
            f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        for admin in admins:
            await bot.send_message(admin["ID"], text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка уведомления администратора: {e}")
