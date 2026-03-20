# inventory/utils.py
from datetime import date
from django.db.models import Sum
from inventory.models import Item, DailySnapshot, DailyItemSnapshot, StockMovement

def create_snapshot(snapshot_date=None):
    snapshot_date = snapshot_date or date.today()

    # Create or get snapshot
    snapshot, _ = DailySnapshot.objects.get_or_create(date=snapshot_date)

    # 🚨 IMPORTANT: Clear old items to prevent duplication
    DailyItemSnapshot.objects.filter(snapshot=snapshot).delete()

    items = Item.objects.all()

    for item in items:
        # Get previous ending as beginning
        try:
            prev_snapshot = DailySnapshot.objects.filter(date__lt=snapshot_date).latest('date')
            prev_item = DailyItemSnapshot.objects.get(snapshot=prev_snapshot, item=item)
            beginning = prev_item.ending_quantity
        except:
            beginning = item.initial_stock or 0

        # Get today's movements ONLY
        stock_in = StockMovement.objects.filter(
            item=item,
            reason="add",
            created_at__date=snapshot_date
        ).aggregate(total=Sum('quantity'))['total'] or 0

        stock_out = StockMovement.objects.filter(
            item=item,
            reason="remove",
            created_at__date=snapshot_date
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