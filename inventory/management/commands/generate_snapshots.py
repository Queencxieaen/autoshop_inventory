from django.core.management.base import BaseCommand
from django.utils import timezone
from inventory.views import create_snapshot  # use your existing function

class Command(BaseCommand):
    help = 'Generate daily snapshot for inventory (midnight job)'

    def handle(self, *args, **kwargs):
        today = timezone.localdate()
        create_snapshot(today)
        self.stdout.write(self.style.SUCCESS('Snapshot created successfully'))  