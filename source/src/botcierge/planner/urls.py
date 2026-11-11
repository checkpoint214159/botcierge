from django.urls import path

from . import views

app_name = "planner"

urlpatterns = [
    path("", views.start, name="start"),
    path("mine/", views.my_plans, name="my_plans"),
    path("<int:pk>/", views.result, name="result"),
    path("<int:pk>/swap/", views.swap, name="swap"),
]
