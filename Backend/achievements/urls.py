from django.urls import path

from . import views

# Mounted under /api/ in config/urls.py. <int:pk> never matches "my" or "categories",
# so the order below is only for readability. There is deliberately no search route.
urlpatterns = [
    path("achievements/", views.AchievementCreateView.as_view(), name="achievement-create"),
    path("achievements/categories/", views.AchievementCategoryListView.as_view(), name="achievement-categories"),
    path("achievements/my/", views.MyAchievementListView.as_view(), name="achievement-my-list"),
    path("achievements/my/<int:pk>/", views.MyAchievementDetailView.as_view(), name="achievement-my-detail"),
    path("achievements/<int:pk>/", views.AchievementDetailView.as_view(), name="achievement-detail"),
    path(
        "achievements/<int:pk>/documents/<int:document_id>/download/",
        views.AchievementDocumentDownloadView.as_view(),
        name="achievement-document-download",
    ),
    path(
        "users/<int:user_id>/achievements/",
        views.UserPublicAchievementListView.as_view(),
        name="user-achievements",
    ),
]
