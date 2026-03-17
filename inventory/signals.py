from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import ShopSettings, StockMovement, DailySnapshot, DailyItemSnapshot

# -------------------------
# Create ShopSettings for new users
# -------------------------
@receiver(post_save, sender=User)
def create_shop_settings(sender, instance, created, **kwargs):
    if created:
        ShopSettings.objects.create(user=instance)


# -------------------------
# Update DailyItemSnapshot when StockMovement is created
# -------------------------
@receiver(post_save, sender=StockMovement)
def update_daily_snapshot(sender, instance, created, **kwargs):
    if not created:
        return

    # ✅ Use the actual movement date
    movement_date = instance.date.date()

    # Get or create the snapshot for that date
    snapshot, _ = DailySnapshot.objects.get_or_create(date=movement_date)

    # Get or create the snapshot item
    snapshot_item, _ = DailyItemSnapshot.objects.get_or_create(
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
    if instance.reason == "add":
        snapshot_item.stock_in += instance.quantity
    elif instance.reason in ["remove", "adjust"]:
        snapshot_item.stock_out += instance.quantity

    # Always update ending quantity
    snapshot_item.ending_quantity = instance.item.quantity
    snapshot_item.save()