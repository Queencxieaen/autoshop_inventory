from django import forms
from .models import Item, Category, ShopSettings, DailyItemSnapshot


# forms.py

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        # 1. ADDED 'compatible_units' HERE
        fields = ['name', 'category', 'unit', 'price', 'compatible_units']

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Item Name'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'unit': forms.Select(attrs={
                'class': 'form-select'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Unit Price'
            }),
            # 2. ADDED THE TEXTAREA WIDGET HERE
            'compatible_units': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Mitsubishi Canter, Toyota Vios, Isuzu Elf',
                'rows': 3  # This makes the box 3 lines tall
            }),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input'}),
            'description': forms.Textarea(attrs={'class': 'input'}),
        }


class AdjustStockForm(forms.Form):
    item = forms.ModelChoiceField(
        queryset=Item.objects.all(),
        empty_label="Select",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    quantity = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    reason = forms.ChoiceField(
        choices=[('add', 'Stock In'), ('remove', 'Stock Out')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class ShopSettingsForm(forms.ModelForm):
    class Meta:
        model = ShopSettings
        fields = ['shop_name', 'address', 'contact', 'low_stock_limit', 'theme', 'profile_image']
        widgets = {
            'shop_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'contact': forms.TextInput(attrs={'class': 'form-control'}),
            'low_stock_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'theme': forms.Select(attrs={'class': 'form-select'}),
            'profile_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class AdminCompatibleUnitsForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['compatible_units']
        widgets = {
            'compatible_units': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Update car models (e.g. Toyota Vios, Avanza)'
            }),
        }
