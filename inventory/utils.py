
from datetime import date, datetime, timedelta
from django.db.models import Sum
from inventory.models import Item, DailySnapshot, DailyItemSnapshot, StockMovement


# inventory/utils.py

def create_snapshot(snapshot_date=None):
    snapshot_date = snapshot_date or date.today()
    snapshot, _ = DailySnapshot.objects.get_or_create(date=snapshot_date)

    yesterday_date = snapshot_date - timedelta(days=1)
    previous_snapshot = DailySnapshot.objects.filter(date=yesterday_date).first()

    items = Item.objects.all()
    start = datetime.combine(snapshot_date, datetime.min.time())
    end = start + timedelta(days=1)

    for item in items:
        # FIXED: Beginning is strictly from yesterday's record. 
        # If no record exists, it MUST be 0 to avoid double-counting today's stock.
        beginning = 0
        if previous_snapshot:
            prev_item = DailyItemSnapshot.objects.filter(
                snapshot=previous_snapshot, item=item
            ).first()
            beginning = prev_item.ending_quantity if prev_item else 0
        else:
            # If the entire system has no previous snapshots, start at 0
            beginning = 0

        # Calculate Movements for the specific date
        stock_in = StockMovement.objects.filter(
            item=item, reason="add", date__range=(start, end)
        ).aggregate(total=Sum('quantity'))['total'] or 0

        stock_out = StockMovement.objects.filter(
            item=item, reason="remove", date__range=(start, end)
        ).aggregate(total=Sum('quantity'))['total'] or 0

        # Calculate Ending: 0 + 31 - 0 = 31
        ending = beginning + stock_in - stock_out

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
