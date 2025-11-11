from django.db import models
from django.core.validators import MinValueValidator
from phonenumber_field.modelfields import PhoneNumberField
from django.db.models import Sum, F, DecimalField, Value
from django.db.models.functions import Coalesce
from geopy.distance import geodesic
from geo.utils import fetch_coordinates
from geo.models import GeocodedAddress


class Restaurant(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )
    address = models.CharField(
        'адрес',
        max_length=100,
        blank=True,
    )
    contact_phone = models.CharField(
        'контактный телефон',
        max_length=50,
        blank=True,
    )
    location = models.ForeignKey(
        GeocodedAddress,
        verbose_name='Координаты',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='restaurants',
    )

    class Meta:
        verbose_name = 'ресторан'
        verbose_name_plural = 'рестораны'

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def available(self):
        products = (
            RestaurantMenuItem.objects
            .filter(availability=True)
            .values_list('product')
        )
        return self.filter(pk__in=products)


class ProductCategory(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )

    class Meta:
        verbose_name = 'категория'
        verbose_name_plural = 'категории'

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )
    category = models.ForeignKey(
        ProductCategory,
        verbose_name='категория',
        related_name='products',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    price = models.DecimalField(
        'цена',
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    image = models.ImageField(
        'картинка'
    )
    special_status = models.BooleanField(
        'спец.предложение',
        default=False,
        db_index=True,
    )
    description = models.TextField(
        'описание',
        max_length=200,
        blank=True,
    )

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = 'товар'
        verbose_name_plural = 'товары'

    def __str__(self):
        return self.name


class RestaurantMenuItem(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        related_name='menu_items',
        verbose_name="ресторан",
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='menu_items',
        verbose_name='продукт',
    )
    availability = models.BooleanField(
        'в продаже',
        default=True,
        db_index=True
    )

    class Meta:
        verbose_name = 'пункт меню ресторана'
        verbose_name_plural = 'пункты меню ресторана'
        unique_together = [
            ['restaurant', 'product']
        ]

    def __str__(self):
        return f"{self.restaurant.name} - {self.product.name}"


class OrderQuerySet(models.QuerySet):
    def with_total_price(self):
        total_expr = Sum(
            F('items__quantity') * F('items__price_snapshot'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        return self.annotate(
            total_price=Coalesce(
                total_expr,
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )


class Order(models.Model):
    STATUS_CHOICES = [
        ('NEW', 'Принят'),
        ('COOKING', 'Готовится'),
        ('DELIVERING', 'Доставляется'),
        ('COMPLETED', 'Завершён'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Наличными'),
        ('ONLINE', 'Электронно'),
    ]

    firstname = models.CharField(
        verbose_name='Имя',
        max_length=50,
        blank=False,
        null=False,
        db_index=True
    )
    lastname = models.CharField(
        verbose_name='Фамилия',
        max_length=50,
        blank=False,
        null=False,
        db_index=True
    )
    phonenumber = PhoneNumberField(
        verbose_name='Номер телефона',
        blank=False,
        null=False,
        db_index=True
    )
    address = models.CharField(
        verbose_name='Адрес доставки',
        max_length=200,
        blank=False,
        null=False,
        db_index=True
    )
    status = models.CharField(
        verbose_name='Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default='NEW',
        db_index=True
    )
    comment = models.TextField(
        verbose_name='Комментарий',
        blank=True,
        null=False,
        default=''
    )
    created_at = models.DateTimeField(
        verbose_name='Дата создания',
        auto_now_add=True,
        db_index=True
    )
    called_at = models.DateTimeField(
        verbose_name='Дата звонка',
        null=True,
        blank=True,
        db_index=True
    )
    delivered_at = models.DateTimeField(
        verbose_name='Дата доставки',
        null=True,
        blank=True,
        db_index=True
    )
    payment_method = models.CharField(
        verbose_name='Способ оплаты',
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='CASH',
        db_index=True
    )
    cooking_restaurant = models.ForeignKey(
        Restaurant,
        verbose_name='Ресторан-исполнитель',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='orders',
    )
    location = models.ForeignKey(
        GeocodedAddress,
        verbose_name='Координаты доставки',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='orders',
    )

    objects = OrderQuerySet.as_manager()

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-id']

    def __str__(self):
        return f'Заказ {self.id} ({self.firstname} {self.lastname})'

    def available_restaurants(self):
        product_ids = set(self.items.values_list('product_id', flat=True))
        if not product_ids:
            return []

        menu_items = (
            RestaurantMenuItem.objects
            .filter(availability=True, product_id__in=product_ids)
            .select_related('restaurant')
        )

        restaurants = {}
        for menu_item in menu_items:
            restaurants.setdefault(menu_item.restaurant, set()).add(menu_item.product_id)

        suitable_restaurants = [
            restaurant
            for restaurant, products in restaurants.items()
            if products == product_ids
        ]

        return suitable_restaurants

    def available_restaurants_with_distance(self):
        restaurants = self.available_restaurants()

        if not self.location or self.location.lat is None or self.location.lng is None:
            return [
                {'restaurant': r, 'distance_km': None}
                for r in restaurants
            ]

        order_point = (self.location.lat, self.location.lng)
        result = []

        for restaurant in restaurants:
            loc = getattr(restaurant, 'location', None)
            if loc and loc.lat is not None and loc.lng is not None:
                rest_point = (loc.lat, loc.lng)
                distance_km = geodesic(order_point, rest_point).km
                result.append({
                    'restaurant': restaurant,
                    'distance_km': round(distance_km, 2),
                })

        result.sort(key=lambda x: x['distance_km'] if x['distance_km'] is not None else 999999)

        return result

    def save(self, *args, **kwargs):
        if self.pk:
            old = Order.objects.filter(pk=self.pk).first()
            if old and old.address != self.address:
                geo = fetch_coordinates(self.address)
                if geo:
                    self.location = geo
        else:
            geo = fetch_coordinates(self.address)
            if geo:
                self.location = geo

        super().save(*args, **kwargs)


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        verbose_name='Заказ',
        on_delete=models.CASCADE,
        related_name='items',
        blank=False,
        null=False
    )
    product = models.ForeignKey(
        Product,
        verbose_name='Продукт',
        on_delete=models.PROTECT,
        related_name='order_items',
        blank=False,
        null=False
    )
    quantity = models.PositiveIntegerField(
        verbose_name='Количество',
        blank=False,
        null=False,
        validators=[MinValueValidator(1)]
    )

    price_snapshot = models.DecimalField(
        'Цена в заказе',
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'
        ordering = ['id']

    def __str__(self):
        return f'{self.product.name} ({self.quantity} шт.)'
