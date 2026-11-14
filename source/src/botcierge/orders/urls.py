from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("cart/", views.cart, name="cart"),
    path("cart/add/<int:rec_id>/", views.cart_add, name="cart_add"),
    path("cart/remove/", views.cart_remove, name="cart_remove"),
    path("checkout/", views.checkout, name="checkout"),
    path("", views.order_list, name="order_list"),
    path("<int:pk>/confirmed/", views.confirmation, name="confirmation"),
    path("<int:pk>/", views.order_detail, name="order_detail"),
]
