"""Test-only URLconf: mounts the module exactly where the real project will (``/api/``) without
touching config/urls.py."""
from django.urls import include, path

urlpatterns = [path("api/", include("announcements.urls"))]
