import csv
import logging
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import re
from django.template.loader import render_to_string

from django.conf import settings
from .models import PasswordResetOTP
from django.contrib.auth.models import User
import random

from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.db.models.functions import ExtractYear, ExtractMonth
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.utils.dateparse import parse_date

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors, pagesizes
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from .models import Item, Category, StockMovement, ShopSettings, DailySnapshot, DailyItemSnapshot
from .forms import ItemForm, CategoryForm, ShopSettingsForm, AdjustStockForm

from django.db.models import Count
from django.core.mail import send_mail
from .utils import create_snapshot
# ===========================
# AUTH
# ===========================
def user_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        remember = request.POST.get("remember")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Remember me: if not checked, session expires on close
            if not remember:
                request.session.set_expiry(0)

            messages.success(request, f"Welcome back, {user.username}!")

            # Handle next parameter
            next_url = request.GET.get('next') or 'dashboard'
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'inventory/login.html')

def user_logout(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('login')


# ===========================
# DASHBOARD
# ===========================
@login_required
def dashboard(request):
    today = timezone.localdate()

    create_snapshot(today)

    total_items = Item.objects.aggregate(total=Sum('quantity'))['total'] or 0
    low_stock = Item.objects.filter(quantity__lte=5).count()
    well_stock = Item.objects.filter(quantity__gt=10).count()
    total_value = sum(item.price * item.quantity for item in Item.objects.all())

    stock_distribution = Category.objects.annotate(count=Count('item'))

    return render(request, 'inventory/dashboard.html', {
        'total_items': total_items,
        'low_stock': low_stock,
        'well_stock': well_stock,
        'total_value': total_value,
        'stock_distribution': stock_distribution,
    })

# ===========================
# EDIT PROFILE (kept)
# ===========================
@login_required
def edit_profile(request):
    return render(request, 'inventory/edit_profile.html')


# ===========================
# SETTINGS
# ===========================
@login_required
def settings_page(request):
    settings_instance, _ = ShopSettings.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ShopSettingsForm(request.POST, request.FILES, instance=settings_instance)

        # Update user fields
        username = request.POST.get("username")
        email = request.POST.get("email")
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        if new_password:
            if not request.user.check_password(current_password):
                messages.error(request, "Current password is incorrect.")
            elif new_password != confirm_password:
                messages.error(request, "New passwords do not match.")
            else:
                request.user.set_password(new_password)
                request.user.save()
                messages.success(request, "Password updated successfully!")

        if username:
            request.user.username = username
        if email:
            request.user.email = email
        request.user.save()

        if form.is_valid():
            form.save()
            messages.success(request, "Settings updated successfully!")
            return redirect('settings_page')
        else:
            messages.error(request, "Please correct the errors below.")
    
    else:
        form = ShopSettingsForm(instance=settings_instance)

    return render(request, "inventory/settings.html", {
        "form": form,
        "username": request.user.username,
        "email": request.user.email,
        "profile_image": settings_instance.profile_image
    })


# ===========================
# ITEMS
# ===========================
@login_required
def all_items(request):
    query = request.GET.get("q", "")
    items = Item.objects.all()
    if query:
        items = items.filter(name__icontains=query)

    return render(request, "inventory/all_items.html", {
        "items": items,
        "total_items": items.count(),
        "low_stock": items.filter(quantity__lte=5).count(),
        "total_value": sum(item.price * item.quantity for item in items),
        "query": query,
    })


@login_required
def add_item(request):
    form = ItemForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.name = form.cleaned_data['name'].strip()

        # DO NOT set quantity here
        item.save()

        messages.success(request, f"Item '{item.name}' added successfully!")
        return redirect("all_items")

    return render(request, "inventory/add_item.html", {"form": form})

@login_required
def edit_item(request, pk):
    item = get_object_or_404(Item, pk=pk)
    form = ItemForm(request.POST or None, instance=item)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Item updated successfully!")
        return redirect('all_items')

    return render(request, 'inventory/item_form.html', {'form': form, 'title': 'Edit Item'})


@login_required
def delete_item(request, pk):
    item = get_object_or_404(Item, pk=pk)

    if request.method == 'POST':
        item.delete()
        messages.success(request, "Item deleted successfully!")
        return redirect('all_items')

    return render(request, 'inventory/delete_confirm.html', {'item': item})


# ===========================
# CATEGORY
# ===========================
@login_required
def categories(request):
    query = request.GET.get('q', '')
    categories = Category.objects.all()

    if query:
        categories = categories.filter(name__icontains=query)

    return render(request, 'inventory/categories.html', {
        'categories': categories,
        'total_categories': Category.objects.count(),
        'query': query,
    })


@login_required
def add_category(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()  # save and capture object
            messages.success(request, f"Category '{category.name}' was added successfully!")
            return redirect('categories')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CategoryForm()

    return render(request, 'inventory/add_category.html', {'form': form})


@login_required
def edit_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, instance=category)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Category updated successfully!")
        return redirect('categories')

    return render(request, 'inventory/category_form.html', {'form': form})


@login_required
def delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk)

    if request.method == "POST":
        category.delete()
        messages.success(request, f'Category {category.name} deleted.')
        return redirect('categories')

    return redirect('categories')


# ===========================
# STOCK
# ===========================
@login_required
def low_stock_page(request):
    shop = ShopSettings.objects.first()
    limit = shop.low_stock_limit if shop else 5

    low_stock_items = Item.objects.filter(quantity__lte=limit)

    return render(request, 'inventory/low_stock.html', {
        'low_stock_items': low_stock_items,
        'limit': limit
    })


@login_required
def adjust_stock(request, pk=None):
    """
    Adjust stock quantities for items and update daily snapshots.
    Prevents stock out below 0 or current item quantity.
    """
    today = timezone.localdate()
    today_snapshot = create_snapshot(today)

    items = Item.objects.all().order_by('name')
    recent_movements = StockMovement.objects.select_related('item', 'user').order_by('-date')[:10]
    today_snapshot_items = DailyItemSnapshot.objects.filter(snapshot=today_snapshot)

    if request.method == 'POST':
        item_id = request.POST.get('item')
        reason = request.POST.get('reason')
        quantity_str = request.POST.get('quantity', '0')

        # Convert quantity safely
        try:
            quantity = int(quantity_str)
        except (TypeError, ValueError):
            quantity = 0

        if item_id and reason in ['add', 'remove'] and quantity > 0:
            item = get_object_or_404(Item, pk=item_id)

            # Prevent stock out below 0
            if reason == 'remove' and quantity > item.quantity:
                messages.error(
                    request,
                    f"Cannot remove {quantity} units. '{item.name}' only has {item.quantity} in stock."
                )
                return redirect('adjust_stock')

            # Update item quantity
            if reason == 'add':
                item.quantity += quantity
            else:  # remove
                item.quantity -= quantity

            item.save()

            # Update or create daily snapshot
            snapshot_item, created = DailyItemSnapshot.objects.get_or_create(
                snapshot=today_snapshot,
                item=item,
                defaults={
                    "beginning_quantity": item.quantity - quantity if reason == 'add' else item.quantity + quantity,
                    "stock_in": 0,
                    "stock_out": 0,
                    "ending_quantity": item.quantity,
                }
            )

            if reason == 'add':
                snapshot_item.stock_in += quantity
            else:
                snapshot_item.stock_out += quantity

            snapshot_item.ending_quantity = snapshot_item.beginning_quantity + snapshot_item.stock_in - snapshot_item.stock_out
            snapshot_item.save()

            # Record stock movement
            StockMovement.objects.create(
                item=item,
                quantity=quantity,
                reason=reason,
                user=request.user
            )

            messages.success(request, f"Stock for '{item.name}' updated successfully.")
            return redirect('adjust_stock')
        else:
            messages.error(request, "Invalid input. Please check your item, reason, and quantity.")

    # Shop name for header (fallback if user has no shop settings)
    shop_settings = getattr(request.user, 'shopsettings', None)
    shop_name = shop_settings.shop_name if shop_settings else 'My Shop'

    context = {
        "items": items,
        "selected_item": None,
        "movements": recent_movements,
        "today_snapshot": today_snapshot_items,
        "shop_name": shop_name,
    }
    return render(request, "inventory/adjust_stock.html", context)
# ===========================
# REPORTS
# ===========================

@login_required
def reports_home(request):
    from .utils import create_snapshot

    years = DailySnapshot.objects.dates('date', 'year', order='DESC')

    today = timezone.localdate()

    # Lazy snapshot creation: only create if not exists
    DailySnapshot.objects.filter(date=today).first() or create_snapshot(today)

    return render(request, 'inventory/reports_home.html', {
        'years': years,
        'today': today
    })


@login_required
def daily_detail(request, year, month, day):
    from datetime import date
    from inventory.utils import create_snapshot

    date_obj = date(year, month, day)

    # Ensure snapshot exists (safe rebuild)
    snapshot = create_snapshot(date_obj)

    items = DailyItemSnapshot.objects.filter(
        snapshot=snapshot
    ).select_related('item__category')

    grouped = {}
    for i in items:
        category = i.item.category.name if i.item.category else "Uncategorized"
        grouped.setdefault(category, []).append(i)

    shop_settings = getattr(request.user, 'shopsettings', None)

    return render(request, 'inventory/daily_detail.html', {
        'snapshot': snapshot,
        'grouped': grouped,
        'shop_name': shop_settings.shop_name if shop_settings else "My Shop",
    })
    
@login_required
def monthly_detail(request):
    snapshots = DailySnapshot.objects.all().order_by('date')
    year = request.GET.get('year')
    month = request.GET.get('month')

    if year and month:
        year = int(year)
        month = int(month)
        # Filter snapshots by selected month/year
        snapshots = snapshots.filter(date__year=year, date__month=month)

        # Ensure each snapshot includes all items
        for snapshot in snapshots:
            create_snapshot(snapshot.date)

    context = {
        'snapshots': snapshots,
        'year': year,
        'month': month,
    }
    return render(request, 'inventory/monthly_detail.html', context)


    
@login_required
def delete_daily_report(request, date_str):
    if request.method != "POST":
        return redirect('reports_home')

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        DailySnapshot.objects.filter(date=date_obj).delete()
        messages.success(request, "Daily report deleted.")
    except:
        messages.error(request, "Report not found.")

    return redirect('monthly_detail', year=date_obj.year, month=date_obj.month)


@login_required
def delete_selected_reports(request, year, month):
    if request.method != "POST":
        return redirect('monthly_detail', year=year, month=month)

    selected_dates = request.POST.get('selected_dates', '')
    dates = selected_dates.split(',') if selected_dates else []

    for date_str in dates:
        DailySnapshot.objects.filter(date=date_str).delete()

    messages.success(request, "Selected reports deleted.")
    return redirect('monthly_detail', year=year, month=month)


# ===========================
# EXPORTS
# ===========================

@login_required
def export_selected_days_pdf(request, year, month):
    from weasyprint import HTML

    selected_dates = request.POST.get('selected_dates')
    date_obj = parse_date(selected_dates)

    snapshot = DailySnapshot.objects.filter(date=date_obj).first()

    if not snapshot:
        return HttpResponse("No data found.")

    items = DailyItemSnapshot.objects.filter(snapshot=snapshot).select_related('item__category')

    grouped = {}
    for item in items:
        category_name = item.item.category.name if item.item.category else "Uncategorized"
        grouped.setdefault(category_name, []).append(item)

    shop = ShopSettings.objects.first()
    shop_name = shop.shop_name if shop else "Inventory System"

    html_string = render_to_string(
        "inventory/pdf/daily_detail_pdf.html",   # ✅ FIXED
        {
            "snapshot": snapshot,
            "grouped": grouped,
            "shop_name": shop_name,
        }
    )

    pdf_file = HTML(
        string=html_string,
        base_url=request.build_absolute_uri()
    ).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Inventory_{snapshot.date}.pdf"'

    return response

@login_required
def monthly_summary(request, year, month):

    records = DailyItemSnapshot.objects.filter(
        snapshot__date__year=year,
        snapshot__date__month=month
    ).select_related("item__category")

    # GROUP BY CATEGORY -> ITEM
    summary = {}

    for record in records:
        category = record.item.category.name if record.item.category else "Uncategorized"
        item_name = record.item.name

        if category not in summary:
            summary[category] = {}

        if item_name not in summary[category]:
            summary[category][item_name] = {
                "beginning": record.beginning_quantity,
                "stock_in": 0,
                "stock_out": 0,
                "ending": 0,
            }

        summary[category][item_name]["stock_in"] += record.stock_in
        summary[category][item_name]["stock_out"] += record.stock_out

        # CORRECT ENDING CALCULATION
        summary[category][item_name]["ending"] = (
            summary[category][item_name]["beginning"]
            + summary[category][item_name]["stock_in"]
            - summary[category][item_name]["stock_out"]
        )

    month_name = datetime(year, month, 1).strftime("%B")

    return render(request, "inventory/monthly_summary.html", {
        "summary": summary,
        "year": year,
        "month": month,
        "month_name": month_name,
    })


@login_required
def monthly_summary_pdf(request, year, month):
    from weasyprint import HTML
    
    records = DailyItemSnapshot.objects.filter(
        snapshot__date__year=year,
        snapshot__date__month=month
    ).select_related("item__category")

    summary = {}

    # Build summary dict
    for record in records:
        category = record.item.category.name if record.item.category else "Uncategorized"
        item_name = record.item.name

        if category not in summary:
            summary[category] = {}

        if item_name not in summary[category]:
            summary[category][item_name] = {
                "beginning": record.beginning_quantity,
                "stock_in": 0,
                "stock_out": 0,
                "ending": 0,
            }

        # Update stock in/out and ending
        summary[category][item_name]["stock_in"] += record.stock_in
        summary[category][item_name]["stock_out"] += record.stock_out
        summary[category][item_name]["ending"] = (
            summary[category][item_name]["beginning"]
            + summary[category][item_name]["stock_in"]
            - summary[category][item_name]["stock_out"]
        )

    # Compute totals per category (Django-safe key)
    for cat, items in summary.items():
        total = {"beginning": 0, "stock_in": 0, "stock_out": 0, "ending": 0}
        for item, data in items.items():
            total["beginning"] += data["beginning"]
            total["stock_in"] += data["stock_in"]
            total["stock_out"] += data["stock_out"]
            total["ending"] += data["ending"]
        items["totals"] = total  # ✅ key does NOT start with underscore

    shop = ShopSettings.objects.first()
    shop_name = shop.shop_name if shop else "Inventory System"
    month_name = datetime(int(year), int(month), 1).strftime("%B")

    html_string = render_to_string(
        "inventory/pdf/monthly_summary_pdf.html",
        {
            "shop_name": shop_name,
            "month_name": month_name,
            "year": year,
            "summary": summary,
        }
    )

    pdf_file = HTML(
        string=html_string,
        base_url=request.build_absolute_uri()
    ).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Monthly_{month_name}_{year}.pdf"'

    return response

    
@login_required
def weekly_summary(request):
    today = timezone.localdate()

    month_start = today.replace(day=1)
    month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)

    weeks = []

    start = month_start

    while start <= month_end:
        end = start + timedelta(days=6)

        if end > month_end:
            end = month_end

        snapshots = DailySnapshot.objects.filter(date__range=[start, end])
        items = DailyItemSnapshot.objects.filter(snapshot__in=snapshots)

        # Summarize by category -> item
        categories = {}

        for item in items:
            category = item.item.category.name if item.item.category else "Uncategorized"
            name = item.item.name

            if category not in categories:
                categories[category] = {}

            if name not in categories[category]:
                categories[category][name] = {
                    'beginning': 0,
                    'in': 0,
                    'out': 0,
                    'ending': 0
                }

            categories[category][name]['beginning'] += item.beginning_quantity
            categories[category][name]['in'] += item.stock_in
            categories[category][name]['out'] += item.stock_out
            
            categories[category][name]['ending'] = (
                categories[category][name]['beginning']
                + categories[category][name]['in']
                - categories[category][name]['out']
            )

        weeks.append({
            'label': f"Week: {start.strftime('%B %d, %Y')} - {end.strftime('%B %d, %Y')}",
            'start': start,
            'end': end,
            'categories': categories
        })

        start = end + timedelta(days=1)

    return render(request, 'inventory/weekly_summary.html', {
        'weeks': weeks,
        'month_name': today.strftime('%B'),
        'year': today.year
    })

@login_required
def weekly_summary_pdf(request):
    from weasyprint import HTML

    selected_weeks = request.POST.getlist("selected_weeks")

    if not selected_weeks:
        return HttpResponse("No weeks selected.")

    weeks_data = []

    for week_range in selected_weeks:
        start_str, end_str = week_range.split("|")
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()

        snapshots = DailySnapshot.objects.filter(
            date__range=[start_date, end_date]
        )

        items = DailyItemSnapshot.objects.filter(
            snapshot__in=snapshots
        ).select_related("item__category")

        categories = {}

        for record in items:
            category_name = record.item.category.name if record.item.category else "Uncategorized"
            item_name = record.item.name

            if category_name not in categories:
                categories[category_name] = {}

            if item_name not in categories[category_name]:
                categories[category_name][item_name] = {
                    "beginning": 0,
                    "in": 0,
                    "out": 0,
                    "ending": 0,
                }

            categories[category_name][item_name]["beginning"] += record.beginning_quantity
            categories[category_name][item_name]["in"] += record.stock_in
            categories[category_name][item_name]["out"] += record.stock_out
            categories[category_name][item_name]["ending"] += record.ending_quantity

        weeks_data.append({
            "label": f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}",
            "categories": categories
        })

    shop = ShopSettings.objects.first()
    shop_name = shop.shop_name if shop else "Inventory System"
    logo_url = shop.profile_image.url if shop and shop.profile_image else None

    # ✅ Fix: added comma between "shop_name" and "logo_url"
    html_string = render_to_string(
        "inventory/pdf/weekly_summary_pdf.html",
        {
            "weeks": weeks_data,
            "shop_name": shop_name,
            "logo_url": logo_url
        }
    )

    pdf_file = HTML(
        string=html_string,
        base_url=request.build_absolute_uri()
    ).write_pdf()

    # Build filename label
    filename_parts = []

    for week_range in selected_weeks:
        start_str, end_str = week_range.split("|")
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()

        label = f"{start_date.strftime('%B %d')}-{end_date.strftime('%d %Y')}"
        filename_parts.append(label)

    filename_label = " & ".join(filename_parts)
    safe_filename = f"Weekly_report_{filename_label}.pdf"

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{safe_filename}"'

    return response
    
@login_required
def custom_summary(request):

    summary = []
    start_date = None
    end_date = None

    if request.method == "POST":
        start_date = parse_date(request.POST.get("start_date"))
        end_date = parse_date(request.POST.get("end_date"))

        if start_date and end_date:

            records = DailyItemSnapshot.objects.filter(
                snapshot__date__range=[start_date, end_date]
            ).select_related("item").order_by("snapshot__date")

            temp = {}

            for record in records:
                item_id = record.item.id

                if item_id not in temp:
                    temp[item_id] = {
                        "item_name": record.item.name,
                        "beginning": record.beginning_quantity,
                        "stock_in": 0,
                        "stock_out": 0,
                        "ending": 0,
                    }

                temp[item_id]["stock_in"] += record.stock_in
                temp[item_id]["stock_out"] += record.stock_out
                temp[item_id]["ending"] = record.ending_quantity

            summary = temp.values()

    return render(request, "inventory/custom_summary.html", {
        "summary": summary,
        "start_date": start_date,
        "end_date": end_date,
    })
# ===========================
# AJAX
# ===========================
@csrf_exempt
@require_POST
@login_required
def ajax_stock_movement(request):
    """
    Adjust stock via AJAX and update daily snapshot.
    """
    item_id = request.POST.get('item_id')
    quantity_str = request.POST.get('quantity', '0')
    reason = request.POST.get('reason', 'adjust')  # default adjust

    # Validate parameters
    if not item_id:
        return JsonResponse({'success': False, 'error': 'Item ID not provided.'})
    try:
        quantity = int(quantity_str)
        if quantity <= 0:
            raise ValueError
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Quantity must be a positive integer.'})

    if reason not in ['add', 'remove', 'adjust']:
        return JsonResponse({'success': False, 'error': 'Invalid reason.'})

    try:
        item = Item.objects.get(pk=item_id)

        # Get or create today's snapshot
        today = timezone.localdate()
        snapshot = create_snapshot(today)

        # Get or create snapshot record for this item
        snapshot_item, _ = DailyItemSnapshot.objects.get_or_create(
            snapshot=snapshot,
            item=item,
            defaults={
                'beginning_quantity': item.quantity if reason != 'add' else item.quantity - quantity,
                'stock_in': 0,
                'stock_out': 0,
                'ending_quantity': item.quantity,
            }
        )

        # Apply stock change
        if reason == 'add':
            item.quantity += quantity
            snapshot_item.stock_in += quantity
        else:  # remove or adjust
            if quantity > item.quantity:
                return JsonResponse({'success': False, 'error': 'Stock out exceeds available quantity.'})
            item.quantity -= quantity
            snapshot_item.stock_out += quantity

        # Prevent negative stock
        if item.quantity < 0:
            item.quantity = 0

        # Save updates
        item.save()
        snapshot_item.ending_quantity = snapshot_item.beginning_quantity + snapshot_item.stock_in - snapshot_item.stock_out
        snapshot_item.save()

        # Record stock movement
        StockMovement.objects.create(
            item=item,
            quantity=quantity,
            reason=reason,
            user=request.user
        )

        return JsonResponse({'success': True, 'new_quantity': item.quantity})

    except Item.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Item not found.'})
        
@csrf_exempt
@require_GET
def get_item_quantity(request):
    item_id = request.GET.get('item_id')
    if not item_id:
        return JsonResponse({'error': 'Item ID not provided'}, status=400)

    try:
        item = Item.objects.get(id=item_id)
        return JsonResponse({'quantity': item.quantity})
    except Item.DoesNotExist:
        return JsonResponse({'error': 'Item not found'}, status=404)


def test_msg(request):
    messages.success(request, "Test message works!")
    return render(request, "inventory/dashboard.html")


# -------------------
# 1️⃣ Request OTP
# -------------------
def send_otp(request):
    if request.method == "POST":
        email = request.POST.get("email").strip()
        if not email:
            messages.error(request, "Please enter your email.")
            return redirect("send_otp")

        user = User.objects.filter(email=email).first()
        if not user:
            messages.error(request, "Email not found.")
            return redirect("send_otp")

        # Expire old OTPs
        PasswordResetOTP.objects.filter(user=user, expired=False).update(expired=True)

        # Generate new OTP
        code = str(random.randint(100000, 999999))
        PasswordResetOTP.objects.create(user=user, code=code, expired=False)

        # Send email
        try:
            send_mail(
                "Password Reset OTP",
                f"Your OTP code is: {code}\nIt expires in 10 minutes.",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except Exception as e:
            print("EMAIL ERROR:", e)
            messages.error(request, "Failed to send OTP. Check server email settings.")
            return redirect("send_otp")

        messages.success(request, "OTP sent to your email.")
        return redirect("verify_otp")

    return render(request, "inventory/otp_request.html")


# -------------------
# 2️⃣ Verify OTP
# -------------------
def verify_otp(request):
    if request.method == "POST":
        code = request.POST.get("code").strip()
        if not code:
            messages.error(request, "Please enter the OTP.")
            return redirect("verify_otp")

        otp = PasswordResetOTP.objects.filter(code=code, expired=False).first()
        if not otp or not otp.is_valid():
            messages.error(request, "Invalid or expired OTP. Please request a new one.")
            return redirect("send_otp")

        # Expire OTP after successful verification
        otp.expired = True
        otp.save()

        # Store user id in session
        request.session['reset_user_id'] = otp.user.id
        messages.success(request, "OTP verified! You can now set a new password.")
        return redirect("set_new_password")

    return render(request, "inventory/otp_verify.html")


# -------------------
# 3️⃣ Set New Password
# -------------------
def set_new_password(request):
    user_id = request.session.get('reset_user_id')
    if not user_id:
        messages.error(request, "Session expired. Please request a new OTP.")
        return redirect("send_otp")

    if request.method == "POST":
        password = request.POST.get("password").strip()
        confirm_password = request.POST.get("confirm_password").strip()

        if not password or not confirm_password:
            messages.error(request, "Please fill out both password fields.")
            return redirect("set_new_password")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("set_new_password")

        # Update user password
        try:
            user = User.objects.get(id=user_id)
            user.set_password(password)
            user.save()
        except User.DoesNotExist:
            messages.error(request, "User not found. Please try again.")
            return redirect("send_otp")

        # Clear session
        request.session.pop('reset_user_id', None)
        messages.success(request, "Password updated successfully! You can now log in.")
        return redirect("login")

    return render(request, "inventory/set_new_password.html")