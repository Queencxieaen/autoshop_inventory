from .models import DailySnapshot, DailyItemSnapshot, Item

def create_snapshot(target_date):
    snapshot, created = DailySnapshot.objects.get_or_create(date=target_date)
    
    # Find previous snapshot
    previous_snapshot = DailySnapshot.objects.filter(date__lt=target_date).order_by('-date').first()
    previous_items = {}
    if previous_snapshot:
        previous_items = {di.item.id: di.ending_quantity for di in DailyItemSnapshot.objects.filter(snapshot=previous_snapshot)}
    
    for item in Item.objects.all():
        beginning = previous_items.get(item.id, item.quantity)  # Use previous ending, or current quantity if no previous
        DailyItemSnapshot.objects.get_or_create(
            snapshot=snapshot,
            item=item,
            defaults={
                'beginning_quantity': beginning,
                'stock_in': 0,
                'stock_out': 0,
                'ending_quantity': beginning,
            }
        )
    return snapshot