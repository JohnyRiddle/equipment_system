from pathlib import Path
from datetime import datetime

from django.core.management import BaseCommand, call_command
from django.conf import settings


class Command(BaseCommand):
    help = 'Create a full database backup in Django XML format.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            help='Exact XML file path. If omitted, a timestamped file is created.',
        )
        parser.add_argument(
            '--output-dir',
            default=str(settings.BASE_DIR.parent / 'backups' / 'database'),
            help='Directory for timestamped XML backups when --output is omitted.',
        )

    def handle(self, *args, **options):
        output = options.get('output')
        if output:
            output_path = Path(output)
        else:
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            output_path = Path(options['output_dir']) / f'database-{timestamp}.xml'

        output_path.parent.mkdir(parents=True, exist_ok=True)

        call_command(
            'dumpdata',
            format='xml',
            indent=2,
            output=str(output_path),
            verbosity=0,
        )

        self.stdout.write(self.style.SUCCESS(f'XML database backup created: {output_path}'))
