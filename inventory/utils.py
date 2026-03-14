def create_snapshot(target_date):
    snapshot, created = DailySnapshot.objects.get_or_create(date=target_date)

    previous_snapshot = DailySnapshot.objects.filter(
        date__lt=target_date
    ).order_by('-date').first()

    # Rebuild snapshot items (fresh calculation)
    DailyItemSnapshot.objects.filter(snapshot=snapshot).delete()

    for item in Item.objects.all():

        # BEGINNING (from previous day)
        if previous_snapshot:
            previous_item = DailyItemSnapshot.objects.filter(
                snapshot=previous_snapshot,
                item=item
            ).first()
            beginning_qty = previous_item.ending_quantity if previous_item else 0
        else:
            beginning_qty = 0

        # STOCK IN (today)
        stock_in = StockMovement.objects.filter(
            item=item,
            reason='add',
            date__date=target_date
        ).aggregate(total=Sum('quantity'))['total'] or 0

        # STOCK OUT (today)
        stock_out = StockMovement.objects.filter(
            item=item,
            reason='remove',
            date__date=target_date
        ).aggregate(total=Sum('quantity'))['total'] or 0

        # ENDING
        ending_qty = beginning_qty + stock_in - stock_out

        # CREATE snapshot row
        DailyItemSnapshot.objects.create(
            snapshot=snapshot,
            item=item,
            beginning_quantity=beginning_qty,
            stock_in=stock_in,
            stock_out=stock_out,
            ending_quantity=ending_qty
        )

    return snapshot