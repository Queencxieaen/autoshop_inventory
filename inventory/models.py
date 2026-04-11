from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.db import transaction

# =========================
# Shop Settings
# =========================
class ShopSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    shop_name = models.CharField(max_length=100, default="Autosthetics Car Care")
    address = models.CharField(max_length=200, blank=True)
    contact = models.CharField(max_length=50, blank=True)
    low_stock_limit = models.IntegerField(default=5)

    theme = models.CharField(
        max_length=20,
        choices=[("gold", "Gold"), ("orange", "Orange"), ("light", "Light"), ("dark", "Dark")],
        default="gold"
    )

    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    last_backup = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.shop_name


# =========================
# Category
# =========================
class Category(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


# =========================
# Item
# =========================
UNIT_CHOICES = [
    ('pcs', 'Pieces'), ('kg', 'Kilogram'), ('g', 'Gram'),
    ('ltr', 'Liter'), ('ml', 'Milliliter'), ('box', 'Box'),
    ('set', 'Set'), ('pair', 'Pair'), ('pack', 'Pack'),
    ('bag', 'Bag'), ('can', 'Can'), ('bottle', 'Bottle'), ('unit', 'Unit'),
]

class Item(models.Model):
    name = models.CharField(max_length=255, unique=True)
    quantity = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='pcs')
    
    # --- NEW FIELD ADDED BELOW ---
    # This allows you to tag parts with car models (e.g. Foton Gratour, Toyota Vios)
    compatible_units = models.TextField(blank=True, null=True, help_text="List cars this fits")
    # -----------------------------

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# =========================
# Stock Movements
# =========================
class StockMovement(models.Model):
    REASON_CHOICES = [('add', 'Stock In'), ('remove', 'Stock Out'), ('adjust', 'Adjustment')]
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.IntegerField() 
    reason = models.CharField(max_length=10, choices=REASON_CHOICES)
    date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    remarks = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.item.name} | {self.get_reason_display()} | {self.quantity}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        if is_new:
            with transaction.atomic():
                # 1. Update the Item Balance strictly
                if self.reason == 'add':
                    self.item.quantity += self.quantity
                elif self.reason == 'remove':
                    self.item.quantity -= self.quantity
                elif self.reason == 'adjust':
                    self.item.quantity = self.quantity
                
                self.item.save()

                # 2. Trigger the Utility to rebuild the Daily Report correctly
                # This ensures the math (Beginning + In - Out) is consistent everywhere.
                from .utils import create_snapshot
                create_snapshot(timezone.localdate())

        super().save(*args, **kwargs)


# =========================
# Daily Snapshots
# =========================
class DailySnapshot(models.Model):
    date = models.DateField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.date)


class DailyItemSnapshot(models.Model):
    snapshot = models.ForeignKey(DailySnapshot, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    beginning_quantity = models.IntegerField()
    stock_in = models.IntegerField()
    stock_out = models.IntegerField()
    ending_quantity = models.IntegerField()

    def __str__(self):
        return f"{self.item.name} - {self.snapshot.date}"


# =========================
# Password Reset OTP
# =========================
class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expired = models.BooleanField(default=False)

    def is_valid(self):
        """Valid for 10 minutes"""
        return not self.expired and timezone.now() <= self.created_at + timedelta(minutes=10)

    def __str__(self):
        return f"{self.user.username} - {self.code}"
