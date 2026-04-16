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

        # =====================================================
        # FIX 1: STRICT CHAINED HISTORY (no fake carryover)
        # =====================================================
        last_record = (
            DailyItemSnapshot.objects
            .filter(item=item, snapshot__date__lt=snapshot_date)
            .order_by('-snapshot__date')
            .first()
        )

        # If no previous day snapshot → NEW ITEM STATE
        beginning = last_record.ending_quantity if last_record else 0

        # =====================================================
        # FIX 2: ONLY TODAY'S MOVEMENTS
        # =====================================================
        stock_in = StockMovement.objects.filter(
            item=item,
            reason="add",
            date__range=(start, end)
        ).aggregate(total=Sum('quantity'))['total'] or 0

        stock_out = StockMovement.objects.filter(
            item=item,
            reason="remove",
            date__range=(start, end)
        ).aggregate(total=Sum('quantity'))['total'] or 0

        # =====================================================
        # FIX 3: ENDING = TRUE LOGIC
        # =====================================================
        ending = beginning + stock_in - stock_out

        # =====================================================
        # FIX 4: SAVE SNAPSHOT
        # =====================================================
        DailyItemSnapshot.objects.update_or_create(
            snapshot=snapshot,
            item=item,
            defaults={
                "beginning_quantity": beginning,
                "stock_in": stock_in,
                "stock_out": stock_out,
                "ending_quantity": ending
            }
        )

    return snapshot


def ensure_daily_snapshots():
    today = date.today()

    DailySnapshot.objects.get_or_create(date=today)

    create_snapshot(today)

    return True