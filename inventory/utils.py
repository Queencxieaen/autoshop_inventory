
from datetime import date, datetime, timedelta
from django.db.models import Sum
from inventory.models import Item, DailySnapshot, DailyItemSnapshot, StockMovement



def create_snapshot(snapshot_date=None):
    snapshot_date = snapshot_date or date.today()
    snapshot, _ = DailySnapshot.objects.get_or_create(date=snapshot_date)

    items = Item.objects.all()
    start = datetime.combine(snapshot_date, datetime.min.time())
    end = start + timedelta(days=1)

    for item in items:
        # 1. Look back for the TRUE starting point (not just yesterday)
        last_record = DailyItemSnapshot.objects.filter(
            item=item, 
            snapshot__date__lt=snapshot_date
        ).order_by('-snapshot__date').first()
        
        # Beginning is last day's ending. If brand new, use current Item.quantity
        beginning = last_record.ending_quantity if last_record else item.quantity

        # 2. Sum today's activity
        stock_in = StockMovement.objects.filter(
            item=item, reason="add", date__range=(start, end)
        ).aggregate(total=Sum('quantity'))['total'] or 0

        stock_out = StockMovement.objects.filter(
            item=item, reason="remove", date__range=(start, end)
        ).aggregate(total=Sum('quantity'))['total'] or 0

        # 3. THE CRITICAL FIX: Perform the math
        # Ending = 85 + 290 - 135 = 240
        ending = beginning + stock_in - stock_out

        # 4. Save the update
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
