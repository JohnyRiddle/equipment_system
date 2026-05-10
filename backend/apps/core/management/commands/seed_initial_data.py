from django.core.management.base import BaseCommand

from apps.equipment.models import EquipmentCategory, EquipmentStatus
from apps.locations.models import Location
from apps.organizations.models import CostCenter, LegalEntity
from apps.warehouses.models import Warehouse


LEGAL_ENTITIES = [
    ('ООО «Трансавангард»', 'Трансавангард'),
    ('ООО «Грелка»', 'Грелка'),
    ('ООО «Северный Мустаг»', 'Северный Мустаг'),
]

LOCATIONS = [
    'Шерегеш',
    'Алтай',
    'Сочи',
    'Москва',
    'Новосибирск',
]

COST_CENTERS = [
    'Грелка',
    'Варя',
    'Восточка',
    'Напойка',
    'Wow Kitchen',
    'Катадзе',
    'Бункер',
]

WAREHOUSES = [
    'Бар',
    'Кухня',
    'Посуда',
    'Оборудование',
    'Хозяйственный',
]

STATUSES = [
    ('В работе', 'WORKING'),
    ('На ремонте', 'REPAIR'),
    ('Списано', 'WRITTEN_OFF'),
    ('На складе', 'STORAGE'),
]

CATEGORIES = [
    'Холодильное оборудование',
    'Тепловое оборудование',
    'POS-оборудование',
    'Сетевое оборудование',
    'Прочее',
]


class Command(BaseCommand):
    help = 'Seed initial AYS CRM directories. Safe to run multiple times.'

    def handle(self, *args, **options):
        legal_entities = self._seed_legal_entities()
        locations = self._seed_locations()
        cost_centers = self._seed_cost_centers(
            legal_entity=legal_entities['ООО «Грелка»'],
            location=locations['Шерегеш'],
        )
        self._seed_warehouses(cost_centers)
        self._seed_statuses()
        self._seed_categories()

        self.stdout.write(self.style.SUCCESS('Initial directories are ready.'))

    def _seed_legal_entities(self):
        result = {}
        for name, short_name in LEGAL_ENTITIES:
            legal_entity, _ = LegalEntity.objects.update_or_create(
                name=name,
                defaults={
                    'short_name': short_name,
                    'is_active': True,
                },
            )
            result[name] = legal_entity
        self.stdout.write(f'Legal entities: {len(result)}')
        return result

    def _seed_locations(self):
        result = {}
        for name in LOCATIONS:
            location, _ = Location.objects.update_or_create(
                name=name,
                defaults={'is_active': True},
            )
            result[name] = location
        self.stdout.write(f'Locations: {len(result)}')
        return result

    def _seed_cost_centers(self, legal_entity, location):
        result = []
        for name in COST_CENTERS:
            cost_center, _ = CostCenter.objects.update_or_create(
                legal_entity=legal_entity,
                location=location,
                name=name,
                defaults={'is_active': True},
            )
            result.append(cost_center)
        self.stdout.write(f'Cost centers: {len(result)}')
        return result

    def _seed_warehouses(self, cost_centers):
        count = 0
        for cost_center in cost_centers:
            for name in WAREHOUSES:
                Warehouse.objects.update_or_create(
                    cost_center=cost_center,
                    name=name,
                    defaults={'is_active': True},
                )
                count += 1
        self.stdout.write(f'Warehouses: {count}')

    def _seed_statuses(self):
        for name, code in STATUSES:
            EquipmentStatus.objects.update_or_create(
                code=code,
                defaults={'name': name},
            )
        self.stdout.write(f'Equipment statuses: {len(STATUSES)}')

    def _seed_categories(self):
        for name in CATEGORIES:
            EquipmentCategory.objects.update_or_create(name=name)
        self.stdout.write(f'Equipment categories: {len(CATEGORIES)}')
