from django.urls import path

from . import views

app_name = "achievement_categories"

urlpatterns = [
    path("", views.AchievementCategoryListView.as_view(), name="list"),
]
