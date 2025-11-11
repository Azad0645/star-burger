from rest_framework import serializers
from django.db import transaction
from phonenumber_field.serializerfields import PhoneNumberField
from .models import Order, OrderItem, Product
from geo.utils import fetch_coordinates


class OrderItemCreateSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all()
    )
    quantity = serializers.IntegerField(min_value=1)


class OrderCreateSerializer(serializers.Serializer):
    firstname = serializers.CharField(max_length=50, allow_blank=False, trim_whitespace=True)
    lastname = serializers.CharField(max_length=50, allow_blank=False, trim_whitespace=True)
    phonenumber = PhoneNumberField()
    address = serializers.CharField(max_length=200, allow_blank=False, trim_whitespace=True)
    products = OrderItemCreateSerializer(many=True, allow_empty=False)
    status = serializers.CharField(read_only=True)

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('products')

        geo = fetch_coordinates(validated_data['address'])
        order = Order.objects.create(
            **validated_data,
            location=geo if geo else None,
        )

        OrderItem.objects.bulk_create([
            OrderItem(
                order=order,
                product=item['product'],
                quantity=item['quantity'],
                price_snapshot=item['product'].price,
            )
            for item in items_data
        ])
        return order


class OrderItemReadSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'product_name', 'quantity')


class OrderReadSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)

    class Meta:
        model = Order
        fields = ('id', 'firstname', 'lastname', 'phonenumber', 'address', 'items', 'status', 'status_display', 'payment_method', 'payment_method_display')
