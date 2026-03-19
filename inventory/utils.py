from datetime import timedelta
from django.utils import timezone
from .models import DailySnapshot, DailyItemSnapshot, Item

def create_snapshot(snapshot_date=None):
    if not snapshot_date:
        snapshot_date = timezone.localdate()

    # 1️⃣ Get or create today's snapshot
    snapshot, created = DailySnapshot.objects.get_or_create(date=snapshot_date)

    # 2️⃣ Get yesterday's snapshot
    yesterday = snapshot_date - timedelta(days=1)
    prev_snapshot = DailySnapshot.objects.filter(date=yesterday).first()

    # 3️⃣ Loop through all items
    for item in Item.objects.all():
        # 3a️⃣ Skip if DailyItemSnapshot already exists for today
        if DailyItemSnapshot.objects.filter(snapshot=snapshot, item=item).exists():
            continue

        # 3b️⃣ Determine beginning_quantity
        if prev_snapshot:
            prev_item = DailyItemSnapshot.objects.filter(snapshot=prev_snapshot, item=item).first()
            beginning_qty = prev_item.ending_quantity if prev_item else item.quantity
        else:
            beginning_qty = item.quantity  # first ever snapshot

        # 3c️⃣ Create DailyItemSnapshot
        DailyItemSnapshot.objects.create(
            snapshot=snapshot,
            item=item,
            beginning_quantity=beginning_qty,
            stock_in=0,
            stock_out=0,
            ending_quantity=beginning_qty
        )

    return snapshot