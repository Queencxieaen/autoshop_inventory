from .models import DailySnapshot, DailyItemSnapshot, Item
from django.utils import timezone

def create_snapshot(target_date):
    snapshot, created = DailySnapshot.objects.get_or_create(date=target_date)
    items = Item.objects.all()
    for item in items:
        DailyItemSnapshot.objects.get_or_create(
            snapshot=snapshot,
            item=item,
            defaults={
                'beginning_quantity': item.quantity,
                'stock_in': 0,
                'stock_out': 0,
                'ending_quantity': item.quantity,
            }
        )
    return snapshot