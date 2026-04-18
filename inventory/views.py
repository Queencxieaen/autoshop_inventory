import csv
import logging
from datetime import datetime, date, timedelta
import datetime as dt_module
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import re
from django.template.loader import render_to_string
 
from django.utils.timezone import now, make_aware

from django.conf import settings
from .models import PasswordResetOTP
from django.contrib.auth.models import User
import random

from django.utils import timezone
import calendar
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q, F, Count
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
from weasyprint import HTML
from django.db import transaction

from .models import Item, Category, StockMovement, ShopSettings, DailySnapshot, DailyItemSnapshot
from inventory.utils import ensure_daily_snapshots
from .forms import ItemForm, CategoryForm, ShopSettingsForm, AdjustStockForm

from django.db.models import Count
from django.core.mail import send_mail
from .utils import create_snapshot
# ===========================
# AUTH
# ===========================
def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == "POST":
        username = request.POST.get("user_auth_id")
        password = request.POST.get("user_auth_key")
        remember = request.POST.get("remember")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if not remember:
                request.session.set_expiry(0)
            
            messages.success(request, f"Welcome back, {user.username}!")
            
            # This handles the ?next=/dashboard/ parameter from the URL
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'inventory/login.html')


def user_logout(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('login')

def home(request):
    return redirect('dashboard')

def fix_april_17(request):
    create_snapshot(date(2026, 4, 17))
    return HttpResponse("April 17 snapshot recreated successfully!")
# ===========================
# DASHBOARD
# ===========================
@login_required
def dashboard(request):
    today = date.today()
    if not DailySnapshot.objects.filter(date=today).exists():
        ensure_daily_snapshots()
 
    # 1. BASIC METRICS (Using Count)
    total_items = Item.objects.count()
    
    # 2. LOW STOCK (Filter by threshold - adjust '5' to your needs)
    low_stock_threshold = 5
    low_stock_items = Item.objects.filter(quantity__lte=low_stock_threshold)
    low_stock_count = low_stock_items.count()
    
    well_stock = total_items - low_stock_count

    # 3. TOTAL VALUE (Database-level math is 10x faster than sum() loop)
    total_value_data = Item.objects.aggregate(
        total=Sum(F('price') * F('quantity'))
    )
    total_value = total_value_data['total'] or 0

    # 4. PERCENTAGE FOR PROGRESS BAR
    if total_items > 0:
        low_stock_percent = (low_stock_count / total_items) * 100
    else:
        low_stock_percent = 0

    # 5. STOCK DISTRIBUTION (Count items per category)
    # This generates the list for your "Items per category" card
    stock_distribution = Category.objects.annotate(
        count=Count('item')
    ).order_by('-count')

    return render(request, "inventory/dashboard.html", {
        "total_items": total_items,
        "low_stock": low_stock_count,
        "well_stock": well_stock,
        "total_value": f"{total_value:,.2f}", # Formatted with commas and 2 decimals
        "low_stock_percent": round(low_stock_percent, 1),
        "stock_distribution": stock_distribution,
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
    # Ensure settings exist for this user
    settings_instance, _ = ShopSettings.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ShopSettingsForm(request.POST, request.FILES, instance=settings_instance)
        
        # 1. Capture User Data
        username = request.POST.get("username")
        email = request.POST.get("email")
        
        # 2. Capture Password Data
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        # --- PART A: PROFILE UPDATE (Always processed) ---
        if username:
            request.user.username = username
        if email:
            request.user.email = email
        request.user.save()

        # --- PART B: SECURITY UPDATE (Only if new_password is typed) ---
        password_error = False
        if new_password:
            if not current_password:
                messages.error(request, "Current password is required to authorize a change.")
                password_error = True
            elif not request.user.check_password(current_password):
                messages.error(request, "The current password you entered is incorrect.")
                password_error = True
            elif new_password != confirm_password:
                messages.error(request, "The new passwords do not match.")
                password_error = True
            else:
                request.user.set_password(new_password)
                request.user.save()
                messages.success(request, "Security credentials updated successfully!")

        # --- PART C: SHOP UPDATE (Only if no password errors) ---
        if not password_error:
            if form.is_valid():
                form.save()
                messages.success(request, "General settings synchronized successfully.")
                return redirect('settings_page')
            else:
                messages.error(request, "Please review the shop information fields.")

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
    ensure_daily_snapshots()
 
    query = request.GET.get("q", "")
    items = Item.objects.all()
    
    if query:
        # UPDATED: Now searches Item Name, Category, AND Compatible Units
        items = items.filter(
            Q(name__icontains=query) | 
            Q(category__name__icontains=query) |
            Q(compatible_units__icontains=query)  # <--- This is the new line
        )

    # Calculate summary data based on the filtered list
    total_items_count = items.count()
    low_stock_count = items.filter(quantity__lte=5).count()
    
    total_value_data = items.aggregate(total=Sum(F('price') * F('quantity')))
    total_value = total_value_data['total'] or 0

    return render(request, "inventory/all_items.html", {
        "items": items,
        "total_items": total_items_count,
        "low_stock": low_stock_count,
        "total_value": f"{total_value:,.2f}",
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
    
    # ✅ Sort by name (A-Z)
    categories = Category.objects.all().order_by('name')

    if query:
        categories = categories.filter(name__icontains=query)

    return render(request, 'inventory/categories.html', {
        'categories': categories,
        'total_categories': categories.count(),
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
    selected_item = get_object_or_404(Item, pk=pk) if pk else None
    today = timezone.localtime(timezone.now()).date()
    
    # 1. SEARCH & FILTER LOGIC
    query = request.GET.get('q', '')
    items = Item.objects.select_related('category').all().order_by('name')

    if query:
        items = items.filter(
            Q(name__icontains=query) | 
            Q(category__name__icontains=query) |
            Q(compatible_units__icontains=query)
        ).distinct()

    # 2. POST HANDLING (Simplified to let Model handle the logic)
    if request.method == "POST":
        item_id = request.POST.get('item')
        target_item = selected_item if selected_item else get_object_or_404(Item, id=item_id)
        
        try:
            quantity = int(request.POST.get('quantity', 0))
            reason = request.POST.get('reason')
            remarks = request.POST.get('remarks', '')

            # Validation: Simple check before attempting save
            if reason == 'remove' and quantity > target_item.quantity:
                messages.error(request, f"Insufficient stock. {target_item.name} only has {target_item.quantity} available.")
                return redirect(request.path)

            # NOTE: We do NOT update target_item.quantity here.
            # Your StockMovement.save() method in models.py handles:
            # - Updating the Item balance
            # - Updating the Daily Snapshot/Daily Audit report
            StockMovement.objects.create(
                item=target_item,
                quantity=quantity,
                reason=reason,
                user=request.user,
                remarks=remarks
            )

            messages.success(request, f"Terminal Sync complete for {target_item.name}.")
            return redirect('adjust_stock')
            
        except ValueError:
            messages.error(request, "Invalid quantity. Please enter a whole number.")
        except Exception as e:
            messages.error(request, f"System Error: {str(e)}")

    # 3. DASHBOARD METRICS (Stats Cards)
    # Low stock items (Threshold from ShopSettings or hardcoded 5)
    critical_items = Item.objects.filter(quantity__lte=5).select_related('category').order_by('quantity')[:5]
    
    # Total Inventory Valuation
    total_value = Item.objects.aggregate(
        total=Sum(F('price') * F('quantity'))
    )['total'] or 0

    low_stock_count = Item.objects.filter(quantity__lte=5).count()
    
    # Recent Activity Feed
    recent_movements = StockMovement.objects.filter(
        date__date=today
    ).select_related('item', 'user').order_by('-date')[:5]

    return render(request, "inventory/adjust_stock.html", {
        "items": items,
        "selected_item": selected_item,
        "today": today,
        "query": query,
        "critical_items": critical_items,
        "low_stock_count": low_stock_count,
        "total_value": total_value,
        "recent_movements": recent_movements,
    })

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
    from .models import Item, DailyItemSnapshot
    from .utils import create_snapshot # Ensure this import is here

    date_obj = date(year, month, day)
    snapshot = create_snapshot(date_obj)

    all_items = Item.objects.select_related('category').all().order_by('name')
    
    # Check this variable name carefully:
    today_snapshots = {
        s.item_id: s for s in DailyItemSnapshot.objects.filter(snapshot=snapshot)
    }

    grouped = {}
    for item in all_items:
        category = item.category.name if item.category else "Uncategorized"
        
        # Using 'today_snapshots' to match the definition above
        snap = today_snapshots.get(item.id)
        
        if snap:
            display_data = snap
        else:
            last_record = DailyItemSnapshot.objects.filter(
                item=item, 
                snapshot__date__lt=date_obj
            ).order_by('-snapshot__date').first()
            
            carry_qty = last_record.ending_quantity if last_record else item.quantity
            
            display_data = {
                'item': item,
                'beginning_quantity': carry_qty,
                'stock_in': 0,
                'stock_out': 0,
                'ending_quantity': carry_qty
            }

        grouped.setdefault(category, []).append(display_data)

    grouped = dict(sorted(grouped.items()))
    shop_settings = getattr(request.user, 'shopsettings', None)
    shop_name = shop_settings.shop_name if shop_settings else "Autosthetics"

    return render(request, 'inventory/daily_detail.html', {
        'snapshot': snapshot,
        'grouped': grouped,
        'shop_name': shop_name,
    })


@login_required
def monthly_detail(request):
    year_param = request.GET.get('year')
    month_param = request.GET.get('month')

    # Default to current month/year
    current_now = now()
    if not year_param or not month_param:
        year, month = current_now.year, current_now.month
    else:
        try:
            year, month = int(year_param), int(month_param)
        except (ValueError, TypeError):
            year, month = current_now.year, current_now.month

    today = date.today()

    # 1. DATA FETCHING (Capped at Today)
    snapshots = DailySnapshot.objects.filter(
        date__year=year,
        date__month=month,
        date__lte=today
    ).order_by('-date')

    records = DailyItemSnapshot.objects.filter(
        snapshot__date__year=year,
        snapshot__date__month=month,
        snapshot__date__lte=today
    ).select_related("item", "item__category").order_by("item__category__name", "item__name")

    # 2. SUMMARY BUILDING
    summary = {}
    for record in records:
        cat_name = record.item.category.name if record.item.category else "Uncategorized"
        item_name = record.item.name

        if cat_name not in summary:
            summary[cat_name] = {}

        if item_name not in summary[cat_name]:
            summary[cat_name][item_name] = {
                "beginning": record.beginning_quantity,
                "stock_in": 0,
                "stock_out": 0,
                "ending": 0,
            }

        summary[cat_name][item_name]["stock_in"] += record.stock_in
        summary[cat_name][item_name]["stock_out"] += record.stock_out

    # 3. TOTALS
    for cat, items in summary.items():
        cat_total = {"beginning": 0, "stock_in": 0, "stock_out": 0, "ending": 0}
        for item_key, data in items.items():
            if item_key == "totals": continue
            data["ending"] = data["beginning"] + data["stock_in"] - data["stock_out"]
            cat_total["beginning"] += data["beginning"]
            cat_total["stock_in"] += data["stock_in"]
            cat_total["stock_out"] += data["stock_out"]
            cat_total["ending"] += data["ending"]
        items["totals"] = cat_total

    return render(request, 'inventory/monthly_detail.html', {
        'snapshots': snapshots,
        'summary': dict(sorted(summary.items())),
        'year': year,
        'month': month,
        'categories': sorted(list(summary.keys())),
    })


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

    selected_dates = request.POST.get('selected_dates')
    date_obj = parse_date(selected_dates)

    snapshot = DailySnapshot.objects.filter(date=date_obj).first()

    if not snapshot:
        return HttpResponse("No data found.")

    # ✅ Get selected categories
    selected_categories = request.POST.getlist("categories")

    # ✅ Get items (sorted)
    items = DailyItemSnapshot.objects.filter(snapshot=snapshot)\
        .select_related('item__category')\
        .order_by('item__name')

    # ✅ FIX: Handle empty selection BEFORE loop
    if not selected_categories:
        selected_categories = list(set(
            i.item.category.name if i.item.category else "Uncategorized"
            for i in items
        ))

    grouped = {}

    for item in items:
        category_name = item.item.category.name if item.item.category else "Uncategorized"

        # ✅ FILTER HERE
        if category_name not in selected_categories:
            continue

        grouped.setdefault(category_name, []).append(item)

    # ✅ AFTER loop
    shop = ShopSettings.objects.first()
    shop_name = shop.shop_name if shop else "Inventory System"

    html_string = render_to_string(
        "inventory/pdf/daily_detail_pdf.html",
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

    # ✅ Get selected categories from POST
    selected_categories = request.POST.getlist("categories")

    # ✅ Fetch records for the month (sorted already)
    records = DailyItemSnapshot.objects.filter(
        snapshot__date__year=year,
        snapshot__date__month=month
    ).select_related("item__category").order_by(
        "item__category__name", "item__name"
    )

    summary = {}

    # ✅ Build summary dictionary
    for record in records:
        category = record.item.category.name if record.item.category else "Uncategorized"

        # ✅ Apply category filter (IMPORTANT)
        if selected_categories and category not in selected_categories:
            continue

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

    # ✅ Compute ending values AFTER aggregation
    for category, items in summary.items():
        for item_name, data in items.items():
            data["ending"] = (
                data["beginning"]
                + data["stock_in"]
                - data["stock_out"]
            )

    # ✅ Compute totals per category
    for category, items in summary.items():
        total = {"beginning": 0, "stock_in": 0, "stock_out": 0, "ending": 0}

        for item_name, data in items.items():
            total["beginning"] += data["beginning"]
            total["stock_in"] += data["stock_in"]
            total["stock_out"] += data["stock_out"]
            total["ending"] += data["ending"]

        items["totals"] = total

    # ✅ SORTING (VERY IMPORTANT 🔥)

    # Sort categories
    sorted_summary = dict(sorted(summary.items()))

    # Sort items inside each category
    for category in sorted_summary:
        items = sorted_summary[category]

        sorted_items = dict(sorted(
            (k, v) for k, v in items.items() if k != "totals"
        ))

        # Keep totals at bottom
        if "totals" in items:
            sorted_items["totals"] = items["totals"]

        sorted_summary[category] = sorted_items

    # ✅ Shop Info
    shop = ShopSettings.objects.first()
    shop_name = shop.shop_name if shop else "Inventory System"
    month_name = datetime(int(year), int(month), 1).strftime("%B")

    # ✅ Render HTML
    html_string = render_to_string(
        "inventory/pdf/monthly_summary_pdf.html",
        {
            "shop_name": shop_name,
            "month_name": month_name,
            "year": year,
            "summary": sorted_summary,
        }
    )

    # ✅ Generate PDF
    pdf_file = HTML(
        string=html_string,
        base_url=request.build_absolute_uri()
    ).write_pdf()

    # ✅ Response
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
    # 1. Capture the parameters from the URL (GET)
    week_num = int(request.GET.get('week', 0))
    year = int(request.GET.get('year', now().year))
    month = int(request.GET.get('month', now().month))

    if not week_num:
        return HttpResponse("Error: No week selected.", status=400)

    # 2. Calculate the Date Range based on the week number
    # Week 1: 1-7, Week 2: 8-14, Week 3: 15-21, Week 4: 22-28, Week 5: 29-End
    start_day = (week_num - 1) * 7 + 1
    
    # Get the total days in the month to handle Week 5 correctly
    _, last_day_of_month = calendar.monthrange(year, month)
    
    if week_num < 5:
        end_day = start_day + 6
    else:
        end_day = last_day_of_month

    # Create actual date objects
    try:
        start_date = date(year, month, start_day)
        end_date = date(year, month, end_day)
    except ValueError:
        return HttpResponse("Error: Invalid date range for this month.", status=400)

    # 3. Fetch snapshots for the specific date range
    snapshots = DailySnapshot.objects.filter(date__range=[start_date, end_date])
    
    # Fetch all item records for those snapshots
    records = DailyItemSnapshot.objects.filter(
        snapshot__in=snapshots
    ).select_related("item", "item__category").order_by('item__category__name', 'item__name')

    # 4. Group data for the PDF (Aggregate 7 days into 1 row per item)
    categories = {}
    for record in records:
        cat_name = record.item.category.name if record.item.category else "General"
        item_name = record.item.name

        if cat_name not in categories:
            categories[cat_name] = {}

        if item_name not in categories[cat_name]:
            # 'beginning' comes from the first record found in the week
            categories[cat_name][item_name] = {
                "beginning": record.beginning_quantity, 
                "in": 0,
                "out": 0,
                "ending": record.ending_quantity 
            }

        # Accumulate movement across the week
        categories[cat_name][item_name]["in"] += record.stock_in
        categories[cat_name][item_name]["out"] += record.stock_out
        # 'ending' is updated continuously so the last record in the loop is the final stock
        categories[cat_name][item_name]["ending"] = record.ending_quantity

    # Prepare data structure for the template
    weeks_data = [{
        "label": f"Week {week_num:02d} ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')})",
        "categories": categories
    }]

    # 5. PDF Generation Setup
    shop = ShopSettings.objects.first()
    shop_name = shop.shop_name if shop else "Autosthetics Studio"
    
    # IMPORTANT: Ensure this template file does NOT use {% extends %}
    html_string = render_to_string(
        "inventory/pdf/weekly_summary_pdf.html", 
        {
            "weeks": weeks_data,
            "shop_name": shop_name,
            "year": year,
            "month_name": calendar.month_name[month]
        }
    )

    # Convert HTML to PDF using WeasyPrint
    pdf_file = HTML(string=html_string).write_pdf()
    
    # Create Response
    filename = f"Weekly_Summary_W{week_num}_{calendar.month_name[month]}_{year}.pdf"
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response
    
@login_required
def custom_summary(request):
    from .utils import create_snapshot  # ensure it's imported
    summary = []
    start_date = None
    end_date = None

    if request.method == "POST":
        start_date = parse_date(request.POST.get("start_date"))
        end_date = parse_date(request.POST.get("end_date"))

        if start_date and end_date:

            # ✅ Ensure snapshots exist for each date in range
            current_date = start_date
            while current_date <= end_date:
                create_snapshot(current_date)
                current_date += timedelta(days=1)

            # ✅ Fetch all DailyItemSnapshots in range
            records = DailyItemSnapshot.objects.filter(
                snapshot__date__range=[start_date, end_date]
            ).select_related("item", "item__category").order_by("snapshot__date", "item__name")

            temp = {}

            for record in records:
                item_id = record.item.id
                item_name = record.item.name
                category_name = record.item.category.name if record.item.category else "Uncategorized"

                if item_id not in temp:
                    temp[item_id] = {
                        "item_name": item_name,
                        "category": category_name,
                        "beginning": record.beginning_quantity,
                        "stock_in": 0,
                        "stock_out": 0,
                        "ending": 0,
                    }

                temp[item_id]["stock_in"] += record.stock_in
                temp[item_id]["stock_out"] += record.stock_out
                # Sum over range; ending will be computed later
                temp[item_id]["ending"] += record.stock_in - record.stock_out

            # ✅ Compute ending properly
            for item_data in temp.values():
                item_data["ending"] = item_data["beginning"] + item_data["stock_in"] - item_data["stock_out"]

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
    item_id = request.POST.get('item_id')
    quantity_str = request.POST.get('quantity', '0')
    reason = request.POST.get('reason', 'adjust')

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

        # ❌ REMOVE manual quantity updates
        # ❌ REMOVE snapshot manipulation

        # ✅ ONLY CREATE STOCK MOVEMENT
        StockMovement.objects.create(
            item=item,
            quantity=quantity,
            reason=reason,
            user=request.user
        )

        # ✅ Refresh item from DB (already updated by model)
        item.refresh_from_db()

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



# ===========================
# INTERN MAINTENANCE PANEL
# ===========================
# ============================================================
# INTERN MAINTENANCE PANEL (SECRET ADMIN ACCESS)
# ============================================================
# ============================================================
# INTERN MAINTENANCE PANEL (SECRET ADMIN ACCESS)
# ============================================================
@login_required
def intern_maintenance(request):
    # 1. INITIALIZE VARIABLES AT THE TOP (This kills the NameError)
    unique_units = []  # <--- DEFINED FIRST
    query = request.GET.get('q', '').strip()
    items = Item.objects.all()

    # 2. SECURITY CHECK
    if not request.user.is_superuser:
        return redirect('dashboard')

    # 3. BUILD THE SIDEBAR LIST (Always do this)
    all_tagged = Item.objects.exclude(compatible_units__isnull=True).exclude(compatible_units__exact='')
    unique_set = set()
    for i in all_tagged:
        if i.compatible_units:
            parts = [u.strip() for u in i.compatible_units.split(',')]
            unique_set.update(parts)
    unique_units = sorted(list(unique_set)) # Now unique_units is fully populated

    # 4. HANDLE THE "UPDATE" BUTTON (POST)
    if request.method == "POST":
        item_id = request.POST.get('item_id')
        new_units = request.POST.get('compatible_units')
        
        item = get_object_or_404(Item, id=item_id)
        item.compatible_units = new_units
        item.save()
        
        messages.success(request, f"Updated compatibility for {item.name}")
        # IMPORTANT: Redirect re-runs the whole function to refresh data
        return redirect(request.get_full_path())

    # 5. FILTER THE TABLE (If searching)
    if query:
        items = items.filter(compatible_units__icontains=query)

    # 6. RENDER THE PAGE
    # All variables (unique_units, items, query) are now guaranteed to exist
    return render(request, "inventory/maintenance_panel.html", {
        "unique_units": unique_units,
        "items": items,
        "query": query,
    })


@login_required
def secret_maintenance_panel(request):
    # 1. SECURITY: Admin Only
    if not request.user.is_superuser:
        return redirect('dashboard')

    # 2. HANDLE DATA SYNC (POST)
    if request.method == "POST":
        item_id = request.POST.get('item_id')
        new_units = request.POST.get('compatible_units')
        item = get_object_or_404(Item, id=item_id)
        item.compatible_units = new_units
        item.save()
        messages.success(request, f"Configuration synchronized for {item.name}")
        # Redirect back to the exact same URL (keeps search/filters active)
        return redirect(request.get_full_path())

    # 3. CORE DATA FETCHING
    query = request.GET.get('q', '').strip()
    # select_related makes the category name load instantly
    all_items = Item.objects.select_related('category').all()
    
    # 4. AUDIT METRICS (For the Header)
    total_count = all_items.count()
    tagged_items = all_items.exclude(Q(compatible_units__isnull=True) | Q(compatible_units__exact=''))
    tagged_count = tagged_items.count()
    health = round((tagged_count / total_count * 100), 1) if total_count > 0 else 0

    # 5. BUILD UNIQUE TAG LIST (Sidebar)
    unique_set = set()
    for i in tagged_items:
        if i.compatible_units:
            try:
                parts = [u.strip() for u in i.compatible_units.split(',')]
                unique_set.update(parts)
            except AttributeError:
                continue
    unique_units = sorted(list(unique_set))

    # 6. FILTER LOGIC (The Search Bar)
    # This filters the table on the right based on name OR compatibility
    items = all_items
    if query:
        items = items.filter(
            Q(name__icontains=query) | 
            Q(compatible_units__icontains=query) |
            Q(category__name__icontains=query) # Added category search too!
        )

    # 7. RENDER
    return render(request, "inventory/maintenance_panel.html", {
        "unique_units": unique_units,
        "items": items,
        "query": query,
        "health": health,
        "total": total_count,
        "tagged_count": tagged_count, # Added this for your HUD
    })
