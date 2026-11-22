from django.urls import path

from . import views

app_name = "categories"

urlpatterns = [
    path("", views.CategoryListCreateView.as_view(), name="list"),
    path("<uuid:category_id>/", views.CategoryDetailView.as_view(), name="detail"),
]
