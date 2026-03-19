
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import StockMovement, DailyItemSnapshot
from .views import create_snapshot

@receiver(post_save, sender=StockMovement)
def update_daily_snapshot(sender, instance, created, **kwargs):
    if not created:
        return

    snapshot = create_snapshot(instance.date.date())
    snapshot_item, _ = DailyItemSnapshot.objects.get_or_create(
        snapshot=snapshot,
        item=instance.item
    )

    # Recalculate stock_in / stock_out for this movement
    if instance.reason == "add":
        snapshot_item.stock_in += instance.quantity
    elif instance.reason in ["remove", "adjust"]:
        snapshot_item.stock_out += instance.quantity

    snapshot_item.ending_quantity = snapshot_item.beginning_quantity + snapshot_item.stock_in - snapshot_item.stock_out
    snapshot_item.save()