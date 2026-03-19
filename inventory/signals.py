from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import StockMovement, DailySnapshot, DailyItemSnapshot

@receiver(post_save, sender=StockMovement)
def update_daily_snapshot(sender, instance, created, **kwargs):
    if not created:
        return  # only new stock movements

    movement_date = instance.date.date()

    # 1️⃣ Get or create DailySnapshot for the movement date
    snapshot, _ = DailySnapshot.objects.get_or_create(date=movement_date)

    # 2️⃣ Get or create DailyItemSnapshot
    snapshot_item, created_item = DailyItemSnapshot.objects.get_or_create(
        snapshot=snapshot,
        item=instance.item,
        defaults={
            'beginning_quantity': instance.item.quantity - instance.quantity if instance.reason == 'add' else instance.item.quantity + instance.quantity,
            'stock_in': 0,
            'stock_out': 0,
            'ending_quantity': instance.item.quantity
        }
    )

    # 3️⃣ Update stock_in / stock_out if already exists
    if not created_item:
        if instance.reason == 'add':
            snapshot_item.stock_in += instance.quantity
        elif instance.reason in ['remove', 'adjust']:
            snapshot_item.stock_out += instance.quantity

    # 4️⃣ Always update ending_quantity
    snapshot_item.ending_quantity = instance.item.quantity
    snapshot_item.save()