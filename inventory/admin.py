from django.contrib import admin
from .models import Item, Category, StockMovement, ShopSettings, DailySnapshot, DailyItemSnapshot


admin.site.register(DailySnapshot)


admin.site.register(DailyItemSnapshot)

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'quantity', 'price', 'category')
    search_fields = ('name',)
    list_filter = ('category',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('item', 'reason', 'quantity', 'date', 'user')
    list_filter = ('reason', 'date')
    search_fields = ('item__name',)

@admin.register(ShopSettings)
class ShopSettingsAdmin(admin.ModelAdmin):
    list_display = ('shop_name', 'user')