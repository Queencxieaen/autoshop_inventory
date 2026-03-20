from django.core.management.base import BaseCommand
from datetime import date, timedelta
from inventory.utils import create_snapshot

class Command(BaseCommand):
    help = 'Automatically create daily snapshot for tomorrow'

    def handle(self, *args, **kwargs):
        tomorrow = date.today() + timedelta(days=1)
        create_snapshot(snapshot_date=tomorrow)
        self.stdout.write(self.style.SUCCESS(f'Created snapshot for {tomorrow}'))