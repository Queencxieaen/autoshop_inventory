from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django.contrib.auth import views as auth_views
from inventory import views

# from two_factor.urls import urlpatterns as tf_urls


urlpatterns = [

    # ADMIN
    path('admin/', admin.site.urls),

    # DASHBOARD
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),


    # path('', include(tf_urls)),

    # CATEGORIES
    path('categories/', views.categories, name='categories'),
    path('categories/add/', views.add_category, name='add_category'),
    path('categories/edit/<int:pk>/', views.edit_category, name='edit_category'),
    path('categories/delete/<int:pk>/', views.delete_category, name='delete_category'),

    # AUTH
    path('login/', auth_views.LoginView.as_view(
        template_name='inventory/login.html',
        redirect_authenticated_user=True
    ), name='login'),

    path('logout/', views.user_logout, name='logout'),

    # -------------------------
    # PASSWORD RESET (Django + OTP)
    # -------------------------

    # Django built-in email reset
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='inventory/password_reset.html'
    ), name='password_reset'),

    path('password_reset_done/', auth_views.PasswordResetDoneView.as_view(
        template_name='inventory/password_reset_done.html'
    ), name='password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='inventory/password_reset_confirm.html'
    ), name='password_reset_confirm'),

    path('password_reset_complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='inventory/password_reset_complete.html'
    ), name='password_reset_complete'),

    # OTP-based reset (renamed to avoid conflict)
    path('password-reset/send/', views.send_otp, name='send_otp'),
    path('password-reset/verify/', views.verify_otp, name='verify_otp'),
    path('password-reset/set/', views.set_new_password, name='set_new_password'),


    # AJAX
    path('ajax/stock-movement/', views.ajax_stock_movement, name='ajax_stock_movement'),
    path('ajax/item-quantity/', views.get_item_quantity, name='get_item_quantity'),

    # STOCK
    path('adjust-stock/', views.adjust_stock, name='adjust_stock'),
    path('adjust-stock/<int:pk>/', views.adjust_stock, name='adjust_stock_with_item'),
    path('low-stock/', views.low_stock_page, name='low_stock'),

    # ITEMS
    path("items/", views.all_items, name="all_items"),
    path('add/', views.add_item, name='add_item'),
    path('edit/<int:pk>/', views.edit_item, name='edit_item'),
    path('delete/<int:pk>/', views.delete_item, name='delete_item'),

    # SETTINGS
    path('settings/', views.settings_page, name='settings_page'),
    path('settings/profile/', views.edit_profile, name='edit_profile'),

    # REPORTS
    path('reports/', views.reports_home, name='reports'),
    path("reports/<int:year>/<int:month>/<int:day>/", views.daily_detail, name="daily_detail"),
    path('reports/monthly/', views.monthly_detail, name='monthly_detail'),

    path('report/delete-selected/<int:year>/<int:month>/', views.delete_selected_reports, name='delete_selected_reports'),
    path('report/export-selected/<int:year>/<int:month>/', views.export_selected_days_pdf, name='export_selected_days_pdf'),
    path('report/delete/<str:date_str>/', views.delete_daily_report, name='delete_daily_report'),

    path("reports/weekly/", views.weekly_summary, name="weekly_summary"),
    path("reports/weekly/pdf/", views.weekly_summary_pdf, name="weekly_summary_pdf"),

    path("reports/monthly/<int:year>/<int:month>/", views.monthly_summary, name="monthly_summary"),
    path("reports/monthly/<int:year>/<int:month>/pdf/", views.monthly_summary_pdf, name="monthly_summary_pdf"),

    path("reports/custom-summary/", views.custom_summary, name="custom_summary"),
]

# MEDIA FILES (development)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)