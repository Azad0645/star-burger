from django.db import models
from django.core.validators import MinValueValidator
from phonenumber_field.modelfields import PhoneNumberField
from django.db.models import Sum, F, DecimalField, Value
from django.db.models.functions import Coalesce
from collections import defaultdict


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

    def with_available_restaurants(self):
        qs = self.prefetch_related('items__product')
        orders = list(qs)

        if not orders:
            return qs

        menu_items = (
            RestaurantMenuItem.objects
            .filter(availability=True)
            .select_related("restaurant")
        )

        restaurants_products = defaultdict(set)
        restaurants_by_id = {}

        for item in menu_items:
            restaurants_products[item.restaurant_id].add(item.product_id)
            restaurants_by_id[item.restaurant_id] = item.restaurant

        for order in orders:
            order_product_ids = {item.product_id for item in order.items.all()}

            if not order_product_ids:
                order.available_restaurants = []
                continue

            available = []
            for restaurant_id, product_ids in restaurants_products.items():
                if order_product_ids.issubset(product_ids):
                    available.append(restaurants_by_id[restaurant_id])

            order.available_restaurants = available

        return qs


class Order(models.Model):
    STATUS_CHOICES = [
        ("UNPROCESSED", "Необработан"),
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
        default='UNPROCESSED',
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

    objects = OrderQuerySet.as_manager()

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-id']

    def __str__(self):
        return f'Заказ {self.id} ({self.firstname} {self.lastname})'


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
