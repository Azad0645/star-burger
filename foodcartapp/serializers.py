from rest_framework import serializers
from django.db import transaction
from phonenumber_field.serializerfields import PhoneNumberField
from .models import Order, OrderItem, Product

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

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('products')
        order = Order.objects.create(**validated_data)
        OrderItem.objects.bulk_create([
            OrderItem(order=order, product=item['product'], quantity=item['quantity'])
            for item in items_data
        ])
        return order
