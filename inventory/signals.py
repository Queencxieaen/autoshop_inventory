from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

from .models import ShopSettings, StockMovement, DailyItemSnapshot
from .utils import create_snapshot


@receiver(post_save, sender=User)
def create_shop_settings(sender, instance, created, **kwargs):
    if created:
        ShopSettings.objects.create(user=instance)


@receiver(post_save, sender=StockMovement)
def update_daily_snapshot(sender, instance, created, **kwargs):
    if not created:
        return

    # Ensure snapshot exists
    snapshot = create_snapshot(instance.date.date())

    # Get the item snapshot
    snapshot_item = DailyItemSnapshot.objects.get(
        snapshot=snapshot,
        item=instance.item
    )

    # Update stock values
    if instance.reason == "add":
        snapshot_item.stock_in += instance.quantity
    else:
        snapshot_item.stock_out += instance.quantity

    # Recalculate ending
    snapshot_item.ending_quantity = (
        snapshot_item.beginning_quantity
        + snapshot_item.stock_in
        - snapshot_item.stock_out
    )

    snapshot_item.save()