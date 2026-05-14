from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

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
        parser.add_argument(
            '--base-url',
            default=None,
            help='Override equipment base URL, for example https://crm.example.com/equipment.',
        )

    def handle(self, *args, **options):
        configured_base_url = getattr(settings, 'QR_EQUIPMENT_BASE_URL', '')
        if not options['base_url'] and (not configured_base_url or configured_base_url.lower() == 'auto'):
            raise CommandError(
                'Use --base-url or set QR_EQUIPMENT_BASE_URL before bulk QR regeneration.'
            )

        equipment_queryset = Equipment.objects.select_related('legal_entity').order_by('name')
        if not options['all']:
            equipment_queryset = equipment_queryset.filter(is_active=True)

        count = 0
        for equipment in equipment_queryset.iterator():
            regenerate_qr_tag_for_equipment(equipment, base_url=options['base_url'])
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Regenerated QR codes: {count}'))
