import os
import requests
from datetime import datetime
from io import BytesIO

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader


# --- Настройки страницы ---
PAGE_W, PAGE_H = A4
LEFT = 40
TOP = PAGE_H - 40
LINE_H = 20

# --- Путь к проекту ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ✅ ПУТЬ К ШРИФТУ (исправлено под Windows/Linux)
FONT_PATH = os.path.abspath(os.path.join(BASE_DIR, "../font/DejaVuSans.ttf"))

# ✅ Убедиться, что шрифт существует
if not os.path.exists(FONT_PATH):
    raise FileNotFoundError(
        f"Файл шрифта DejaVuSans.ttf не найден по пути: {FONT_PATH}\n"
        "Положите файл вручную в папку /font/"
    )

# ✅ Регистрируем шрифт (русские символы работают)
pdfmetrics.registerFont(TTFont("DejaVu", FONT_PATH))


async def generate_defects_report(bot, call, spreadsheet):
    """
    Генерация красивого PDF отчёта по браку (вариант B)
    """

    # --- Чтение листа Defects ---
    try:
        sheet = spreadsheet.worksheet("Defects")
    except Exception:
        await bot.send_message(call.message.chat.id, "❌ Лист 'Defects' отсутствует.")
        return

    records = sheet.get_all_records()
    if not records:
        await bot.send_message(call.message.chat.id, "✅ Нет записей по браку.")
        return

    # --- Папка для PDF ---
    REPORTS_DIR = os.path.abspath(os.path.join(BASE_DIR, "../reports"))
    os.makedirs(REPORTS_DIR, exist_ok=True)

    filename = os.path.join(
        REPORTS_DIR,
        f"defects_report_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.pdf"
    )

    # --- Создание PDF ---
    pdf = canvas.Canvas(filename, pagesize=A4)
    pdf.setTitle("Отчёт по браку")

    # Заголовок
    pdf.setFont("DejaVu", 18)
    pdf.drawString(LEFT, TOP, f"Отчёт по браку — {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    pdf.setFont("DejaVu", 12)
    pdf.drawString(LEFT, TOP - 25, f"Всего записей: {len(records)}")

    y = TOP - 60

    # --- Перебор записей ---
    for idx, row in enumerate(records, start=1):

        # --- Новая страница при необходимости ---
        if y < 180:
            pdf.showPage()
            pdf.setFont("DejaVu", 12)
            y = TOP - 20

        # Заголовок блока
        pdf.setFont("DejaVu", 16)
        pdf.drawString(LEFT, y, f"Брак №{idx}")
        y -= 28
        pdf.setFont("DejaVu", 12)

        # Поля
        fields = [
            ("Дата", row.get("Дата")),
            ("ID заявки", row.get("ID заявки")),
            ("Номер заявки", row.get("Номер маршрутного листа")),
            ("Изделие", row.get("Изделие")),
            ("Цвет ткани", row.get("Цвет ткани")),
            ("Размер", row.get("Размер")),
            ("Стопка", row.get("Стопка")),
            ("Комментарий", row.get("Комментарий")),
            ("Швея", row.get("Швея")),
        ]

        for label, value in fields:
            pdf.drawString(LEFT, y, f"{label}: {value}")
            y -= LINE_H

        # Фото
        y -= 10
        pdf.setFont("DejaVu", 13)
        pdf.drawString(LEFT, y, "Фото:")
        y -= 20

        file_ids = (row.get("Фото (file_id)") or "")
        file_ids = [f.strip() for f in file_ids.split(",") if f.strip()]

        if not file_ids:
            pdf.setFont("DejaVu", 12)
            pdf.drawString(LEFT, y, "Нет фото")
            y -= 30
        else:

            img_size = 160
            x = LEFT

            for fid in file_ids:

                if x + img_size > PAGE_W - LEFT:
                    x = LEFT
                    y -= img_size + 20

                try:
                    file_info = await bot.get_file(fid)
                    url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
                    resp = requests.get(url)
                    img = ImageReader(BytesIO(resp.content))
                except:
                    pdf.drawString(x, y, "[Ошибка загрузки фото]")
                    x += img_size + 10
                    continue

                pdf.drawImage(
                    img,
                    x,
                    y - img_size,
                    width=img_size,
                    height=img_size,
                    preserveAspectRatio=True,
                    mask="auto"
                )
                x += img_size + 10

            y -= img_size + 30

        # линия между блоками
        pdf.line(LEFT, y, PAGE_W - LEFT, y)
        y -= 30

    # Сохранение PDF
    pdf.save()

    # Отправка PDF пользователю
    await bot.send_document(
        call.message.chat.id,
        open(filename, "rb"),
        caption="📄 PDF отчёт по браку сформирован."
    )
