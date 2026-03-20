from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import ShopSettings


@receiver(post_save, sender=User)
def create_shop_settings(sender, instance, created, **kwargs):
    if created:
        ShopSettings.objects.get_or_create(user=instance)