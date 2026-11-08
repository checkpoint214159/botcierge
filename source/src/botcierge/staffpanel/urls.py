from django.urls import path

from . import views

app_name = "staffpanel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("robots/", views.robot_list, name="robot_list"),
    path("fleet/", views.fleet_list, name="fleet_list"),
    path("orders/", views.order_list, name="order_list"),
    path("requests/", views.request_list, name="request_list"),
    path("tickets/", views.ticket_list, name="ticket_list"),
]
