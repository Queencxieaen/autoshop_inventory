# inventory/utils.py
from datetime import date, datetime, timedelta
from django.db.models import Sum
from inventory.models import Item, DailySnapshot, DailyItemSnapshot, StockMovement


def create_snapshot(snapshot_date=None):
    snapshot_date = snapshot_date or date.today()

    # Create or get snapshot
    snapshot, _ = DailySnapshot.objects.get_or_create(date=snapshot_date)

    # ✅ Lock past days, allow today to update
    today = date.today()

    if snapshot.date != today:
        if DailyItemSnapshot.objects.filter(snapshot=snapshot).exists():
            return snapshot

    # ✅ Only clear today's snapshot (so it updates live)
    if snapshot.date == today:
        DailyItemSnapshot.objects.filter(snapshot=snapshot).delete()

    items = Item.objects.all()

    # ✅ Correct date range (fix timezone issue)
    start = datetime.combine(snapshot_date, datetime.min.time())
    end = start + timedelta(days=1)

    for item in items:
        # Get previous ending as beginning
        try:
            prev_snapshot = DailySnapshot.objects.filter(date__lt=snapshot_date).latest('date')
            prev_item = DailyItemSnapshot.objects.get(snapshot=prev_snapshot, item=item)
            beginning = prev_item.ending_quantity
        except:
            beginning = item.quantity or 0

        # ✅ FIXED stock movement query
        stock_in = StockMovement.objects.filter(
            item=item,
            reason="add",
            date__gte=start,
            date__lt=end
        ).aggregate(total=Sum('quantity'))['total'] or 0

        stock_out = StockMovement.objects.filter(
            item=item,
            reason="remove",
            date__gte=start,
            date__lt=end
        ).aggregate(total=Sum('quantity'))['total'] or 0

        ending = beginning + stock_in - stock_out

        DailyItemSnapshot.objects.create(
            snapshot=snapshot,
            item=item,
            beginning_quantity=beginning,
            stock_in=stock_in,
            stock_out=stock_out,
            ending_quantity=ending
        )

    return snapshot