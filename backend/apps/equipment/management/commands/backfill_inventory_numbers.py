from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.equipment.models import Equipment


class Command(BaseCommand):
    help = 'Проставляет инвентарные номера оборудованию, у которого номер не заполнен.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, какие номера будут назначены, но не сохранять изменения.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        equipment_items = (
            Equipment.objects
            .filter(Q(inventory_number__isnull=True) | Q(inventory_number=''))
            .select_related('location')
            .order_by('created_at', 'id')
        )

        total = equipment_items.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('Оборудования без инвентарного номера нет.'))
            return

        if dry_run:
            with transaction.atomic():
                self._backfill(equipment_items)
                transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING(f'DRY RUN: найдено позиций без номера: {total}. Изменения не сохранены.'))
        else:
            self._backfill(equipment_items)
            self.stdout.write(self.style.SUCCESS(f'Инвентарные номера проставлены: {total}.'))

    def _backfill(self, equipment_items):
        for equipment in equipment_items:
            old_number = equipment.inventory_number
            equipment.inventory_number = ''
            equipment.save()
            new_number = equipment.inventory_number

            self.stdout.write(f'{equipment.name or equipment.id}: {old_number or "-"} -> {new_number}')
