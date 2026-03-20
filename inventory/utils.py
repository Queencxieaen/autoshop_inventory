from datetime import timedelta
from django.utils import timezone
from .models import DailySnapshot, DailyItemSnapshot, Item, StockMovement

def create_snapshot(snapshot_date=None):
    if not snapshot_date:
        snapshot_date = timezone.localdate()

    # 1. Get or create snapshot for this date
    snapshot, _ = DailySnapshot.objects.get_or_create(date=snapshot_date)

    # 2. Get yesterday's snapshot for beginning quantities
    yesterday = snapshot_date - timedelta(days=1)
    prev_snapshot = DailySnapshot.objects.filter(date=yesterday).first()

    # 3. Determine which items are missing in today's snapshot
    existing_item_ids = set(DailyItemSnapshot.objects.filter(snapshot=snapshot).values_list('item_id', flat=True))
    items_to_create = Item.objects.exclude(id__in=existing_item_ids)

    daily_snapshots = []
    for item in items_to_create:
        # Beginning quantity
        beginning_qty = 0
        if prev_snapshot:
            prev_item = DailyItemSnapshot.objects.filter(snapshot=prev_snapshot, item=item).first()
            if prev_item:
                beginning_qty = prev_item.ending_quantity
        else:
            beginning_qty = item.quantity

        # Calculate today's Stock In / Stock Out
        movements = StockMovement.objects.filter(
            item=item,
            date__date=snapshot_date
        )
        stock_in = sum(m.quantity for m in movements if m.quantity > 0)
        stock_out = sum(abs(m.quantity) for m in movements if m.quantity < 0)

        # Ending quantity
        ending_qty = beginning_qty + stock_in - stock_out

        daily_snapshots.append(DailyItemSnapshot(
            snapshot=snapshot,
            item=item,
            beginning_quantity=beginning_qty,
            stock_in=stock_in,
            stock_out=stock_out,
            ending_quantity=ending_qty
        ))

    # 4. Save only new items
    if daily_snapshots:
        DailyItemSnapshot.objects.bulk_create(daily_snapshots)

    return snapshot