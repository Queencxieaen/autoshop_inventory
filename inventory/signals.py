# signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import StockMovement, DailySnapshot, DailyItemSnapshot, Item

@receiver(post_save, sender=StockMovement)
def update_daily_snapshot(sender, instance, created, **kwargs):
    if not created:
        return  # only new stock movements

    movement_date = instance.date.date()  # use actual movement date

    # Get or create the snapshot for that date
    snapshot, _ = DailySnapshot.objects.get_or_create(date=movement_date)

    # Get or create the DailyItemSnapshot
    snapshot_item, created_item = DailyItemSnapshot.objects.get_or_create(
        snapshot=snapshot,
        item=instance.item,
        defaults={
            'beginning_quantity': instance.item.quantity - instance.quantity if instance.reason == "add" else instance.item.quantity + instance.quantity,
            'stock_in': 0,
            'stock_out': 0,
            'ending_quantity': instance.item.quantity
        }
    )

    # Update stock_in or stock_out
    if not created_item:
        if instance.reason == "add":
            snapshot_item.stock_in += instance.quantity
        elif instance.reason in ["remove", "adjust"]:
            snapshot_item.stock_out += instance.quantity

    snapshot_item.ending_quantity = instance.item.quantity
    snapshot_item.save()