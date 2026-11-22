from django.urls import path

from . import views

app_name = "profiles"

urlpatterns = [
    path("me/", views.OwnProfileView.as_view(), name="me"),
    path("me/privacy/", views.OwnPrivacyView.as_view(), name="me-privacy"),
    path("me/picture/", views.OwnPictureView.as_view(), name="me-picture"),
    path("me/cover/", views.OwnCoverView.as_view(), name="me-cover"),
    path("<uuid:user_id>/", views.ProfileDetailView.as_view(), name="detail"),
]
