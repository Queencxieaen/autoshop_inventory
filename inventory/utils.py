from .models import DailySnapshot, DailyItemSnapshot, Item
from django.utils import timezone

def create_snapshot(target_date):
    snapshot, _ = DailySnapshot.objects.get_or_create(date=target_date)
    items = Item.objects.all()

    for item in items:
        daily_item, created = DailyItemSnapshot.objects.get_or_create(
            snapshot=snapshot,
            item=item,
            defaults={
                'beginning_quantity': item.quantity,
                'stock_in': 0,
                'stock_out': 0,
                'ending_quantity': item.quantity,
            }
        )
        if not created:
            # If the DailyItemSnapshot exists but is empty, fill it
            if daily_item.beginning_quantity is None:
                daily_item.beginning_quantity = item.quantity
                daily_item.stock_in = 0
                daily_item.stock_out = 0
                daily_item.ending_quantity = item.quantity
                daily_item.save()

    return snapshot