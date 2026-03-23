# inventory/utils.py
from datetime import date, datetime, timedelta
from django.db.models import Sum
from inventory.models import Item, DailySnapshot, DailyItemSnapshot, StockMovement


def create_snapshot(snapshot_date=None):
    snapshot_date = snapshot_date or date.today()

    snapshot, created = DailySnapshot.objects.get_or_create(date=snapshot_date)

    # ❌ DO NOT TOUCH if already exists (VERY IMPORTANT)
    if not created:
        return snapshot

    items = Item.objects.all()

    start = datetime.combine(snapshot_date, datetime.min.time())
    end = start + timedelta(days=1)

    # Get previous snapshot
    previous_snapshot = DailySnapshot.objects.filter(date__lt=snapshot_date).order_by('-date').first()

    for item in items:
        # ✅ Get previous ending
        if previous_snapshot:
            prev_item = DailyItemSnapshot.objects.filter(
                snapshot=previous_snapshot,
                item=item
            ).first()
            beginning = prev_item.ending_quantity if prev_item else 0
        else:
            beginning = item.quantity or 0

        # Calculate movements
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