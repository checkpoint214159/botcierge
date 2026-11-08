from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
    path("robots/", views.robot_list, name="robot_list"),
    path("robots/<slug:slug>/", views.robot_detail, name="robot_detail"),
]
