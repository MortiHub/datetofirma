import os
import logging
from datetime import datetime
import asyncio
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telebot.async_telebot import AsyncTeleBot
from telebot import types
import json

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()


# Константы для состояний разговора
(
    PRODUCT_NAME, COLOR, SIZES_TYPE, SELECT_SIZES, SIZES_QUANTITY, CONFIRM_SIZES,  # Для создания заявки
    ACTUAL_SIZES_QUANTITY, SIZE_STACKS, FABRIC_USED, PARTICIPANTS, COMMENT, CONFIRM_COMPLETION,  # Для завершения заявки
    VIEW_REQUESTS,  # Для просмотра заявок
    COLOR_SELECTION  # Новое состояние для выбора цвета
) = range(14)

# Проверка TELEGRAM_TOKEN
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8271216736:AAHBqFT4ErMWXXKp0Txozy4ZjtNQJfw56lk")
if not TELEGRAM_TOKEN:
    logger.error("Переменная окружения TELEGRAM_TOKEN не установлена.")
    raise ValueError("TELEGRAM_TOKEN не найден. Убедитесь, что он указан в файле .env или корректен.")

# Настройка Google Sheets
GOOGLE_CREDENTIALS = {
    "type": "service_account",
    "project_id": "rishtan-fab",
    "private_key_id": "33319145950bfe7865ad6292cdf21c1732406a4d",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCNQue0zauKuXar\nOaPeVFvDFiEKvVHI7z+6IJcLe3XG+l0//VgFfZ+G4FmF7M+5ForEB97h1LLrzH3T\nZIjAWMUOqgc8JLnuja2b1G+WZo5xaIgzqenYuKOpmR2FKAfl/g5rtMhKhgRgGfFF\nhEJ1u30THLlV4mqKT0KqEs7tHIDAKKV6N6imFt7sB8y8/tjSw0uB/SllMNyiX6jM\nhHycpSiqH1nFssdQq2pm8ugTDZKKyH/GXVa1VTsIUvQdOu0Qkt1u/XjpY9kBa1wT\nkhFi4+H3poik83uVwMD/3VJuiws42Gd0uspauZNHVt86g3uh4g/apfQuH5hvDuZd\nijs/1ZuFAgMBAAECggEAAoMdlsgPlGx+8UWZpfMPHLWQid3bDf0/P2Kj/QbJjevW\n67PoNFTLGP11ah3PheWiOyE+s/px4iKlXDSOAAm0G3Inpcira9QmMb7B60VQpDCt\nN2n+qCWEd5gq/7q6BTuS6xRweW7PthvQACH9gpV+gHAC1cWsimAledvSxUG8Am7P\n2aqQ+M9Zj0VndsptAux5VzkXAjqgqYTD/g3MzHgZopNeqpfXWA08rTy4UwvwPTA7\n7/9qiE9pJPKRDtPKKm+hv6R23Y/6VglNmHb20KtOoISujS857P1IQfBuv5iWdEpR\ngVqs3s7aGj7LWPsumVHTviQAN3fFN8zgJvdKkuiSQwKBgQDF06QSUwYPVDM3uNNP\nYgtb/q2LIuXbmfa8z23/5cHq/FWEsKWERBxBp1qHM8yNmUHbaT8tEYvgbpRGu14M\nDgX1ngUDlxfdf615zpd5X0ZOW1Faz5knEOW8ZUq02WGJe8uHBed9fEMoLpPlyqaN\nPOyGjtKsp0N95VRoJaMzQ5BcSwKBgQC2zQiE/9uvRzo6Qj6wkhu1Jy8PMqsDovK/\nqMncwFrRBjIcshk/HnFYv0nXNDM6gn/qRVFxonsrTCmlDxbB/W7iC5HhfgqMsO9+\n0d6/MSpqdwjWAORa12XICsVsQ+2kQAK1O+/qQCg+RGJrJ3t/6TQfUrDTcxgi+pts\nWhH2svxlbwKBgQCXpiENRwXLNHG60n1ySieJExd4JH1uNX2WybB6TWe1OlBYUo3f\ncdLzZVYZdNTm60g36Vtbsiq3Fi2mdzWmKg3ZdpRDZ00NKDYUvRETIr0jjg80fRXb\ng7GJFWEKd+W0XejsjdMiN+LHZ8VKj2nTtZNfpxbK8cHkPavR1qBfyPheNwKBgBbB\n+eCM9e2hYXdlTeavmfF4mlw7A51lSPFhcxgffm7tZYm7BnecM6JH1kqLfiE3o/Mn\nhBcwkkL2rWyWL1AhXA+aPyQii++uC3Lvb9q/pTcx8JCr9cH1dP9tj9yFrG05Ztzn\nRFwWdqwh2VrbxH1NLCcGJWt9tbCNIJJhuEDNUazTAoGAJ9ukDTNok2ycvJNard/I\nRX4T3gGEkFpioaSWkx27uJlyZnlinvUB8wDHeiNvBIfaBYy5Rxv7xKuiJWsEjwzq\nPzxRYicosMatzeYXLmmNAI1dYHY4tye4Oq96QQ/ZwTwKMBaC0VEo3qFYdC2JKm7O\nygbG1PPIsn0HPzrE9xIHrsw=\n-----END PRIVATE KEY-----\n",
    "client_email": "rihtan-fab@rishtan-fab.iam.gserviceaccount.com",
    "client_id": "106390835829056664101",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/rihtan-fab%40rishtan-fab.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com"
}

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Инициализация Google Sheets
def init_sheets():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open("FabricData")

        try:
            users_sheet = spreadsheet.worksheet("Users")
        except gspread.WorksheetNotFound:
            users_sheet = spreadsheet.add_worksheet(title="Users", rows=100, cols=4)
            users_sheet.append_row(["ID", "Name", "Role", "JoinDate"])

        try:
            requests_sheet = spreadsheet.worksheet("RoleRequests")
        except gspread.WorksheetNotFound:
            requests_sheet = spreadsheet.add_worksheet(title="RoleRequests", rows=100, cols=4)
            requests_sheet.append_row(["ID", "Name", "RequestedRole", "Status"])

        expected_headers = [
            "ID заявки", "Дата создания", "Название изделия", "Цвет ткани",
            "Количество", "Статус", "ID администратора", "Имя администратора",
            "ID раскройщика", "Имя раскройщика", "Фактическое количество",
            "Количество стопок", "Расход ткани", "Участники раскроя", "Номер маршрутного листа", "Расход на единицу",
            "Тип размеров", "Детали размеров", "Детали размеров (фактические)"
        ]

        try:
            cutting_requests_sheet = spreadsheet.worksheet("CuttingRequests")
            current_headers = cutting_requests_sheet.row_values(1)
            if current_headers != expected_headers:
                logger.warning("Заголовки в листе CuttingRequests не соответствуют ожидаемым. Синхронизируем...")
                cutting_requests_sheet.resize(rows=1)
                cutting_requests_sheet.resize(rows=100, cols=len(expected_headers))
                cutting_requests_sheet.append_row(expected_headers)
                cutting_requests_sheet.format("A1:S1", {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
                })
                logger.info("Заголовки в листе CuttingRequests обновлены")
        except gspread.WorksheetNotFound:
            cutting_requests_sheet = spreadsheet.add_worksheet(title="CuttingRequests", rows=100, cols=len(expected_headers))
            cutting_requests_sheet.append_row(expected_headers)
            cutting_requests_sheet.format("A1:S1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
            })
            logger.info("Создан новый лист CuttingRequests с правильными заголовками")

        # Новый лист для продуктов и цветов
        try:
            products_sheet = spreadsheet.worksheet("Products")
        except gspread.WorksheetNotFound:
            products_sheet = spreadsheet.add_worksheet(title="Products", rows=100, cols=2)
            products_sheet.append_row(["ProductName", "Colors"])  # Colors - строка с цветами через запятую, напр. "Красный, Синий, Зеленый"
            products_sheet.format("A1:B1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
            })
            logger.info("Создан новый лист Products")

        logger.info("Google Sheets успешно инициализирован")
        return {
            "client": client,
            "spreadsheet": spreadsheet,
            "users_sheet": users_sheet,
            "requests_sheet": requests_sheet,
            "cutting_requests_sheet": cutting_requests_sheet,
            "products_sheet": products_sheet  # Добавлен
        }
    except Exception as e:
        logger.error(f"Ошибка при инициализации Google Sheets: {e}")
        raise

# Инициализируем Google Sheets
sheets_data = init_sheets()
users_sheet = sheets_data["users_sheet"]
requests_sheet = sheets_data["requests_sheet"]
cutting_requests_sheet = sheets_data["cutting_requests_sheet"]
products_sheet = sheets_data["products_sheet"]  # Добавлен
# Проверка авторизации
def is_authorized(user_id: int) -> bool:
    try:
        users = users_sheet.get_all_records()
        for user in users:
            if str(user["ID"]).strip() == str(user_id) and user["Role"].strip() in ["Admin", "Cutter", "Seamstress"]:
                return True
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке авторизации: {e}")
        return False

# Проверка роли
def get_user_role(user_id: int) -> str:
    try:
        users = users_sheet.get_all_records()
        for user in users:
            if str(user["ID"]).strip() == str(user_id):
                return user["Role"].strip()
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении роли для ID {user_id}: {e}")
        return None

# Проверка наличия ожидающей заявки
def has_pending_request(user_id: int) -> bool:
    try:
        requests = requests_sheet.get_all_records()
        for req in requests:
            if str(req.get("ID", "")).strip() == str(user_id) and req.get("Status", "").lower() == "pending":
                return True
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке заявок пользователя {user_id}: {e}")
        return False

bot = AsyncTeleBot(TELEGRAM_TOKEN)

user_states = {}
user_data = {}

@bot.message_handler(commands=['start'])
async def start(message):
    user_id = message.from_user.id
    logger.info(f"Обработка /start для пользователя {user_id}")
    keyboard = []

    if is_authorized(user_id):
        role = get_user_role(user_id)
        logger.info(f"Роль пользователя {user_id}: {role}")
        if role == "Admin":
            keyboard = [
                [types.InlineKeyboardButton("👥 Просмотр заявок на роли", callback_data="requests")],
                [types.InlineKeyboardButton("✂️ Создать заявку на раскрой", callback_data="new_cutting_request")],
                [types.InlineKeyboardButton("📋 Просмотреть заявки на раскрой", callback_data="view_requests")]
            ]
        elif role == "Cutter":
            keyboard = [
                [types.InlineKeyboardButton("📋 Просмотреть заявки", callback_data="view_requests")]
            ]
        elif role == "Seamstress":
            keyboard = [
                [types.InlineKeyboardButton("📋 Просмотреть заявки", callback_data="view_requests")]
            ]
    else:
        keyboard = [
            [types.InlineKeyboardButton("Подать заявку", callback_data="submit_request")]
        ]

    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.send_message(message.chat.id, "Добро пожаловать! Выберите действие:", reply_markup=reply_markup)

@bot.callback_query_handler(func=lambda call: True)
async def button_handler(call):
    await bot.answer_callback_query(call.id)
    callback_data = call.data
    user_id = call.from_user.id
    logger.info(f"Обработка callback для пользователя {user_id}, данные: {callback_data}")

    state = user_states.get(user_id, None)
    if state in [SIZES_TYPE, SELECT_SIZES, CONFIRM_SIZES] and callback_data in ["sizes_adult", "sizes_child", "sizes_done"] or callback_data.startswith("size_") or callback_data in ["confirm_sizes", "cancel_request"]:
        if callback_data in ["sizes_adult", "sizes_child"]:
            await process_sizes_type(call)
        elif callback_data.startswith("size_") or callback_data == "sizes_done":
            await select_sizes(call)
        elif callback_data == "confirm_sizes":
            await confirm_sizes(call)
        elif callback_data == "cancel_request":
            await cancel_request(call)
        return

    if state in [ACTUAL_SIZES_QUANTITY, SIZE_STACKS, FABRIC_USED, PARTICIPANTS, COMMENT, CONFIRM_COMPLETION] and callback_data.startswith("confirmcomplete_") or callback_data.startswith("edit_completion_") or callback_data.startswith("cancel_completion_"):
        if callback_data.startswith("confirmcomplete_"):
            await confirmcompletion(call)
        elif callback_data.startswith("edit_completion_"):
            await edit_completion(call)
        elif callback_data.startswith("cancel_completion_"):
            await cancel_completion(call)
        return

    # Новое: обработка выбора цвета
    if state == COLOR_SELECTION and callback_data.startswith("color_"):
        await select_color(call)
        return

    if not is_authorized(user_id):
        if callback_data == "submit_request":
            if has_pending_request(user_id):
                await bot.answer_callback_query(call.id, "У вас уже есть активная заявка! Ожидайте решения администратора.", show_alert=True)
                return

            keyboard = [
                [
                    types.InlineKeyboardButton("Раскройщик", callback_data="request_cutter"),
                    types.InlineKeyboardButton("Швея", callback_data="request_seamstress")
                ],
                [types.InlineKeyboardButton("Назад", callback_data="start_callback")]
            ]
            reply_markup = types.InlineKeyboardMarkup(keyboard)
            await bot.edit_message_text("Выберите роль:", call.message.chat.id, call.message.message_id, reply_markup=reply_markup)

        elif callback_data in ["request_cutter", "request_seamstress"]:
            role = "Раскройщик" if callback_data == "request_cutter" else "Швея"
            name = call.from_user.first_name or "Unknown"
            requests_sheet.append_row([str(user_id), name, role, "Pending"])
            logger.info(f"Заявка от {user_id} ({name}) на роль {role} добавлена")

            keyboard = [[types.InlineKeyboardButton("Подать заявку", callback_data="submit_request")]]
            reply_markup = types.InlineKeyboardMarkup(keyboard)
            await bot.edit_message_text(f"Ваша заявка на роль {role} отправлена на рассмотрение!",
                                          call.message.chat.id, call.message.message_id, reply_markup=reply_markup)

        elif callback_data == "start_callback":
            await start_callback(call)

        return

    if callback_data == "view_requests":
        await view_requests(call)
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
            [types.InlineKeyboardButton("✂️ Создать заявку на раскрой", callback_data="new_cutting_request")]
        ]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.edit_message_text("Главное меню администратора:", call.message.chat.id, call.message.message_id, reply_markup=reply_markup)

    elif callback_data == "new_cutting_request":
        await start_cutting_request(call)

    elif callback_data.startswith("accept_"):
        request_id = callback_data.replace("accept_", "")
        await accept_request(call, request_id)

    elif callback_data == "back_to_cutter":
        await back_to_cutter(call)

    elif callback_data.startswith("complete_"):
        await complete_request(call)

@bot.message_handler(func=lambda message: True)
async def text_handler(message):
    user_id = message.from_user.id
    state = user_states.get(user_id, None)

    if state == PRODUCT_NAME:
        await process_product_name(message)
    elif state == COLOR:
        await process_color(message)
    elif state == SIZES_QUANTITY:
        await process_sizes_quantity(message)
    elif state == ACTUAL_SIZES_QUANTITY:
        await process_actual_sizes_quantity(message)
    elif state == SIZE_STACKS:
        await process_size_stacks(message)
    elif state == FABRIC_USED:
        await process_fabric_used(message)
    elif state == PARTICIPANTS:
        await process_participants(message)
    elif state == COMMENT:
        await process_comment(message)

async def back_to_cutter(call):
    role = get_user_role(call.from_user.id)
    keyboard = [
        [types.InlineKeyboardButton("📋 Просмотреть заявки", callback_data="view_requests")]
    ]
    reply_markup = types.InlineKeyboardMarkup(keyboard)

    await bot.edit_message_text(
        f"Главное меню {'раскройщика' if role == 'Cutter' else 'швеи'}:",
        call.message.chat.id, call.message.message_id, reply_markup=reply_markup
    )

async def view_requests(call):
    user_id = call.from_user.id
    role = get_user_role(user_id)
    if role not in ["Cutter", "Seamstress"]:
        await bot.answer_callback_query(call.id, "❌ Только раскройщики и швеи могут просматривать заявки.", show_alert=True)
        return

    try:
        expected_headers = [
            "ID заявки", "Дата создания", "Название изделия", "Цвет ткани",
            "Количество", "Статус", "ID администратора", "Имя администратора",
            "ID раскройщика", "Имя раскройщика", "Фактическое количество",
            "Количество стопок", "Расход ткани", "Участники раскроя", "Номер маршрутного листа", "Расход на единицу",
            "Тип размеров", "Детали размеров", "Детали размеров (фактические)"
        ]
        current_headers = cutting_requests_sheet.row_values(1)
        logger.info(f"Текущие заголовки в CuttingRequests: {current_headers}")
        requests = cutting_requests_sheet.get_all_records()
        new_requests = [r for r in requests if r.get("Статус") == "Новая"]

        if not new_requests:
            await bot.answer_callback_query(call.id, "Нет новых заявок на раскрой.", show_alert=True)
            await bot.edit_message_text("Нет новых заявок на раскрой.", call.message.chat.id, call.message.message_id)
            return

        keyboard = []
        for req in new_requests:
            req_id = req.get("ID заявки", "Unknown")
            product_name = req.get("Название изделия", "Unknown")
            quantity = req.get("Количество", "Unknown")
            color = req.get("Цвет ткани", "Unknown")
            keyboard.append([
                types.InlineKeyboardButton(
                    text=f"{product_name} (Цвет: {color}, Кол-во: {quantity})",
                    callback_data=f"accept_{req_id}"
                )
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

async def accept_request(call, request_id: str):
    user_id = call.from_user.id

    try:
        expected_headers = [
            "ID заявки", "Дата создания", "Название изделия", "Цвет ткани",
            "Количество", "Статус", "ID администратора", "Имя администратора",
            "ID раскройщика", "Имя раскройщика", "Фактическое количество",
            "Количество стопок", "Расход ткани", "Участники раскроя", "Номер маршрутного листа", "Расход на единицу",
            "Тип размеров", "Детали размеров", "Детали размеров (фактические)"
        ]
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

        # Извлекаем данные о размерах
        sizes_json = cutting_requests_sheet.cell(row_idx, 18).value
        sizes_dict = json.loads(sizes_json) if sizes_json else {}
        sizes_text = "\nРазмеры и количества:\n"
        for size, qty in sorted(sizes_dict.items()):
            sizes_text += f"  {size}: {qty}\n"

        # Инициализируем данные заявки в user_data
        if user_id not in user_data:
            user_data[user_id] = {}
        if 'requests' not in user_data[user_id]:
            user_data[user_id]['requests'] = {}
        user_data[user_id]['requests'][request_id] = {
            'row_idx': row_idx,
            'ordered_sizes_dict': sizes_dict,
            'product_name': cutting_requests_sheet.cell(row_idx, 3).value,
            'color': cutting_requests_sheet.cell(row_idx, 4).value,
            'total_quantity': cutting_requests_sheet.cell(row_idx, 5).value
        }

        keyboard = [
            [types.InlineKeyboardButton("✅ Завершить заявку", callback_data=f"complete_{request_id}")]
        ]
        reply_markup = types.InlineKeyboardMarkup(keyboard)

        await bot.edit_message_text(
            text=f"✅ Вы приняли заявку:\n\n"
                 f"ID: {request_id}\n"
                 f"Изделие: {cutting_requests_sheet.cell(row_idx, 3).value}\n"
                 f"Цвет: {cutting_requests_sheet.cell(row_idx, 4).value}\n"
                 f"Количество: {cutting_requests_sheet.cell(row_idx, 5).value}\n"
                 f"{sizes_text}\n"
                 "После выполнения нажмите кнопку ниже:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=reply_markup
        )

        admin_id = cutting_requests_sheet.cell(row_idx, 7).value
        try:
            await bot.send_message(
                admin_id,
                f"✅ {cutter_name} принял заявку {request_id}"
            )
        except Exception as e:
            logger.error(f"Ошибка при уведомлении администратора: {e}")

    except Exception as e:
        logger.error(f"Ошибка при принятии заявки: {e}")
        await bot.answer_callback_query(call.id, "Произошла ошибка.", show_alert=True)

async def complete_request(call):
    request_id = call.data.replace("complete_", "")
    user_id = call.from_user.id

    try:
        # Проверяем, есть ли данные заявки в user_data
        if user_id not in user_data or 'requests' not in user_data[user_id] or request_id not in user_data[user_id]['requests']:
            await bot.send_message(call.message.chat.id, "❌ Данные заявки не найдены. Попробуйте принять заявку заново.")
            return

        request_data = user_data[user_id]['requests'][request_id]
        row_idx = request_data['row_idx']

        current_status = cutting_requests_sheet.cell(row_idx, 6).value
        if current_status == "Выполнена":
            await bot.edit_message_text("❌ Эта заявка уже выполнена.", call.message.chat.id, call.message.message_id)
            return

        cutter_id = cutting_requests_sheet.cell(row_idx, 9).value
        if str(cutter_id) != str(user_id):
            await bot.edit_message_text("❌ Вы не можете завершить эту заявку.", call.message.chat.id, call.message.message_id)
            return

        # Инициализируем данные для завершения заявки
        if 'current_request_id' not in user_data[user_id]:
            user_data[user_id]['current_request_id'] = request_id
        user_data[user_id]['requests'][request_id]['actual_sizes_dict'] = {}
        user_data[user_id]['requests'][request_id]['stacks_dict'] = {}
        user_data[user_id]['requests'][request_id]['actual_selected_sizes'] = sorted(request_data['ordered_sizes_dict'].keys())
        user_data[user_id]['requests'][request_id]['actual_current_index'] = 0

        if not user_data[user_id]['requests'][request_id]['actual_selected_sizes']:
            await bot.send_message(call.message.chat.id, "❌ В заявке нет указанных размеров. Свяжитесь с администратором.")
            return

        first_size = user_data[user_id]['requests'][request_id]['actual_selected_sizes'][0]
        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(
            call.message.chat.id,
            f"Заполните фактические данные по заявке {request_id}:\n\nВведите фактическое количество для размера {first_size}:",
            reply_markup=reply_markup
        )
        user_states[user_id] = ACTUAL_SIZES_QUANTITY

    except Exception as e:
        logger.error(f"Ошибка при проверке заявки {request_id}: {e}")
        await bot.edit_message_text("❌ Произошла ошибка.", call.message.chat.id, call.message.message_id)

async def process_actual_sizes_quantity(message):
    user_id = message.from_user.id
    request_id = user_data[user_id].get('current_request_id')
    if not request_id or 'requests' not in user_data[user_id] or request_id not in user_data[user_id]['requests']:
        await bot.send_message(message.chat.id, "❌ Ошибка: данные заявки не найдены.")
        return

    try:
        quantity = int(message.text.strip())
        if quantity < 0:
            await bot.send_message(message.chat.id, "❌ Количество не может быть отрицательным. Попробуйте снова:")
            return
    except ValueError:
        await bot.send_message(message.chat.id, "❌ Пожалуйста, введите число. Попробуйте снова:")
        return

    current_index = user_data[user_id]['requests'][request_id]['actual_current_index']
    selected_sizes = user_data[user_id]['requests'][request_id]['actual_selected_sizes']
    user_data[user_id]['requests'][request_id]['actual_sizes_dict'][selected_sizes[current_index]] = quantity

    keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.send_message(
        message.chat.id,
        f"Введите количество стопок для размера {selected_sizes[current_index]}:",
        reply_markup=reply_markup
    )
    user_states[user_id] = SIZE_STACKS

async def process_size_stacks(message):
    user_id = message.from_user.id
    request_id = user_data[user_id].get('current_request_id')
    if not request_id or 'requests' not in user_data[user_id] or request_id not in user_data[user_id]['requests']:
        await bot.send_message(message.chat.id, "❌ Ошибка: данные заявки не найдены.")
        return

    try:
        stacks = int(message.text.strip())
        if stacks < 0:
            await bot.send_message(message.chat.id, "❌ Количество стопок не может быть отрицательным. Попробуйте снова:")
            return
    except ValueError:
        await bot.send_message(message.chat.id, "❌ Пожалуйста, введите число. Попробуйте снова:")
        return

    current_index = user_data[user_id]['requests'][request_id]['actual_current_index']
    selected_sizes = user_data[user_id]['requests'][request_id]['actual_selected_sizes']
    user_data[user_id]['requests'][request_id]['stacks_dict'][selected_sizes[current_index]] = stacks

    current_index += 1
    user_data[user_id]['requests'][request_id]['actual_current_index'] = current_index

    if current_index < len(selected_sizes):
        next_size = selected_sizes[current_index]
        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(
            message.chat.id,
            f"Введите фактическое количество для размера {next_size}:",
            reply_markup=reply_markup
        )
        user_states[user_id] = ACTUAL_SIZES_QUANTITY
    else:
        total_quantity = sum(user_data[user_id]['requests'][request_id]['actual_sizes_dict'].values())
        if total_quantity == 0:
            await bot.send_message(message.chat.id, "❌ Фактическое количество не может быть нулевым. Начните заново:")
            user_states[user_id] = ACTUAL_SIZES_QUANTITY
            return

        user_data[user_id]['requests'][request_id]['actual_quantity'] = total_quantity

        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(message.chat.id, "Введите расход ткани (в метрах):", reply_markup=reply_markup)
        user_states[user_id] = FABRIC_USED

async def process_fabric_used(message):
    user_id = message.from_user.id
    request_id = user_data[user_id].get('current_request_id')
    if not request_id or 'requests' not in user_data[user_id] or request_id not in user_data[user_id]['requests']:
        await bot.send_message(message.chat.id, "❌ Ошибка: данные заявки не найдены.")
        return

    try:
        fabric_used = float(message.text)
        if fabric_used <= 0:
            await bot.send_message(message.chat.id, "❌ Расход должен быть положительным числом. Попробуйте снова:")
            return
    except ValueError:
        await bot.send_message(message.chat.id, "❌ Пожалуйста, введите число. Попробуйте снова:")
        return

    user_data[user_id]['requests'][request_id]['fabric_used'] = fabric_used

    keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.send_message(message.chat.id, "Введите участников раскроя (через запятую):", reply_markup=reply_markup)
    user_states[user_id] = PARTICIPANTS

async def process_participants(message):
    user_id = message.from_user.id
    request_id = user_data[user_id].get('current_request_id')
    if not request_id or 'requests' not in user_data[user_id] or request_id not in user_data[user_id]['requests']:
        await bot.send_message(message.chat.id, "❌ Ошибка: данные заявки не найдены.")
        return

    participants = message.text.strip()
    if not participants:
        await bot.send_message(message.chat.id, "❌ Пожалуйста, введите хотя бы одного участника.")
        return

    user_data[user_id]['requests'][request_id]['participants'] = participants

    keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.send_message(message.chat.id, "Введите номер маршрутного листа:", reply_markup=reply_markup)
    user_states[user_id] = COMMENT

async def process_comment(message):
    user_id = message.from_user.id
    request_id = user_data[user_id].get('current_request_id')
    if not request_id or 'requests' not in user_data[user_id] or request_id not in user_data[user_id]['requests']:
        await bot.send_message(message.chat.id, "❌ Ошибка: данные заявки не найдены.")
        return

    route_list_number = message.text.strip()
    if not route_list_number:
        await bot.send_message(message.chat.id, "❌ Номер маршрутного листа не может быть пустым. Попробуйте снова:")
        return

    user_data[user_id]['requests'][request_id]['route_list_number'] = route_list_number
    await show_confirmation(message)

async def show_confirmation(message_or_call):
    if hasattr(message_or_call, 'text'):
        message = message_or_call
        user_id = message.from_user.id
        chat_id = message.chat.id
    else:
        call = message_or_call
        user_id = call.from_user.id
        chat_id = call.message.chat.id

    request_id = user_data[user_id].get('current_request_id')
    if not request_id or 'requests' not in user_data[user_id] or request_id not in user_data[user_id]['requests']:
        await bot.send_message(chat_id, "❌ Ошибка: данные заявки не найдены.")
        return

    data = user_data[user_id]['requests'][request_id]
    confirmation_text = (
        "✅ Подтвердите завершение заявки:\n\n"
        f"ID заявки: {request_id}\n"
        f"Фактическое количество: {data['actual_quantity']}\n"
        f"Фактические размеры и стопки:\n"
    )
    for size, qty in sorted(data['actual_sizes_dict'].items()):
        stacks = data['stacks_dict'].get(size, 0)
        confirmation_text += f"  {size}: {qty} (стопок: {stacks})\n"
    confirmation_text += (
        f"Расход ткани: {data['fabric_used']} м\n"
        f"Участники: {data['participants']}\n"
        f"Номер маршрутного листа: {data.get('route_list_number', 'нет')}"
    )

    keyboard = [
        [types.InlineKeyboardButton("✔ Подтвердить", callback_data=f"confirmcomplete_{request_id}")],
        [types.InlineKeyboardButton("✏ Исправить", callback_data=f"edit_completion_{request_id}")]
    ]
    reply_markup = types.InlineKeyboardMarkup(keyboard)

    await bot.send_message(chat_id, confirmation_text, reply_markup=reply_markup)
    user_states[user_id] = CONFIRM_COMPLETION

async def confirmcompletion(call):
    request_id = call.data.replace("confirmcomplete_", "")
    user_id = call.from_user.id

    if user_id not in user_data or 'requests' not in user_data[user_id] or request_id not in user_data[user_id]['requests']:
        await bot.edit_message_text("❌ Ошибка: данные заявки не найдены.", call.message.chat.id, call.message.message_id)
        return

    data = user_data[user_id]['requests'][request_id]

    try:
        expected_headers = [
            "ID заявки", "Дата создания", "Название изделия", "Цвет ткани",
            "Количество", "Статус", "ID администратора", "Имя администратора",
            "ID раскройщика", "Имя раскройщика", "Фактическое количество",
            "Количество стопок", "Расход ткани", "Участники раскроя", "Номер маршрутного листа", "Расход на единицу",
            "Тип размеров", "Детали размеров", "Детали размеров (фактические)"
        ]
        requests = cutting_requests_sheet.get_all_records()
        row_idx = None
        for idx, req in enumerate(requests, 2):
            if req.get("ID заявки") == request_id:
                row_idx = idx
                break

        if not row_idx:
            await bot.edit_message_text("❌ Заявка не найдена", call.message.chat.id, call.message.message_id)
            return

        current_status = cutting_requests_sheet.cell(row_idx, 6).value
        if current_status == "Выполнена":
            await bot.edit_message_text("❌ Эта заявка уже выполнена.", call.message.chat.id, call.message.message_id)
            return

        cutter_id = cutting_requests_sheet.cell(row_idx, 9).value
        if str(cutter_id) != str(user_id):
            await bot.edit_message_text("❌ Вы не можете завершить эту заявку.", call.message.chat.id, call.message.message_id)
            return

        product_name = cutting_requests_sheet.cell(row_idx, 3).value
        color = cutting_requests_sheet.cell(row_idx, 4).value
        actual_sizes_json = json.dumps(data['actual_sizes_dict'])
        total_stacks = sum(data['stacks_dict'].values())
        updates = [
            (row_idx, 6, "Выполнена"),
            (row_idx, 11, data['actual_quantity']),
            (row_idx, 12, total_stacks),
            (row_idx, 13, data['fabric_used']),
            (row_idx, 14, data['participants']),
            (row_idx, 15, data['route_list_number']),
            (row_idx, 16, f'=M{row_idx}/K{row_idx}'),
            (row_idx, 19, actual_sizes_json)
        ]

        for row, col, value in updates:
            cutting_requests_sheet.update_cell(row, col, value)

        fabric_per_unit = data['fabric_used'] / data['actual_quantity'] if data['actual_quantity'] > 0 else 0

        spreadsheet = sheets_data["spreadsheet"]
        try:
            route_list_number = data['route_list_number']
            new_sheet = spreadsheet.add_worksheet(title=route_list_number+color, rows=50, cols=9)
            new_sheet.append_row([
                "Наименование изделия", "Размер", "Количество (заказано)", "Фактическое количество",
                "Количество стопок", "Цвет ткани", "Расход ткани (м)", "Расход на единицу (м)", "Участники"
            ])
            new_sheet.format("A1:I1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
            })
            new_sheet.format("A2:I100", {
                "backgroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                "textFormat": {"foregroundColor": {"red": 0.0, "green": 0.0, "blue": 0.0}}
            })
            new_sheet.format("D2:D100", {
                "backgroundColor": {"red": 0.8, "green": 1.0, "blue": 0.8}
            })
            row = 2
            for size in sorted(data['ordered_sizes_dict'].keys()):
                ordered_qty = data['ordered_sizes_dict'].get(size, 0)
                actual_qty = data['actual_sizes_dict'].get(size, 0)
                stacks = data['stacks_dict'].get(size, 0)
                new_sheet.append_row([
                    product_name, size, ordered_qty, actual_qty, stacks,
                    color, data['fabric_used'], round(fabric_per_unit, 2), data['participants']
                ])
                row += 1
            new_sheet.append_row(["Номер маршрутного листа", route_list_number, "", "", "", "", "", "", ""])
            logger.info(f"Создан лист {route_list_number}")
        except Exception as e:
            route_list_number = data['route_list_number']
            logger.error(f"Ошибка создания листа {route_list_number}: {e}")

        admin_id = cutting_requests_sheet.cell(row_idx, 7).value
        admin_message = (
            f"✅ Заявка {request_id} выполнена!\n"
            f"Раскройщик: {call.from_user.full_name}\n"
            f"Изделие: {product_name}\n"
            f"Цвет ткани: {color}\n"
            f"Номер маршрутного листа: {data['route_list_number']}\n"
            f"Фактическое количество: {data['actual_quantity']}\n"
            f"Расход ткани: {data['fabric_used']} м\n"
            f"Расход на единицу: {round(fabric_per_unit, 2)} м\n"
            f"Участники: {data['participants']}\n"
            f"Сводка размеров:\n"
            f"Заказано:\n"
        )
        for size, qty in sorted(data['ordered_sizes_dict'].items()):
            admin_message += f"  {size}: {qty}\n"
        admin_message += f"Фактически (с количеством стопок):\n"
        for size, qty in sorted(data['actual_sizes_dict'].items()):
            stacks = data['stacks_dict'].get(size, 0)
            admin_message += f"  {size}: {qty} (стопок: {stacks})\n"

        try:
            await bot.send_message(admin_id, admin_message)
        except Exception as e:
            logger.error(f"Ошибка уведомления администратора: {e}")

        keyboard = [
            [types.InlineKeyboardButton("📋 Посмотреть другие заявки", callback_data="view_requests")]
        ]
        reply_markup = types.InlineKeyboardMarkup(keyboard)

        await bot.edit_message_text(
            "✅ Заявка успешно завершена и сохранена!",
            call.message.chat.id, call.message.message_id,
            reply_markup=reply_markup
        )

        # Очищаем данные только для текущей заявки
        if 'requests' in user_data[user_id] and request_id in user_data[user_id]['requests']:
            del user_data[user_id]['requests'][request_id]
        if user_data[user_id].get('current_request_id') == request_id:
            user_data[user_id].pop('current_request_id', None)
        user_states.pop(user_id, None)

    except Exception as e:
        logger.error(f"Ошибка завершения заявки {request_id}: {e}")
        await bot.edit_message_text("❌ Произошла ошибка при сохранении данных", call.message.chat.id, call.message.message_id)

async def edit_completion(call):
    request_id = call.data.replace("edit_completion_", "")
    user_id = call.from_user.id

    if user_id not in user_data or 'requests' not in user_data[user_id] or request_id not in user_data[user_id]['requests']:
        await bot.edit_message_text("❌ Ошибка: данные заявки не найдены.", call.message.chat.id, call.message.message_id)
        return

    try:
        row_idx = user_data[user_id]['requests'][request_id]['row_idx']
        current_status = cutting_requests_sheet.cell(row_idx, 6).value
        if current_status == "Выполнена":
            await bot.edit_message_text("❌ Эта заявка уже выполнена.", call.message.chat.id, call.message.message_id)
            return

        cutter_id = cutting_requests_sheet.cell(row_idx, 9).value
        if str(cutter_id) != str(user_id):
            await bot.edit_message_text("❌ Вы не можете редактировать эту заявку.", call.message.chat.id, call.message.message_id)
            return

        user_data[user_id]['current_request_id'] = request_id
        user_data[user_id]['requests'][request_id]['actual_sizes_dict'] = {}
        user_data[user_id]['requests'][request_id]['stacks_dict'] = {}
        user_data[user_id]['requests'][request_id]['actual_selected_sizes'] = sorted(user_data[user_id]['requests'][request_id]['ordered_sizes_dict'].keys())
        user_data[user_id]['requests'][request_id]['actual_current_index'] = 0

        if not user_data[user_id]['requests'][request_id]['actual_selected_sizes']:
            await bot.send_message(call.message.chat.id, "❌ В заявке нет указанных размеров. Свяжитесь с администратором.")
            return

        first_size = user_data[user_id]['requests'][request_id]['actual_selected_sizes'][0]
        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_completion_{request_id}")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.edit_message_text(
            f"Редактирование заявки {request_id}:\n\nВведите фактическое количество для размера {first_size}:",
            call.message.chat.id, call.message.message_id,
            reply_markup=reply_markup
        )
        user_states[user_id] = ACTUAL_SIZES_QUANTITY

    except Exception as e:
        logger.error(f"Ошибка при проверке заявки {request_id}: {e}")
        await bot.edit_message_text("❌ Произошла ошибка.", call.message.chat.id, call.message.message_id)

async def cancel_completion(call):
    request_id = call.data.replace("cancel_completion_", "")
    user_id = call.from_user.id

    if user_id not in user_data or 'requests' not in user_data[user_id] or request_id not in user_data[user_id]['requests']:
        await bot.edit_message_text("❌ Ошибка: данные заявки не найдены.", call.message.chat.id, call.message.message_id)
        return

    # Очищаем данные только для текущей заявки
    if 'requests' in user_data[user_id] and request_id in user_data[user_id]['requests']:
        del user_data[user_id]['requests'][request_id]
    if user_data[user_id].get('current_request_id') == request_id:
        user_data[user_id].pop('current_request_id', None)
    user_states.pop(user_id, None)

    role = get_user_role(user_id)
    keyboard = [
        [types.InlineKeyboardButton("📋 Просмотреть заявки", callback_data="view_requests")]
    ]
    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.edit_message_text(
        f"❌ Завершение заявки {request_id} отменено.",
        call.message.chat.id, call.message.message_id,
        reply_markup=reply_markup
    )

async def start_cutting_request(call):
    user_id = call.from_user.id
    logger.info(f"Попытка создания новой заявки на раскрой пользователем {user_id} в {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    if not is_authorized(user_id):
        logger.warning(f"Пользователь {user_id} не авторизован")
        await bot.answer_callback_query(call.id, "❌ Вы не авторизованы для создания заявок.", show_alert=True)
        return

    keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")]]
    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.send_message(call.message.chat.id, "Введите название изделия:", reply_markup=reply_markup)
    if user_id not in user_data:
        user_data[user_id] = {}
    user_states[user_id] = PRODUCT_NAME

async def process_product_name(message):
    user_id = message.from_user.id
    product_name = message.text.strip()

    if not product_name:
        await bot.send_message(message.chat.id, "❌ Название изделия не может быть пустым. Попробуйте снова:")
        return

    user_data[user_id]['product_name'] = product_name

    # Получаем цвета из листа Products
    try:
        products = products_sheet.get_all_records()
        colors_list = []
        for prod in products:
            if prod.get("ProductName", "").strip().lower() == product_name.lower():
                colors_str = prod.get("Colors", "")
                if colors_str:
                    colors_list = [c.strip() for c in colors_str.split(",")]
                break

        if colors_list:
            # Показываем кнопки для выбора цвета
            keyboard = []
            row = []
            for color in colors_list:
                row.append(types.InlineKeyboardButton(color, callback_data=f"color_{color}"))
                if len(row) == 3:  # По 3 в ряд для удобства
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            keyboard.append([types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")])
            reply_markup = types.InlineKeyboardMarkup(keyboard)
            await bot.send_message(message.chat.id, f"Выберите цвет для изделия '{product_name}':", reply_markup=reply_markup)
            user_states[user_id] = COLOR_SELECTION
        else:
            # Если нет цветов, ввод вручную (как раньше)
            keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")]]
            reply_markup = types.InlineKeyboardMarkup(keyboard)
            await bot.send_message(message.chat.id, "Цвета не найдены для этого изделия. Введите цвет ткани вручную:", reply_markup=reply_markup)
            user_states[user_id] = COLOR
    except Exception as e:
        logger.error(f"Ошибка при получении цветов для продукта {product_name}: {e}")
        await bot.send_message(message.chat.id, "❌ Ошибка при загрузке цветов. Введите цвет вручную:")
        user_states[user_id] = COLOR

async def process_color(message):
    user_id = message.from_user.id
    color = message.text.strip()

    if not color:
        await bot.send_message(message.chat.id, "❌ Цвет ткани не может быть пустым. Попробуйте снова:")
        return

    user_data[user_id]['color'] = color

    keyboard = [
        [types.InlineKeyboardButton("Взрослые (34-64)", callback_data="sizes_adult")],
        [types.InlineKeyboardButton("Детские (122-158)", callback_data="sizes_child")],
        [types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")]
    ]
    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.send_message(message.chat.id, "Выберите тип размеров:", reply_markup=reply_markup)
    user_states[user_id] = SIZES_TYPE

async def process_sizes_type(call):
    sizes_type = "adult" if call.data == "sizes_adult" else "child"
    user_id = call.from_user.id
    user_data[user_id]['sizes_type'] = sizes_type
    user_data[user_id]['selected_sizes'] = []
    user_data[user_id]['sizes_dict'] = {}

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
    await bot.send_message(
        call.message.chat.id,
        f"Выберите размеры (нажмите на нужные размеры, затем 'Готово'):",
        reply_markup=reply_markup
    )
    user_states[user_id] = SELECT_SIZES

async def select_sizes(call):
    user_id = call.from_user.id
    callback_data = call.data

    if callback_data == "sizes_done":
        if not user_data[user_id].get('selected_sizes'):
            await bot.send_message(call.message.chat.id, "❌ Выберите хотя бы один размер!")
            return

        user_data[user_id]['current_size_index'] = 0
        size = user_data[user_id]['selected_sizes'][0]
        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(call.message.chat.id, f"Введите количество для размера {size}:", reply_markup=reply_markup)
        user_states[user_id] = SIZES_QUANTITY
        return

    elif callback_data.startswith("size_"):
        size = int(callback_data.replace("size_", ""))
        selected_sizes = user_data[user_id]['selected_sizes']
        if size in selected_sizes:
            selected_sizes.remove(size)
            await bot.answer_callback_query(call.id, f"Размер {size} убран из выбора")
        else:
            selected_sizes.append(size)
            await bot.answer_callback_query(call.id, f"Размер {size} добавлен")

        sizes_type = user_data[user_id]['sizes_type']
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

async def process_sizes_quantity(message):
    user_id = message.from_user.id
    try:
        quantity = int(message.text.strip())
        if quantity < 0:
            await bot.send_message(message.chat.id, "❌ Количество не может быть отрицательным. Попробуйте снова:")
            return
    except ValueError:
        await bot.send_message(message.chat.id, "❌ Пожалуйста, введите число. Попробуйте снова:")
        return

    current_index = user_data[user_id]['current_size_index']
    selected_sizes = user_data[user_id]['selected_sizes']
    user_data[user_id]['sizes_dict'][selected_sizes[current_index]] = quantity

    current_index += 1
    user_data[user_id]['current_size_index'] = current_index

    if current_index < len(selected_sizes):
        next_size = selected_sizes[current_index]
        keyboard = [[types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(message.chat.id, f"Введите количество для размера {next_size}:", reply_markup=reply_markup)
        return
    else:
        total_quantity = sum(user_data[user_id]['sizes_dict'].values())
        if total_quantity == 0:
            await bot.send_message(message.chat.id, "❌ Общее количество не может быть нулевым. Начните заново:")
            await process_sizes_type(message)  # Note: message instead of call, may need adjustment
            return

        user_data[user_id]['quantity'] = total_quantity

        confirmation_text = "✅ Подтвердите данные:\n\n"
        confirmation_text += f"Изделие: {user_data[user_id]['product_name']}\n"
        confirmation_text += f"Цвет: {user_data[user_id]['color']}\n"
        confirmation_text += f"Тип размеров: {'Взрослые' if user_data[user_id]['sizes_type'] == 'adult' else 'Детские'}\n"
        confirmation_text += "Размеры и количества:\n"
        for size, qty in sorted(user_data[user_id]['sizes_dict'].items()):
            confirmation_text += f"  {size}: {qty}\n"
        confirmation_text += f"Общее количество: {total_quantity}"

        keyboard = [
            [types.InlineKeyboardButton("✔ Подтвердить", callback_data="confirm_sizes")],
            [types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")]
        ]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(message.chat.id, confirmation_text, reply_markup=reply_markup)
        user_states[user_id] = CONFIRM_SIZES

async def confirm_sizes(call):
    user_id = call.from_user.id

    try:
        data = user_data[user_id]
        product_name = data.get('product_name', 'Не указано')
        color = data.get('color', 'Не указан')
        sizes_type = data.get('sizes_type')
        sizes_dict = data.get('sizes_dict')
        total_quantity = data.get('quantity')
        sizes_type_ru = "Взрослые" if sizes_type == "adult" else "Детские"
        sizes_json = json.dumps(sizes_dict)

        request_id = f"CR-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        admin_id = user_id
        admin_name = call.from_user.full_name

        cutting_requests_sheet.append_row([
            request_id, created_at, product_name, color, total_quantity, "Новая",
            admin_id, admin_name, "", "", "", "", "", "", "", "", sizes_type_ru, sizes_json, ""
        ])

        await notify_cutters(bot, request_id, created_at, product_name, sizes_dict)

        keyboard = [[types.InlineKeyboardButton("➕ Создать новую заявку", callback_data="new_cutting_request")]]
        reply_markup = types.InlineKeyboardMarkup(keyboard)
        await bot.send_message(
            call.message.chat.id,
            f"✅ Заявка на раскрой создана!\n"
            f"ID: {request_id}\n"
            f"Изделие: {product_name}\n"
            f"Цвет: {color}\n"
            f"Тип размеров: {sizes_type_ru}\n"
            f"Общее количество: {total_quantity}\n"
            f"Дата: {created_at}",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Ошибка при создании заявки: {e}")
        await bot.send_message(call.message.chat.id, f"❌ Произошла ошибка: {str(e)}. Попробуйте снова.")
    finally:
        user_data.pop(user_id, None)
        user_states.pop(user_id, None)

async def notify_cutters(bot, request_id: str, created_at: str, product_name: str, sizes_dict: dict):
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
                    logger.info(f"Уведомление отправлено пользователю {user['ID']}")
                except Exception as e:
                    logger.error(f"Ошибка при уведомлении пользователя {user['ID']}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}")

async def cancel_request(call):
    user_id = call.from_user.id
    user_data.pop(user_id, None)
    user_states.pop(user_id, None)

    if not is_authorized(user_id):
        await bot.edit_message_text("❌ Доступ запрещен.", call.message.chat.id, call.message.message_id)
        return

    role = get_user_role(user_id)
    keyboard = []

    if role == "Admin":
        keyboard = [
            [types.InlineKeyboardButton("👥 Просмотр заявок на роли", callback_data="requests")],
            [types.InlineKeyboardButton("✂️ Создать заявку на раскрой", callback_data="new_cutting_request")]
        ]
    elif role in ["Cutter", "Seamstress"]:
        keyboard = [
            [types.InlineKeyboardButton("📋 Просмотреть заявки", callback_data="view_requests")]
        ]

    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.edit_message_text("❌ Создание заявки отменено.", call.message.chat.id, call.message.message_id, reply_markup=reply_markup)
async def select_color(call):
    user_id = call.from_user.id
    color = call.data.replace("color_", "")

    user_data[user_id]['color'] = color

    keyboard = [
        [types.InlineKeyboardButton("Взрослые (34-64)", callback_data="sizes_adult")],
        [types.InlineKeyboardButton("Детские (122-158)", callback_data="sizes_child")],
        [types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_request")]
    ]
    reply_markup = types.InlineKeyboardMarkup(keyboard)
    await bot.edit_message_text(f"Цвет '{color}' выбран. Выберите тип размеров:", call.message.chat.id, call.message.message_id, reply_markup=reply_markup)
    user_states[user_id] = SIZES_TYPE
async def start_callback(call):
    user_id = call.from_user.id
    keyboard = []
    if is_authorized(user_id):
        role = get_user_role(user_id)

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
    await bot.edit_message_text("Добро пожаловать! Выберите действие:", call.message.chat.id, call.message.message_id, reply_markup=reply_markup)

if __name__ == "__main__":
    logger.info("Бот запущен")
    asyncio.run(bot.infinity_polling())