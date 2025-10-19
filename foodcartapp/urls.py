from django.urls import path
from .views import product_list_api, banners_list_api
from .views import OrderCreateView

app_name = "foodcartapp"

urlpatterns = [
    path('products/', product_list_api),
    path('banners/', banners_list_api),
    path('order/', OrderCreateView.as_view()),
]
