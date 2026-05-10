import uuid
from io import BytesIO

import qrcode
from django.core.files.base import ContentFile
from django.db import models


class EquipmentTag(models.Model):
    TAG_TYPE_CHOICES = [
        ('QR', 'QR Code'),
        ('NFC', 'NFC Tag'),
        ('BARCODE', 'Barcode'),
        ('RFID', 'RFID'),
    ]

    PAYLOAD_FORMAT_CHOICES = [
        ('url', 'URL'),
        ('uuid', 'UUID'),
        ('text', 'Text'),
        ('json', 'JSON'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    equipment = models.ForeignKey(
        'equipment.Equipment',
        on_delete=models.CASCADE,
        related_name='tags'
    )
    legal_entity = models.ForeignKey(
        'organizations.LegalEntity',
        on_delete=models.CASCADE,
        related_name='equipment_tags'
    )

    tag_type = models.CharField(max_length=20, choices=TAG_TYPE_CHOICES)
    code = models.CharField(max_length=255, unique=True)
    uid = models.CharField(max_length=255, blank=True, null=True)
    payload = models.TextField(blank=True)
    payload_format = models.CharField(max_length=20, choices=PAYLOAD_FORMAT_CHOICES, default='uuid')

    qr_image = models.ImageField(upload_to='qr_codes/', blank=True, null=True)

    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    assigned_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tags'
    )

    comment = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['uid']),
            models.Index(fields=['tag_type']),
        ]

    def __str__(self):
        return f'{self.tag_type} - {self.code}'

    def get_effective_payload(self):
        if self.payload:
            return self.payload
        return f'/tag/{self.code}/'

    def generate_qr_image(self):
        if self.tag_type != 'QR':
            return

        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=4,
        )
        qr.add_data(self.get_effective_payload())
        qr.make(fit=True)

        image = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        image.save(buffer, format='PNG')

        filename = f'qr_{self.code}.png'
        self.qr_image.save(filename, ContentFile(buffer.getvalue()), save=False)

    def save(self, *args, **kwargs):
        if self.tag_type == 'QR' and not self.qr_image:
            self.generate_qr_image()
        super().save(*args, **kwargs)