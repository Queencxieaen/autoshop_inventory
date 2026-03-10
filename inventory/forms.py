from django import forms
from .models import Item, Category, ShopSettings, DailyItemSnapshot


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['name', 'category', 'unit', 'price']

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