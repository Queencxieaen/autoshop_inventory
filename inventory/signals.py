from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import StockMovement, DailySnapshot, DailyItemSnapshot


@receiver(post_save, sender=StockMovement)
def update_daily_snapshot(sender, instance, created, **kwargs):
    if not created:
        return

    today = timezone.localdate()
    item = instance.item

    snapshot, _ = DailySnapshot.objects.get_or_create(date=today)

    snapshot_item, _ = DailyItemSnapshot.objects.get_or_create(
        snapshot=snapshot,
        item=item,
        defaults={
            'beginning_quantity': item.quantity,
            'stock_in': 0,
            'stock_out': 0,
            'ending_quantity': item.quantity
        }
    )

    if instance.reason == "add":
        snapshot_item.stock_in += instance.quantity
    elif instance.reason in ["remove", "adjust"]:
        snapshot_item.stock_out += instance.quantity

    snapshot_item.ending_quantity = item.quantity
    snapshot_item.save()