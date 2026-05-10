from django.core.management.base import BaseCommand

from apps.accesses.models import AccessType


ACCESS_TYPES = [
    ('rdp', 'RDP', 10),
    ('ssh', 'SSH', 20),
    ('vpn', 'VPN', 30),
    ('web_admin', 'Web admin', 40),
    ('database', 'Database', 50),
    ('pos_admin', 'POS admin', 60),
    ('wifi', 'Wi-Fi', 70),
    ('other', 'Other', 100),
]


class Command(BaseCommand):
    help = 'Seed base access types.'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for code, name, sort_order in ACCESS_TYPES:
            _, was_created = AccessType.objects.update_or_create(
                code=code,
                defaults={
                    'name': name,
                    'sort_order': sort_order,
                    'is_active': True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Access types seeded. Created: {created}. Updated: {updated}.'
        ))
