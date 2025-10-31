from telebot import types
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

qc_states = {}  # временное хранение фото брака


async def handle_quality_callbacks(bot, call, cutting_requests_sheet):
    data = call.data
    user_id = call.from_user.id

    if data == "view_requests_qc":
        await view_requests_qc(bot, call, cutting_requests_sheet)
        return

    elif data.startswith("qc_select_request_"):
        request_id = data.replace("qc_select_request_", "")
        await show_request_qc(bot, call, cutting_requests_sheet, request_id)
        return

    elif data.startswith("qc_defect_"):
        request_id, size, stack_num = data.replace("qc_defect_", "").split("_", 2)
        qc_states[user_id] = {
            "state": "qc_sending_photos",
            "photos": [],
            "comment": None,
            "request_id": request_id,
            "size": size,
            "stack_num": stack_num
        }
        kb = [[types.InlineKeyboardButton("✅ Отправить отчет", callback_data="qc_send_defect")]]
        await bot.send_message(
            call.message.chat.id,
            "📸 Отправьте фото брака (можно несколько), затем введите комментарий — что именно не так.\nПосле этого нажмите «✅ Отправить отчет».",
            reply_markup=types.InlineKeyboardMarkup(kb)
        )
        return

    elif data == "qc_send_defect":
        await qc_send_defect(bot, call)
        return

    elif data.startswith("qc_no_defect_"):
        request_id, size, stack_num = data.replace("qc_no_defect_", "").split("_", 2)
        await qc_no_defect(bot, call, request_id, size, stack_num)
        return


async def view_requests_qc(bot, call, sheet):
    """Список заявок для КК"""
    try:
        requests = sheet.get_all_records()
        available = [r for r in requests if r.get("Завершенные стопки")]

        if not available:
            text = "Нет заявок для проверки."
            try:
                await bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
            except Exception:
                await bot.send_message(call.message.chat.id, text)
            return

        kb = []
        for r in available:
            kb.append([types.InlineKeyboardButton(
                f"{r['Номер маршрутного листа']} — {r['Название изделия']} ({r['Цвет ткани']})",
                callback_data=f"qc_select_request_{r['ID заявки']}"
            )])

        text = "📋 Заявки для контроля качества:"
        markup = types.InlineKeyboardMarkup(kb)

        try:
            await bot.edit_message_text(
                text, call.message.chat.id, call.message.message_id, reply_markup=markup
            )
        except Exception as e:
            if "message is not modified" in str(e).lower() or "message to edit not found" in str(e).lower():
                await bot.send_message(call.message.chat.id, text, reply_markup=markup)
            else:
                raise e
    except Exception as e:
        logger.error(f"Ошибка view_requests_qc: {e}")
        await bot.send_message(call.message.chat.id, "⚠️ Ошибка при загрузке заявок.")


async def show_request_qc(bot, call, sheet, request_id):
    """Показ стопок"""
    try:
        requests = sheet.get_all_records()
        req = next((r for r in requests if r.get("ID заявки") == request_id), None)
        if not req:
            await bot.send_message(call.message.chat.id, "❌ Заявка не найдена.")
            return

        stacks = json.loads(req.get("Завершенные стопки", "{}") or "{}")
        checked = json.loads(req.get("Проверенные стопки", "{}") or "{}")

        text = (
            f"🧵 *Заявка:* {req.get('Номер маршрутного листа')}\n"
            f"Изделие: {req.get('Название изделия')}\n"
            f"Цвет: {req.get('Цвет ткани')}\n\n"
        )

        kb = []
        for size, nums in stacks.items():
            for n in nums:
                if int(n) not in checked.get(size, []):
                    kb.append([
                        types.InlineKeyboardButton(f"✅ Нет брака ({size}-{n})",
                                                   callback_data=f"qc_no_defect_{request_id}_{size}_{n}"),
                        types.InlineKeyboardButton(f"⚠️ Сообщить о браке ({size}-{n})",
                                                   callback_data=f"qc_defect_{request_id}_{size}_{n}")
                    ])

        if not kb:
            text += "✅ Все стопки проверены."

        markup = types.InlineKeyboardMarkup(kb)
        try:
            await bot.edit_message_text(
                text, call.message.chat.id, call.message.message_id,
                parse_mode="Markdown", reply_markup=markup
            )
        except Exception:
            await bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        logger.error(f"Ошибка show_request_qc: {e}")
        await bot.send_message(call.message.chat.id, "⚠️ Ошибка при показе стопок.")


async def qc_no_defect(bot, call, request_id, size, stack_num):
    """Без брака"""
    try:
        sheet = bot._sheets_data["cutting_requests_sheet"]
        requests = sheet.get_all_records()
        req = next((r for r in requests if r.get("ID заявки") == request_id), None)
        if not req:
            await bot.send_message(call.message.chat.id, "❌ Заявка не найдена.")
            return

        checked = json.loads(req.get("Проверенные стопки", "{}") or "{}")
        checked.setdefault(size, [])
        if int(stack_num) not in checked[size]:
            checked[size].append(int(stack_num))

        row = requests.index(req) + 2
        headers = sheet.row_values(1)
        if "Проверенные стопки" not in headers:
            sheet.update_cell(1, len(headers) + 1, "Проверенные стопки")
            headers.append("Проверенные стопки")

        col_checked = headers.index("Проверенные стопки") + 1
        sheet.update_cell(row, col_checked, json.dumps(checked, ensure_ascii=False))

        stacks_done = json.loads(req.get("Завершенные стопки", "{}") or "{}")
        stacks_total = json.loads(req.get("Детали стопок", "{}") or "{}")
        raz_done = json.loads(req.get("Детали размеров", "{}") or "{}")
        raz_total = json.loads(req.get("Детали размеров (фактические)", "{}") or "{}")
        total_stacks = sum(stacks_total.values())
        total_done = sum(len(v) for v in stacks_done.values())
        total_checked = sum(len(v) for v in checked.values())

        col_status = headers.index("Статус") + 1
        if total_done == total_stacks and total_checked == total_stacks and raz_done == raz_total:
            sheet.update_cell(row, col_status, "Проверено")
            await bot.send_message(call.message.chat.id, "✅ Все стопки проверены. Заявка завершена.")
        else:
            await bot.send_message(call.message.chat.id, f"✅ Стопка №{stack_num} ({size}) проверена без брака.")
    except Exception as e:
        logger.error(f"Ошибка qc_no_defect: {e}")
        await bot.send_message(call.message.chat.id, "⚠️ Ошибка при отметке.")


async def qc_send_defect(bot, call):
    """Сообщение о браке + комментарий + запись в лист Defects + отметка как проверено"""
    user_id = call.from_user.id
    state = qc_states.get(user_id, {})
    photos = state.get("photos", [])
    comment = state.get("comment")

    if not photos and not comment:
        await bot.send_message(call.message.chat.id, "❗ Добавьте хотя бы фото или комментарий.")
        return

    request_id, size, stack_num = state["request_id"], state["size"], state["stack_num"]
    sheet = bot._sheets_data["cutting_requests_sheet"]
    users_sheet = bot._sheets_data["users_sheet"]
    spreadsheet = bot._sheets_data["spreadsheet"]

    # создаём лист Defects при отсутствии
    try:
        defects_sheet = spreadsheet.worksheet("Defects")
    except Exception:
        defects_sheet = spreadsheet.add_worksheet(title="Defects", rows=200, cols=10)
        defects_sheet.append_row([
            "Дата", "ID заявки", "Номер маршрутного листа", "Изделие",
            "Цвет ткани", "Размер", "Стопка", "Комментарий", "Фото (file_id)", "Проверил"
        ])

    requests = sheet.get_all_records()
    req = next((r for r in requests if r.get("ID заявки") == request_id), None)
    if not req:
        await bot.send_message(call.message.chat.id, "❌ Заявка не найдена.")
        return

    users = users_sheet.get_all_records()
    qc_user = next((u for u in users if str(u.get("ID")) == str(user_id)), {})
    qc_name = qc_user.get("Name", f"ID:{user_id}")

    # === 🔹 Добавляем отметку как проверено ===
    checked = json.loads(req.get("Проверенные стопки", "{}") or "{}")
    checked.setdefault(size, [])
    if int(stack_num) not in checked[size]:
        checked[size].append(int(stack_num))

    row = requests.index(req) + 2
    headers = sheet.row_values(1)
    if "Проверенные стопки" not in headers:
        sheet.update_cell(1, len(headers) + 1, "Проверенные стопки")
        headers.append("Проверенные стопки")
    col_checked = headers.index("Проверенные стопки") + 1
    sheet.update_cell(row, col_checked, json.dumps(checked, ensure_ascii=False))

    # === 🔹 Проверяем, все ли стопки сшиты и проверены ===
    stacks_done = json.loads(req.get("Завершенные стопки", "{}") or "{}")
    stacks_total = json.loads(req.get("Детали стопок", "{}") or "{}")

    total_stacks = sum(stacks_total.values())
    total_done = sum(len(v) for v in stacks_done.values())
    total_checked = sum(len(v) for v in checked.values())

    col_status = headers.index("Статус") + 1
    if total_done == total_stacks and total_checked == total_stacks:
        sheet.update_cell(row, col_status, "Проверено")

    # === 🔹 Отправка админу ===
    caption = (
        f"⚠️ *Сообщение о браке*\n"
        f"Заявка: {req.get('Номер маршрутного листа')}\n"
        f"Изделие: {req.get('Название изделия')}\n"
        f"Цвет: {req.get('Цвет ткани')}\n"
        f"Размер: {size}\n"
        f"Стопка №{stack_num}\n"
        f"Комментарий: {comment or '—'}\n"
        f"Проверил(а): {qc_name}\n"
        f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    admins = [u for u in users if u.get("Role", "").strip().lower() == "admin"]
    for admin in admins:
        try:
            media = [types.InputMediaPhoto(p) for p in photos[:-1]]
            media.append(types.InputMediaPhoto(photos[-1], caption=caption, parse_mode="Markdown"))
            await bot.send_media_group(admin["ID"], media)
        except Exception as e:
            logger.warning(f"Ошибка при отправке админу {admin.get('ID')}: {e}")

    # === 🔹 Запись в лист Defects ===
    # Получаем имя швеи для конкретной стопки
    seamstresses_data = json.loads(req.get("Швеи стопок", "{}") or "{}")
    seamstress_name = None
    if size in seamstresses_data:
        if isinstance(seamstresses_data[size], dict):
            seamstress_name = seamstresses_data[size].get(str(stack_num))
        elif isinstance(seamstresses_data[size], list):
            # если швеи записаны списком — берём первого
            seamstress_name = seamstresses_data[size][0]
    if not seamstress_name:
        seamstress_name = "Не указана"

    # === 🔹 Запись в лист Defects ===
    defects_sheet.append_row([
        datetime.now().strftime("%d.%m.%Y %H:%M"),
        request_id,
        req.get("Номер маршрутного листа"),
        req.get("Название изделия"),
        req.get("Цвет ткани"),
        size,
        stack_num,
        comment or "",
        ", ".join(photos),
        seamstress_name
    ])

    qc_states[user_id] = {}
    await bot.send_message(call.message.chat.id, "✅ Отчёт о браке отправлен и стопка отмечена как проверенная.")

