# inventory/utils.py
from datetime import date, timedelta
from django.db.models import Sum
from inventory.models import Item, DailySnapshot, DailyItemSnapshot, StockMovement

def create_snapshot(snapshot_date=None):
    snapshot_date = snapshot_date or date.today()

    # Check if snapshot already exists
    snapshot, created = DailySnapshot.objects.get_or_create(date=snapshot_date)

    # Prevent recreating item snapshots if they already exist
    if DailyItemSnapshot.objects.filter(snapshot=snapshot).exists():
        return snapshot

    items = Item.objects.all()

    for item in items:
        # Get previous snapshot to set beginning
        try:
            prev_snapshot = DailySnapshot.objects.filter(date__lt=snapshot_date).latest('date')
            prev_item_snapshot = DailyItemSnapshot.objects.get(snapshot=prev_snapshot, item=item)
            beginning = prev_item_snapshot.ending
        except (DailySnapshot.DoesNotExist, DailyItemSnapshot.DoesNotExist):
            beginning = item.initial_stock or 0

        # Sum stock movements for this day only
        stock_in = StockMovement.objects.filter(
            item=item, type='in', created_at__date=snapshot_date
        ).aggregate(total=Sum('quantity'))['total'] or 0

        stock_out = StockMovement.objects.filter(
            item=item, type='out', created_at__date=snapshot_date
        ).aggregate(total=Sum('quantity'))['total'] or 0

        ending = beginning + stock_in - stock_out

        # Save item snapshot
        DailyItemSnapshot.objects.create(
            snapshot=snapshot,
            item=item,
            beginning=beginning,
            stock_in=stock_in,
            stock_out=stock_out,
            ending=ending
        )

    return snapshot