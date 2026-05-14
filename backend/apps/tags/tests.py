from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.equipment.models import Equipment, EquipmentCategory, EquipmentStatus
from apps.locations.models import Location
from apps.organizations.models import CostCenter, LegalEntity
from apps.tags.services import build_equipment_qr_payload
from apps.warehouses.models import Warehouse


class EquipmentQrPayloadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        legal_entity = LegalEntity.objects.create(name='ООО Грелка')
        location = Location.objects.create(name='Шерегеш')
        cost_center = CostCenter.objects.create(
            legal_entity=legal_entity,
            location=location,
            name='Грелка',
        )
        warehouse = Warehouse.objects.create(cost_center=cost_center, name='Бар')
        category = EquipmentCategory.objects.create(name='POS')
        status = EquipmentStatus.objects.create(name='В работе', code='WORKING')
        cls.equipment = Equipment.objects.create(
            legal_entity=legal_entity,
            location=location,
            cost_center=cost_center,
            warehouse=warehouse,
            category=category,
            status=status,
            name='Тестовый терминал',
        )

    @override_settings(QR_EQUIPMENT_BASE_URL='', ALLOWED_HOSTS=['local.test'])
    def test_payload_uses_request_host_when_base_url_is_auto(self):
        request = RequestFactory().get('/', HTTP_HOST='local.test:8000')

        payload = build_equipment_qr_payload(self.equipment, request=request)

        self.assertEqual(payload, f'http://local.test:8000/equipment/{self.equipment.pk}/')

    @override_settings(QR_EQUIPMENT_BASE_URL='https://crm.example.com/equipment')
    def test_payload_uses_configured_base_url(self):
        payload = build_equipment_qr_payload(self.equipment)

        self.assertEqual(payload, f'https://crm.example.com/equipment/{self.equipment.pk}/')

    @override_settings(QR_EQUIPMENT_BASE_URL='auto')
    def test_payload_falls_back_to_relative_url_without_request(self):
        payload = build_equipment_qr_payload(self.equipment)

        self.assertEqual(payload, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
