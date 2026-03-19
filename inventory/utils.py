from datetime import timedelta
from django.utils import timezone
from .models import DailySnapshot, DailyItemSnapshot, Item

def create_snapshot(snapshot_date=None):
    if not snapshot_date:
        snapshot_date = timezone.localdate()

    # Get or create today's snapshot
    snapshot, created = DailySnapshot.objects.get_or_create(date=snapshot_date)

    # Get yesterday's snapshot
    yesterday = snapshot_date - timedelta(days=1)
    prev_snapshot = DailySnapshot.objects.filter(date=yesterday).first()

    # Check which items are missing in today's snapshot
    existing_item_ids = set(DailyItemSnapshot.objects.filter(snapshot=snapshot).values_list('item_id', flat=True))
    items_to_create = Item.objects.exclude(id__in=existing_item_ids)

    daily_snapshots = []
    for item in items_to_create:
        # beginning_quantity comes from yesterday's ending_quantity
        beginning_qty = 0
        if prev_snapshot:
            prev_item = DailyItemSnapshot.objects.filter(snapshot=prev_snapshot, item=item).first()
            if prev_item:
                beginning_qty = prev_item.ending_quantity
        else:
            beginning_qty = item.quantity  # only for the first day ever

        daily_snapshots.append(DailyItemSnapshot(
            snapshot=snapshot,
            item=item,
            beginning_quantity=beginning_qty,
            stock_in=0,
            stock_out=0,
            ending_quantity=beginning_qty
        ))

    if daily_snapshots:
        DailyItemSnapshot.objects.bulk_create(daily_snapshots)

    return snapshot