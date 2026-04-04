# inventory/utils.py
from datetime import date, datetime, timedelta
from django.db.models import Sum
from inventory.models import Item, DailySnapshot, DailyItemSnapshot, StockMovement


def create_snapshot(snapshot_date=None):
    snapshot_date = snapshot_date or date.today()
    snapshot, _ = DailySnapshot.objects.get_or_create(date=snapshot_date)

    # Use a specific 'yesterday' date to ensure chain continuity
    yesterday_date = snapshot_date - timedelta(days=1)
    previous_snapshot = DailySnapshot.objects.filter(date=yesterday_date).first()

    items = Item.objects.all()
    start = datetime.combine(snapshot_date, datetime.min.time())
    end = start + timedelta(days=1)

    for item in items:
        # Determine Beginning Balance
        beginning = 0
        if previous_snapshot:
            prev_item = DailyItemSnapshot.objects.filter(
                snapshot=previous_snapshot, item=item
            ).first()
            # Carry over the previous ending, or fallback to live quantity
            beginning = prev_item.ending_quantity if prev_item else item.quantity
        else:
            # FIX: Use live quantity instead of 0 for new snapshots
            beginning = item.quantity

        # Calculate Movements
        stock_in = StockMovement.objects.filter(
            item=item, reason="add", date__range=(start, end)
        ).aggregate(total=Sum('quantity'))['total'] or 0

        stock_out = StockMovement.objects.filter(
            item=item, reason="remove", date__range=(start, end)
        ).aggregate(total=Sum('quantity'))['total'] or 0

        # Calculate Ending
        ending = beginning + stock_in - stock_out

        # Save or Update
        DailyItemSnapshot.objects.update_or_create(
            snapshot=snapshot,
            item=item,
            defaults={
                'beginning_quantity': beginning,
                'stock_in': stock_in,
                'stock_out': stock_out,
                'ending_quantity': ending
            }
        )
    return snapshot

def ensure_daily_snapshots():
    today = date.today()
    yesterday = today - timedelta(days=1)

    # Ensure yesterday exists
    if not DailySnapshot.objects.filter(date=yesterday).exists():
        create_snapshot(snapshot_date=yesterday)

    # Ensure today exists
    if not DailySnapshot.objects.filter(date=today).exists():
        create_snapshot(snapshot_date=today)

    return True
