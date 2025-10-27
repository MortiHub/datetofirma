import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import GOOGLE_CREDENTIALS, SCOPES
import logging

logger = logging.getLogger(__name__)

def init_sheets():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, SCOPES)
        client = gspread.authorize(creds)
        spreadsheet = client.open("FabricData")

        # Инициализация листов
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
            "Тип размеров", "Детали размеров", "Детали размеров (фактические)", "Детали стопок"
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

        try:
            products_sheet = spreadsheet.worksheet("Products")
        except gspread.WorksheetNotFound:
            products_sheet = spreadsheet.add_worksheet(title="Products", rows=100, cols=2)
            products_sheet.append_row(["ProductName", "Colors"])
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
            "products_sheet": products_sheet
        }
    except Exception as e:
        logger.error(f"Ошибка при инициализации Google Sheets: {e}")
        raise