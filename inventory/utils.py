# utils.py (or inside views.py)
from datetime import timedelta
from django.utils import timezone
from .models import DailySnapshot, DailyItemSnapshot, Item

def create_snapshot(snapshot_date=None):
    if not snapshot_date:
        snapshot_date = timezone.localdate()

    snapshot, created = DailySnapshot.objects.get_or_create(date=snapshot_date)

    yesterday = snapshot_date - timedelta(days=1)
    prev_snapshot = DailySnapshot.objects.filter(date=yesterday).first()

    existing_items = set(DailyItemSnapshot.objects.filter(snapshot=snapshot).values_list('item_id', flat=True))
    all_items = Item.objects.all()

    daily_snapshots = []
    for item in all_items:
        if item.id in existing_items:
            continue

        beginning_qty = 0
        if prev_snapshot:
            prev_item = DailyItemSnapshot.objects.filter(snapshot=prev_snapshot, item=item).first()
            beginning_qty = prev_item.ending_quantity if prev_item else item.quantity
        else:
            beginning_qty = item.quantity

        daily_snapshots.append(DailyItemSnapshot(
            snapshot=snapshot,
            item=item,
            beginning_quantity=beginning_qty,
            stock_in=0,
            stock_out=0,
            ending_quantity=beginning_qty
        ))

    if daily_snapshots:
        DailyItemSnapshot.objects.bulk_create(daily_snapshots)

    return snapshot