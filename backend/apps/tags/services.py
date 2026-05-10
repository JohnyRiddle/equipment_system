from django.conf import settings

from apps.tags.models import EquipmentTag


def build_equipment_qr_payload(equipment):
    base_url = getattr(settings, 'QR_EQUIPMENT_BASE_URL', 'https://ays-crm.ru/equipment')
    return f'{base_url.rstrip("/")}/{equipment.id}/'


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


def create_qr_tag_for_equipment(equipment, assigned_by=None):
    existing_tag = equipment.tags.filter(tag_type='QR', is_active=True).first()
    if existing_tag:
        return existing_tag

    code = generate_next_qr_code()

    tag = EquipmentTag.objects.create(
        equipment=equipment,
        legal_entity=equipment.legal_entity,
        tag_type='QR',
        code=code,
        payload=build_equipment_qr_payload(equipment),
        payload_format='url',
        assigned_by=assigned_by,
        is_active=True,
    )

    return tag


def regenerate_qr_tag_for_equipment(equipment, assigned_by=None):
    tag = equipment.tags.filter(tag_type='QR', is_active=True).first()
    if not tag:
        return create_qr_tag_for_equipment(equipment, assigned_by=assigned_by)

    tag.legal_entity = equipment.legal_entity
    tag.payload = build_equipment_qr_payload(equipment)
    tag.payload_format = 'url'
    if assigned_by is not None:
        tag.assigned_by = assigned_by
    if tag.qr_image:
        tag.qr_image.delete(save=False)
    tag.generate_qr_image()
    tag.save(update_fields=['legal_entity', 'payload', 'payload_format', 'assigned_by', 'qr_image'])
    return tag
