from django.core.management.base import BaseCommand
from inventory.models import DailySnapshot, DailyItemSnapshot, Item
from django.utils import timezone

class Command(BaseCommand):
    help = "Create daily snapshot for all items at the start of the day"

    def handle(self, *args, **kwargs):
        # 1. Use local date
        today = timezone.localdate()
        
        # 2. Prevent duplicates
        snapshot, created = DailySnapshot.objects.get_or_create(date=today)
        if not created:
            self.stdout.write(self.style.WARNING(f"Snapshot already exists for {today}."))
            return

        # 3. Create records for every item
        items = Item.objects.all()
        snapshot_records = []
        
        for item in items:
            snapshot_records.append(DailyItemSnapshot(
                snapshot=snapshot,
                item=item,
                beginning_quantity=item.quantity, # Current stock at 12:01 AM
                stock_in=0,
                stock_out=0,
                ending_quantity=item.quantity
            ))
        
        # 4. Use bulk_create for speed (much faster than a loop save)
        DailyItemSnapshot.objects.bulk_create(snapshot_records)

        self.stdout.write(self.style.SUCCESS(f"Successfully initiated snapshot for {today}"))
