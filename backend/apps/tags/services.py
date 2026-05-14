from django.conf import settings
from django.urls import reverse

from apps.tags.models import EquipmentTag


def _configured_equipment_base_url():
    base_url = getattr(settings, 'QR_EQUIPMENT_BASE_URL', '')
    if not base_url or base_url.lower() == 'auto':
        return ''
    return base_url.rstrip('/')


def build_equipment_qr_payload(equipment, request=None, base_url=None):
    if base_url:
        return f'{base_url.rstrip("/")}/{equipment.id}/'

    configured_base_url = _configured_equipment_base_url()
    if configured_base_url:
        return f'{configured_base_url}/{equipment.id}/'

    path = reverse('equipment_detail', kwargs={'pk': equipment.pk})
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def generate_next_qr_code():
    last_tag = EquipmentTag.objects.filter(
        tag_type='QR'
    ).order_by('-assigned_at').first()

    if not last_tag:
        return 'EQ-000001'

    last_code = last_tag.code

    if not last_code.startswith('EQ-'):
        return 'EQ-000001'

    try:
        last_number = int(last_code.replace('EQ-', ''))
    except ValueError:
        return 'EQ-000001'

    next_number = last_number + 1
    return f'EQ-{next_number:06d}'


def create_qr_tag_for_equipment(equipment, assigned_by=None, request=None, base_url=None):
    existing_tag = equipment.tags.filter(tag_type='QR', is_active=True).first()
    if existing_tag:
        return existing_tag

    code = generate_next_qr_code()

    tag = EquipmentTag.objects.create(
        equipment=equipment,
        legal_entity=equipment.legal_entity,
        tag_type='QR',
        code=code,
        payload=build_equipment_qr_payload(equipment, request=request, base_url=base_url),
        payload_format='url',
        assigned_by=assigned_by,
        is_active=True,
    )

    return tag


def regenerate_qr_tag_for_equipment(equipment, assigned_by=None, request=None, base_url=None):
    tag = equipment.tags.filter(tag_type='QR', is_active=True).first()
    if not tag:
        return create_qr_tag_for_equipment(equipment, assigned_by=assigned_by)

    tag.legal_entity = equipment.legal_entity
    tag.payload = build_equipment_qr_payload(equipment, request=request, base_url=base_url)
    tag.payload_format = 'url'
    if assigned_by is not None:
        tag.assigned_by = assigned_by
    if tag.qr_image:
        tag.qr_image.delete(save=False)
    tag.generate_qr_image()
    tag.save(update_fields=['legal_entity', 'payload', 'payload_format', 'assigned_by', 'qr_image'])
    return tag
