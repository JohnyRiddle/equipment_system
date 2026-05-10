from django.core.management.base import BaseCommand

from apps.equipment.models import Equipment
from apps.tags.services import regenerate_qr_tag_for_equipment


class Command(BaseCommand):
    help = 'Regenerate QR tags and images for equipment.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Regenerate QR codes for inactive equipment too.',
        )

    def handle(self, *args, **options):
        equipment_queryset = Equipment.objects.select_related('legal_entity').order_by('name')
        if not options['all']:
            equipment_queryset = equipment_queryset.filter(is_active=True)

        count = 0
        for equipment in equipment_queryset.iterator():
            regenerate_qr_tag_for_equipment(equipment)
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Regenerated QR codes: {count}'))
