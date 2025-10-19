import json
from django.http import JsonResponse
from django.templatetags.static import static
from django.db import transaction
from .models import Product, Order, OrderItem


def banners_list_api(request):
    # FIXME move data to db?
    return JsonResponse([
        {
            'title': 'Burger',
            'src': static('burger.jpg'),
            'text': 'Tasty Burger at your door step',
        },
        {
            'title': 'Spices',
            'src': static('food.jpg'),
            'text': 'All Cuisines',
        },
        {
            'title': 'New York',
            'src': static('tasty.jpg'),
            'text': 'Food is incomplete without a tasty dessert',
        }
    ], safe=False, json_dumps_params={
        'ensure_ascii': False,
        'indent': 4,
    })


def product_list_api(request):
    products = Product.objects.select_related('category').available()

    dumped_products = []
    for product in products:
        dumped_product = {
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'special_status': product.special_status,
            'description': product.description,
            'category': {
                'id': product.category.id,
                'name': product.category.name,
            } if product.category else None,
            'image': product.image.url,
            'restaurant': {
                'id': product.id,
                'name': product.name,
            }
        }
        dumped_products.append(dumped_product)
    return JsonResponse(dumped_products, safe=False, json_dumps_params={
        'ensure_ascii': False,
        'indent': 4,
    })


def register_order(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Некорректный JSON"}, status=400)

        try:
            with transaction.atomic():
                order = Order.objects.create(
                    firstname=data['firstname'],
                    lastname=data['lastname'],
                    phonenumber=data['phonenumber'],
                    address=data['address']
                )

                for item in data['products']:
                    product = Product.objects.get(id=item['product'])
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=item['quantity']
                    )

        except KeyError as e:
            return JsonResponse({"error": f"Отсутствует обязательное поле: {e}"}, status=400)
        except Product.DoesNotExist:
            return JsonResponse({"error": "Указан несуществующий товар"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

        return JsonResponse({"status": "ok", "order_id": order.id})

    return JsonResponse({"error": "Разрешён только POST-запрос"}, status=405)
