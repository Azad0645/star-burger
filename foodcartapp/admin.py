from django import forms
from django.contrib import admin
from django.shortcuts import reverse, redirect
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from geo.utils import fetch_coordinates

from .models import Product, ProductCategory, Restaurant, RestaurantMenuItem, Order, OrderItem


class RestaurantMenuItemInline(admin.TabularInline):
    model = RestaurantMenuItem
    extra = 0


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    search_fields = [
        'name',
        'address',
        'contact_phone',
    ]
    list_display = [
        'name',
        'address',
        'contact_phone',
    ]
    inlines = [
        RestaurantMenuItemInline
    ]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'get_image_list_preview',
        'name',
        'category',
        'price',
    ]
    list_display_links = [
        'name',
    ]
    list_filter = [
        'category',
    ]
    search_fields = [
        'name',
        'category__name',
    ]

    inlines = [
        RestaurantMenuItemInline
    ]
    fieldsets = (
        ('Общее', {
            'fields': [
                'name',
                'category',
                'image',
                'get_image_preview',
                'price',
            ]
        }),
        ('Подробно', {
            'fields': [
                'special_status',
                'description',
            ],
            'classes': [
                'wide'
            ],
        }),
    )

    readonly_fields = [
        'get_image_preview',
    ]

    class Media:
        css = {
            "all": (
                static("admin/foodcartapp.css")
            )
        }

    def get_image_preview(self, obj):
        if not obj.image:
            return 'выберите картинку'
        return format_html('<img src="{url}" style="max-height: 200px;"/>', url=obj.image.url)
    get_image_preview.short_description = 'превью'

    def get_image_list_preview(self, obj):
        if not obj.image or not obj.id:
            return 'нет картинки'
        edit_url = reverse('admin:foodcartapp_product_change', args=(obj.id,))
        return format_html('<a href="{edit_url}"><img src="{src}" style="max-height: 50px;"/></a>', edit_url=edit_url, src=obj.image.url)
    get_image_list_preview.short_description = 'превью'


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    search_fields = ['name']


class OrderItemInlineForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ['product', 'quantity', 'price_snapshot']
        widgets = {
            'price_snapshot': forms.NumberInput(attrs={'min': '0', 'step': '0.01'})
        }


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    form = OrderItemInlineForm
    extra = 0
    autocomplete_fields = ['product']
    fields = ['product', 'quantity', 'price_snapshot']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'firstname', 'lastname', 'phonenumber', 'address', 'status', 'comment', 'created_at', 'called_at', 'delivered_at', 'payment_method', 'cooking_restaurant']
    list_filter = ['status', 'created_at', 'payment_method', 'cooking_restaurant']
    search_fields = ['id', 'firstname', 'lastname', 'phonenumber', 'address', 'comment']
    inlines = [OrderItemInline]
    ordering = ['-id']
    fields = ['firstname', 'lastname', 'phonenumber', 'address', 'status', 'comment', 'created_at', 'called_at', 'delivered_at', 'payment_method', 'cooking_restaurant', 'location']
    readonly_fields = ['created_at', 'location']

    def save_model(self, request, obj, form, change):
        if obj.cooking_restaurant and obj.status == 'NEW':
            obj.status = 'COOKING'

        if 'address' in form.changed_data and obj.address:
            geo = fetch_coordinates(obj.address)
            if geo:
                obj.location = geo

        super().save_model(request, obj, form, change)

    def response_change(self, request, obj):
        next_url = request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure()
        ):
            return redirect(next_url)
        return super().response_change(request, obj)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'product', 'quantity', 'price_snapshot']
    list_select_related = ['order', 'product']
    search_fields = ['order__id', 'product__name']
    raw_id_fields = ['order', 'product']
