from django.contrib import admin
from .models import Item, Category, StockMovement, ShopSettings, DailySnapshot, DailyItemSnapshot

# Register these directly
admin.site.register(DailySnapshot)
admin.site.register(DailyItemSnapshot)

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    # This now shows the Compatible Units column in your list view
    list_display = ('name', 'quantity', 'price', 'category', 'compatible_units')
    
    # This is the most important change: 
    # It tells the search bar to look inside 'compatible_units' too!
    search_fields = ('name', 'compatible_units')
    
    list_filter = ('category',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('item', 'reason', 'quantity', 'date', 'user')
    list_filter = ('reason', 'date')
    
    # This allows searching movements by item name OR the car it fits
    search_fields = ('item__name', 'item__compatible_units')

@admin.register(ShopSettings)
class ShopSettingsAdmin(admin.ModelAdmin):
    list_display = ('shop_name', 'user')
