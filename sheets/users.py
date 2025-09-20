import logging

logger = logging.getLogger(__name__)

def is_authorized(user_id: int, users_sheet) -> bool:
    try:
        users = users_sheet.get_all_records()
        for user in users:
            if str(user["ID"]).strip() == str(user_id) and user["Role"].strip() in ["Admin", "Cutter", "Seamstress"]:
                return True
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке авторизации: {e}")
        return False

def get_user_role(user_id: int, users_sheet) -> str:
    try:
        users = users_sheet.get_all_records()
        for user in users:
            if str(user["ID"]).strip() == str(user_id):
                return user["Role"].strip()
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении роли для ID {user_id}: {e}")
        return None

def has_pending_request(user_id: int, requests_sheet) -> bool:
    try:
        requests = requests_sheet.get_all_records()
        for req in requests:
            if str(req.get("ID", "")).strip() == str(user_id) and req.get("Status", "").lower() == "pending":
                return True
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке заявок пользователя {user_id}: {e}")
        return False