from django.core.management.base import BaseCommand
from datetime import date, timedelta
from inventory.utils import create_snapshot
from inventory.models import DailySnapshot

class Command(BaseCommand):
    help = 'Backfill missing daily snapshots up to today'

    def handle(self, *args, **kwargs):
        last_snapshot = DailySnapshot.objects.order_by('date').last()
        start_date = last_snapshot.date + timedelta(days=1) if last_snapshot else date.today()
        today = date.today()

        current = start_date
        while current <= today:
            create_snapshot(snapshot_date=current)
            self.stdout.write(self.style.SUCCESS(f'Created snapshot for {current}'))
            current += timedelta(days=1)