from django.urls import path

from . import views

app_name = "support"

urlpatterns = [
    path("", views.ticket_new, name="home"),  # /support/ -> the support page (keeps any ?order=)
    path("review/<int:order_pk>/", views.review_new, name="review_new"),
    path("tickets/", views.ticket_list, name="ticket_list"),
    path("tickets/new/", views.ticket_new, name="ticket_new"),
    path("tickets/<int:pk>/", views.ticket_detail, name="ticket_detail"),
]
