from io import BytesIO
from pathlib import Path

import qrcode
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from apps.tags.services import build_equipment_qr_payload


FONT_NAME = 'Helvetica'
LABEL_SIZE = (55 * mm, 40 * mm)


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


def draw_label_page(pdf, equipment):
    label_width, label_height = LABEL_SIZE
    padding_x = 3 * mm
    qr_size = 21 * mm
    qr_x = (label_width - qr_size) / 2
    qr_y = 10.5 * mm

    pdf.setPageSize(LABEL_SIZE)
    pdf.setStrokeColor(colors.HexColor('#d7dbe2'))
    pdf.setLineWidth(0.5)
    pdf.roundRect(0.8 * mm, 0.8 * mm, label_width - 1.6 * mm, label_height - 1.6 * mm, 3, stroke=1, fill=0)

    qr_code = get_active_qr_code(equipment)
    if qr_code:
        pdf.setFillColor(colors.HexColor('#0b0b0c'))
        pdf.setFont(FONT_NAME, 9)
        code_width = pdf.stringWidth(qr_code, FONT_NAME, 9)
        pdf.drawString((label_width - code_width) / 2, label_height - 5 * mm, qr_code)

    pdf.drawImage(
        qr_image_reader(build_equipment_qr_payload(equipment)),
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
            f'Инв.: {equipment.inventory_number or "-"}',
            f'Сер.: {equipment.serial_number or "-"}',
        ],
        padding_x,
        7.2 * mm,
        label_width - padding_x * 2,
        2.5 * mm,
        max_lines=3,
        font_size=6,
        align='center',
    )


def build_qr_labels_pdf(equipment_items):
    register_pdf_font()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LABEL_SIZE, pageCompression=0)

    if not equipment_items:
        pdf.setPageSize(LABEL_SIZE)
        pdf.setFont(FONT_NAME, 8)
        pdf.drawCentredString(LABEL_SIZE[0] / 2, LABEL_SIZE[1] / 2, 'Нет оборудования для печати QR.')
    else:
        for index, equipment in enumerate(equipment_items):
            if index:
                pdf.showPage()
            draw_label_page(pdf, equipment)

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
