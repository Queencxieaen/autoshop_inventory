
from datetime import timedelta
from django.utils import timezone
from .models import DailySnapshot, DailyItemSnapshot, Item

def create_snapshot(snapshot_date=None):
    snapshot_date = snapshot_date or timezone.localdate()
    
    snapshot, created = DailySnapshot.objects.get_or_create(date=snapshot_date)

    if created:
        yesterday = snapshot_date - timedelta(days=1)
        prev_snapshot = DailySnapshot.objects.filter(date=yesterday).first()

        for item in Item.objects.all():
            if prev_snapshot:
                prev_item_snapshot = prev_snapshot.items.filter(item=item).first()
                beginning = prev_item_snapshot.ending_quantity if prev_item_snapshot else item.quantity
            else:
                beginning = item.quantity

            DailyItemSnapshot.objects.create(
                snapshot=snapshot,
                item=item,
                beginning_quantity=beginning,
                stock_in=0,
                stock_out=0,
                ending_quantity=beginning
            )

    return snapshot