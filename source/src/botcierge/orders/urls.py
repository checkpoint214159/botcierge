from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("book/<int:pk>/", views.booking, name="booking"),
    path("book/<int:pk>/quote/", views.booking_quote, name="booking_quote"),
    path("cart/", views.cart, name="cart"),
    path("cart/<int:pk>/remove/", views.cart_remove, name="cart_remove"),
    path("cart/<int:pk>/restore/", views.cart_restore, name="cart_restore"),
    path("checkout/<int:pk>/", views.checkout, name="checkout"),
    path("", views.order_list, name="order_list"),
    path("<int:pk>/confirmed/", views.confirmation, name="confirmation"),
    path("<int:pk>/", views.order_detail, name="order_detail"),
]
