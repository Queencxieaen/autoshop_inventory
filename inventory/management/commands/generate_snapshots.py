from django.core.management.base import BaseCommand
from inventory.models import DailySnapshot, DailyItemSnapshot, Item
from django.utils import timezone

class Command(BaseCommand):
    help = "Create daily snapshot for all items"

    def handle(self, *args, **kwargs):
        today = timezone.localdate()
        snapshot, created = DailySnapshot.objects.get_or_create(date=today)
        if not created:
            self.stdout.write("Daily snapshot already exists for today.")
            return

        for item in Item.objects.all():
            DailyItemSnapshot.objects.create(
                snapshot=snapshot,
                item=item,
                beginning_quantity=item.quantity,
                stock_in=0,
                stock_out=0,
                ending_quantity=item.quantity
            )

        self.stdout.write(f"Daily snapshot created for {today}.")