import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Константы для состояний разговора
(
    PRODUCT_NAME, COLOR, SIZES_TYPE, SELECT_SIZES, SIZES_QUANTITY, CONFIRM_SIZES,
    ACTUAL_SIZES_QUANTITY, SIZE_STACKS, FABRIC_USED, PARTICIPANTS, COMMENT, CONFIRM_COMPLETION, SELECT_PARTICIPANTS,
    VIEW_REQUESTS, COLOR_SELECTION, SELECT_COLORS, PARTIAL_OR_FULL, AWAITING_ROUTE_LIST
) = range(18)

# Токен бота
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Настройки Google Sheets
GOOGLE_CREDENTIALS = {
    "type": "service_account",
    "project_id": "rishtan-fab",
    "private_key_id": "33319145950bfe7865ad6292cdf21c1732406a4d",
    "private_key": os.getenv("GOOGLE_PRIVATE_KEY", "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCNQue0zauKuXar\nOaPeVFvDFiEKvVHI7z+6IJcLe3XG+l0//VgFfZ+G4FmF7M+5ForEB97h1LLrzH3T\nZIjAWMUOqgc8JLnuja2b1G+WZo5xaIgzqenYuKOpmR2FKAfl/g5rtMhKhgRgGfFF\nhEJ1u30THLlV4mqKT0KqEs7tHIDAKKV6N6imFt7sB8y8/tjSw0uB/SllMNyiX6jM\nhHycpSiqH1nFssdQq2pm8ugTDZKKyH/GXVa1VTsIUvQdOu0Qkt1u/XjpY9kBa1wT\nkhFi4+H3poik83uVwMD/3VJuiws42Gd0uspauZNHVt86g3uh4g/apfQuH5hvDuZd\nijs/1ZuFAgMBAAECggEAAoMdlsgPlGx+8UWZpfMPHLWQid3bDf0/P2Kj/QbJjevW\n67PoNFTLGP11ah3PheWiOyE+s/px4iKlXDSOAAm0G3Inpcira9QmMb7B60VQpDCt\nN2n+qCWEd5gq/7q6BTuS6xRweW7PthvQACH9gpV+gHAC1cWsimAledvSxUG8Am7P\n2aqQ+M9Zj0VndsptAux5VzkXAjqgqYTD/g3MzHgZopNeqpfXWA08rTy4UwvwPTA7\n7/9qiE9pJPKRDtPKKm+hv6R23Y/6VglNmHb20KtOoISujS857P1IQfBuv5iWdEpR\ngVqs3s7aGj7LWPsumVHTviQAN3fFN8zgJvdKkuiSQwKBgQDF06QSUwYPVDM3uNNP\nYgtb/q2LIuXbmfa8z23/5cHq/FWEsKWERBxBp1qHM8yNmUHbaT8tEYvgbpRGu14M\nDgX1ngUDlxfdf615zpd5X0ZOW1Faz5knEOW8ZUq02WGJe8uHBed9fEMoLpPlyqaN\nPOyGjtKsp0N95VRoJaMzQ5BcSwKBgQC2zQiE/9uvRzo6Qj6wkhu1Jy8PMqsDovK/\nqMncwFrRBjIcshk/HnFYv0nXNDM6gn/qRVFxonsrTCmlDxbB/W7iC5HhfgqMsO9+\n0d6/MSpqdwjWAORa12XICsVsQ+2kQAK1O+/qQCg+RGJrJ3t/6TQfUrDTcxgi+pts\nWhH2svxlbwKBgQCXpiENRwXLNHG60n1ySieJExd4JH1uNX2WybB6TWe1OlBYUo3f\ncdLzZVYZdNTm60g36Vtbsiq3Fi2mdzWmKg3ZdpRDZ00NKDYUvRETIr0jjg80fRXb\ng7GJFWEKd+W0XejsjdMiN+LHZ8VKj2nTtZNfpxbK8cHkPavR1qBfyPheNwKBgBbB\n+eCM9e2hYXdlTeavmfF4mlw7A51lSPFhcxgffm7tZYm7BnecM6JH1kqLfiE3o/Mn\nhBcwkkL2rWyWL1AhXA+aPyQii++uC3Lvb9q/pTcx8JCr9cH1dP9tj9yFrG05Ztzn\nRFwWdqwh2VrbxH1NLCcGJWt9tbCNIJJhuEDNUazTAoGAJ9ukDTNok2ycvJNard/I\nRX4T3gGEkFpioaSWkx27uJlyZnlinvUB8wDHeiNvBIfaBYy5Rxv7xKuiJWsEjwzq\nPzxRYicosMatzeYXLmmNAI1dYHY4tye4Oq96QQ/ZwTwKMBaC0VEo3qFYdC2JKm7O\nygbG1PPIsn0HPzrE9xIHrsw=\n-----END PRIVATE KEY-----\n"),
    "client_email": "rihtan-fab@rishtan-fab.iam.gserviceaccount.com",
    "client_id": "106390835829056664101",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/rihtan-fab%40rishtan-fab.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com"
}

SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]