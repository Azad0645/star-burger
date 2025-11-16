from django import forms
from django.shortcuts import redirect, render
from django.views import View
from django.urls import reverse_lazy
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Sum, IntegerField, Value
from django.db.models import Case, When
from django.db.models.functions import Coalesce

from django.contrib.auth import authenticate, login
from django.contrib.auth import views as auth_views

from foodcartapp.models import Product, Restaurant, Order
from geopy.distance import geodesic
from geo.models import GeocodedAddress
from geo.utils import fetch_coordinates


class Login(forms.Form):
    username = forms.CharField(
        label='Логин', max_length=75, required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Укажите имя пользователя'
        })
    )
    password = forms.CharField(
        label='Пароль', max_length=75, required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите пароль'
        })
    )


class LoginView(View):
    def get(self, request, *args, **kwargs):
        form = Login()
        return render(request, "login.html", context={
            'form': form
        })

    def post(self, request):
        form = Login(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                if user.is_staff:  # FIXME replace with specific permission
                    return redirect("restaurateur:RestaurantView")
                return redirect("start_page")

        return render(request, "login.html", context={
            'form': form,
            'ivalid': True,
        })


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy('restaurateur:login')


def is_manager(user):
    return user.is_staff  # FIXME replace with specific permission


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_products(request):
    restaurants = list(Restaurant.objects.order_by('name'))
    products = list(Product.objects.prefetch_related('menu_items'))

    products_with_restaurant_availability = []
    for product in products:
        availability = {item.restaurant_id: item.availability for item in product.menu_items.all()}
        ordered_availability = [availability.get(restaurant.id, False) for restaurant in restaurants]

        products_with_restaurant_availability.append(
            (product, ordered_availability)
        )

    return render(request, template_name="products_list.html", context={
        'products_with_restaurant_availability': products_with_restaurant_availability,
        'restaurants': restaurants,
    })


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_restaurants(request):
    return render(request, template_name="restaurants_list.html", context={
        'restaurants': Restaurant.objects.all(),
    })


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_orders(request):
    status_order = Case(
        When(status='UNPROCESSED', then=Value(0)),
        When(status='NEW', then=Value(1)),
        When(status='COOKING', then=Value(2)),
        When(status='DELIVERING', then=Value(3)),
        When(status='COMPLETED', then=Value(4)),
        default=Value(5),
        output_field=IntegerField(),
    )

    orders_qs = (
        Order.objects
        .with_total_price()
        .annotate(
            items_count=Coalesce(
                Sum('items__quantity'),
                Value(0),
                output_field=IntegerField(),
            ),
            status_priority=status_order,
        )
        .order_by('status_priority', '-id')
        .select_related('cooking_restaurant')
        .prefetch_related('items__product')
        .exclude(status='COMPLETED')
        .with_available_restaurants()
    )

    orders = list(orders_qs)

    addresses = set()
    for order in orders:
        if order.address:
            addresses.add(order.address)
        for restaurant in getattr(order, 'available_restaurants', []):
            if restaurant.address:
                addresses.add(restaurant.address)

    geocoded_addresses = GeocodedAddress.objects.filter(address__in=addresses)
    coords_by_address = {
        geo.address: (geo.lat, geo.lng)
        for geo in geocoded_addresses
        if geo.lat is not None and geo.lng is not None
    }

    missing_addresses = [addr for addr in addresses if addr not in coords_by_address]

    for addr in missing_addresses:
        geo = fetch_coordinates(addr)
        if geo and geo.lat is not None and geo.lng is not None:
            coords_by_address[addr] = (geo.lat, geo.lng)

    for order in orders:
        if order.address and order.address not in coords_by_address:
            order.address_not_found = True
        else:
            order.address_not_found = False

    for order in orders:
        if order.address_not_found:
            order.available_restaurants_with_distance = []
            continue

        order_coords = coords_by_address.get(order.address)
        restaurants_with_distance = []

        for restaurant in getattr(order, 'available_restaurants', []):
            rest_coords = coords_by_address.get(restaurant.address)
            distance_km = None
            if order_coords and rest_coords:
                distance_km = round(geodesic(order_coords, rest_coords).km, 2)

            restaurants_with_distance.append({
                'restaurant': restaurant,
                'distance_km': distance_km,
            })

        restaurants_with_distance.sort(key=lambda x: x['distance_km'] if x['distance_km'] is not None else 999999)
        order.available_restaurants_with_distance = restaurants_with_distance

    return render(request, 'order_items.html', {
        'order_items': orders,
    })
