from django.test import TestCase

from apps.equipment.models import Equipment
from apps.locations.models import Location


class EquipmentInventoryNumberTests(TestCase):
    def test_equipment_save_assigns_inventory_number_by_location(self):
        location = Location.objects.create(name='Шерегеш')

        equipment = Equipment.objects.create(name='Холодильник', location=location)
        next_equipment = Equipment.objects.create(name='Печь', location=location)

        self.assertEqual(equipment.inventory_number, 'GESH-A0001')
        self.assertEqual(next_equipment.inventory_number, 'GESH-A0002')

    def test_equipment_save_keeps_existing_inventory_number(self):
        location = Location.objects.create(name='Шерегеш')

        equipment = Equipment.objects.create(
            name='Весы',
            location=location,
            inventory_number='MANUAL-001',
        )

        self.assertEqual(equipment.inventory_number, 'MANUAL-001')

    def test_equipment_without_location_gets_generic_prefix(self):
        equipment = Equipment.objects.create(name='Без локации')

        self.assertEqual(equipment.inventory_number, 'GEN-A0001')
