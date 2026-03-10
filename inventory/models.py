from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

# =========================
# Shop Settings
# =========================
class ShopSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    shop_name = models.CharField(max_length=100, default="Autosthetics Car Care")
    address = models.CharField(max_length=200, blank=True)
    contact = models.CharField(max_length=50, blank=True)
    low_stock_limit = models.IntegerField(default=5)

    # Appearance
    theme = models.CharField(
        max_length=20,
        choices=[("gold", "Gold"), ("orange", "Orange"), ("light", "Light"), ("dark", "Dark")],
        default="gold"
    )

    # Profile image
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)

    # Backup trigger flag (optional)
    last_backup = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.shop_name

# =========================
# Category
# =========================
class Category(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)  # Optional description

    def __str__(self):
        return self.name

# =========================
# Item
# =========================
UNIT_CHOICES = [
    ('pcs', 'Pieces'),
    ('kg', 'Kilogram'),
    ('g', 'Gram'),
    ('ltr', 'Liter'),
    ('ml', 'Milliliter'),
    ('box', 'Box'),
    ('set', 'Set'),
    ('pair', 'Pair'),
    ('pack', 'Pack'),
    ('bag', 'Bag'),
    ('can', 'Can'),
    ('bottle', 'Bottle'),
    ('unit', 'Unit'),
]

class Item(models.Model):
    name = models.CharField(max_length=255, unique=True)
    quantity = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='pcs')
    created_at = models.DateTimeField(auto_now_add=True)  # ADD THIS

    def __str__(self):
        return self.name


class StockMovement(models.Model):
    REASON_CHOICES = [('add', 'Stock In'), ('remove', 'Stock Out'), ('adjust', 'Adjustment')]
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    reason = models.CharField(max_length=10, choices=REASON_CHOICES)
    date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    remarks = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.item.name} | {self.reason} | {self.quantity}"

# =========================
# Daily Snapshot
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



class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return timezone.now() < self.created_at + timezone.timedelta(minutes=10)