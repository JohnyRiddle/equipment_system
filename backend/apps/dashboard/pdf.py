from io import BytesIO
from pathlib import Path

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from apps.tags.services import build_equipment_qr_payload


FONT_NAME = 'Helvetica'


def register_pdf_font():
    global FONT_NAME

    candidates = [
        Path('C:/Windows/Fonts/arial.ttf'),
        Path('C:/Windows/Fonts/calibri.ttf'),
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
    ]
    for font_path in candidates:
        if font_path.exists():
            pdfmetrics.registerFont(TTFont('AYSFont', str(font_path)))
            FONT_NAME = 'AYSFont'
            return


def qr_image_reader(payload):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color='black', back_color='white')
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    return ImageReader(buffer)


def draw_text_lines(pdf, lines, x, y, max_width, line_height, max_lines=4):
    pdf.setFont(FONT_NAME, 8)
    current_y = y
    rendered = 0

    for line in lines:
        if not line:
            continue
        words = str(line).split()
        current = ''
        for word in words:
            candidate = f'{current} {word}'.strip()
            if pdf.stringWidth(candidate, FONT_NAME, 8) <= max_width:
                current = candidate
                continue
            if current:
                pdf.drawString(x, current_y, current)
                current_y -= line_height
                rendered += 1
                current = word
            if rendered >= max_lines:
                return
        if current and rendered < max_lines:
            pdf.drawString(x, current_y, current)
            current_y -= line_height
            rendered += 1
        if rendered >= max_lines:
            return


def build_qr_labels_pdf(equipment_items):
    register_pdf_font()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_x = 12 * mm
    margin_top = 45 * mm
    margin_bottom = 12 * mm
    gap = 4 * mm
    columns = 2
    rows = 4
    label_width = (width - margin_x * 2 - gap) / columns
    label_height = (height - margin_top - margin_bottom - gap * (rows - 1)) / rows
    qr_size = 31 * mm

    for index, equipment in enumerate(equipment_items):
        position = index % (columns * rows)
        if index and position == 0:
            pdf.showPage()

        col = position % columns
        row = position // columns
        x = margin_x + col * (label_width + gap)
        y = height - margin_top - (row + 1) * label_height - row * gap

        pdf.setStrokeColor(colors.HexColor('#d7dbe2'))
        pdf.setLineWidth(0.7)
        pdf.roundRect(x, y, label_width, label_height, 4, stroke=1, fill=0)

        pdf.setFillColor(colors.HexColor('#ff4c34'))
        pdf.rect(x, y + label_height - 3, label_width, 3, stroke=0, fill=1)

        payload = build_equipment_qr_payload(equipment)
        pdf.drawImage(
            qr_image_reader(payload),
            x + 5 * mm,
            y + label_height - qr_size - 8 * mm,
            width=qr_size,
            height=qr_size,
            preserveAspectRatio=True,
            mask='auto',
        )

        text_x = x + qr_size + 9 * mm
        text_y = y + label_height - 12 * mm
        text_width = label_width - qr_size - 14 * mm

        pdf.setFillColor(colors.HexColor('#0b0b0c'))
        pdf.setFont(FONT_NAME, 10)
        draw_text_lines(
            pdf,
            [
                equipment.name,
                f'Инв.: {equipment.inventory_number or "—"}',
                f'Сер.: {equipment.serial_number or "—"}',
                f'{equipment.location or "—"} / {equipment.warehouse or "—"}',
            ],
            text_x,
            text_y,
            text_width,
            4.2 * mm,
            max_lines=5,
        )

        pdf.setFont(FONT_NAME, 7)
        pdf.setFillColor(colors.HexColor('#6b7280'))
        pdf.drawString(x + 5 * mm, y + 5 * mm, payload)

    if not equipment_items:
        pdf.setFont(FONT_NAME, 14)
        pdf.drawString(margin_x, height - margin_top, 'Нет оборудования для печати QR.')

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
