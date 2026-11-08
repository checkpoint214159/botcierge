from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path("", include("catalog.urls")),
    path("accounts/", include("accounts.urls")),
    path("plan/", include("planner.urls")),
    path("orders/", include("orders.urls")),
    path("support/", include("support.urls")),
    path("staff/", include("staffpanel.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
