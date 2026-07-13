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


def draw_text_lines(pdf, lines, x, y, max_width, line_height, max_lines=4, font_size=8, align='left'):
    pdf.setFont(FONT_NAME, font_size)
    current_y = y
    rendered = 0

    for line in lines:
        if not line:
            continue
        words = str(line).split()
        current = ''
        for word in words:
            candidate = f'{current} {word}'.strip()
            if pdf.stringWidth(candidate, FONT_NAME, font_size) <= max_width:
                current = candidate
                continue
            if current:
                line_x = x
                if align == 'center':
                    line_x = x + (max_width - pdf.stringWidth(current, FONT_NAME, font_size)) / 2
                pdf.drawString(line_x, current_y, current)
                current_y -= line_height
                rendered += 1
                current = word
            if rendered >= max_lines:
                return
        if current and rendered < max_lines:
            line_x = x
            if align == 'center':
                line_x = x + (max_width - pdf.stringWidth(current, FONT_NAME, font_size)) / 2
            pdf.drawString(line_x, current_y, current)
            current_y -= line_height
            rendered += 1
        if rendered >= max_lines:
            return


def get_active_qr_code(equipment):
    tag = equipment.tags.filter(tag_type='QR', is_active=True).first()
    return tag.code if tag else ''


def build_qr_labels_pdf(equipment_items):
    register_pdf_font()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_x = 12 * mm
    margin_top = 45 * mm
    margin_bottom = 12 * mm
    gap = 4 * mm
    columns = 3
    rows = 5
    label_width = 55 * mm
    label_height = 40 * mm
    qr_size = 22 * mm

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

        payload = build_equipment_qr_payload(equipment)
        qr_x = x + (label_width - qr_size) / 2
        qr_y = y + 10 * mm
        qr_code = get_active_qr_code(equipment)

        if qr_code:
            pdf.setFillColor(colors.HexColor('#0b0b0c'))
            pdf.setFont(FONT_NAME, 9)
            code_width = pdf.stringWidth(qr_code, FONT_NAME, 9)
            pdf.drawString(x + (label_width - code_width) / 2, y + label_height - 5 * mm, qr_code)

        pdf.drawImage(
            qr_image_reader(payload),
            qr_x,
            qr_y,
            width=qr_size,
            height=qr_size,
            preserveAspectRatio=True,
            mask='auto',
        )

        pdf.setFillColor(colors.HexColor('#0b0b0c'))
        draw_text_lines(
            pdf,
            [
                equipment.name,
                f'Инв.: {equipment.inventory_number or "—"}',
                f'Сер.: {equipment.serial_number or "—"}',
            ],
            x + 3 * mm,
            y + 6.5 * mm,
            label_width - 6 * mm,
            2.6 * mm,
            max_lines=3,
            font_size=6,
            align='center',
        )

    if not equipment_items:
        pdf.setFont(FONT_NAME, 14)
        pdf.drawString(margin_x, height - margin_top, 'Нет оборудования для печати QR.')

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
