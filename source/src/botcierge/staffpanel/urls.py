from django.urls import path

from . import views

app_name = "staffpanel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("robots/", views.robot_list, name="robot_list"),
    path("robots/new/", views.robot_edit, name="robot_new"),
    path("robots/<int:pk>/", views.robot_edit, name="robot_edit"),
    path("robots/<int:pk>/toggle/", views.robot_toggle, name="robot_toggle"),
    path("fleet/", views.fleet_list, name="fleet_list"),
    path("fleet/new/", views.fleet_edit, name="fleet_new"),
    path("fleet/<int:pk>/", views.fleet_edit, name="fleet_edit"),
    path("addons/", views.addon_list, name="addon_list"),
    path("addons/new/", views.addon_edit, name="addon_new"),
    path("addons/<int:pk>/", views.addon_edit, name="addon_edit"),
    path("addons/<int:pk>/toggle/", views.addon_toggle, name="addon_toggle"),
    path("skill-packs/", views.skillpack_list, name="skillpack_list"),
    path("skill-packs/new/", views.skillpack_edit, name="skillpack_new"),
    path("skill-packs/<int:pk>/", views.skillpack_edit, name="skillpack_edit"),
    path("skill-packs/<int:pk>/toggle/", views.skillpack_toggle, name="skillpack_toggle"),
    path("recommendation-models/", views.ml_models, name="ml_models"),
    path("recommendation-models/changes.csv", views.ml_overrides_csv, name="ml_overrides_csv"),
    path("orders/", views.order_list, name="order_list"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("requests/", views.request_list, name="request_list"),
    path("review/", views.review_list, name="review_list"),
    path("review/<int:pk>/", views.review_detail, name="review_detail"),
    path("tickets/", views.ticket_list, name="ticket_list"),
    path("tickets/<int:pk>/", views.ticket_detail, name="ticket_detail"),
    path("promos/", views.promo_list, name="promo_list"),
    path("promos/new/", views.promo_edit, name="promo_new"),
    path("promos/<int:pk>/", views.promo_edit, name="promo_edit"),
    path("promos/<int:pk>/toggle/", views.promo_toggle, name="promo_toggle"),
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("customers/<int:pk>/toggle/", views.customer_toggle, name="customer_toggle"),
    path("customer-reviews/", views.customer_reviews, name="customer_reviews"),
    path("customer-reviews/<int:pk>/toggle/", views.customer_review_toggle, name="customer_review_toggle"),
]
