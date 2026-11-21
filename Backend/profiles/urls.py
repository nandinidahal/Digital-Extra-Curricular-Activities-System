from django.urls import path

from . import views

# Mounted under /api/profile/ in config/urls.py. <int:user_id> never matches "me" or "reactivate".
urlpatterns = [
    path("me/", views.ProfileMeView.as_view(), name="profile-me"),
    path("me/update/", views.ProfileUpdateView.as_view(), name="profile-update"),
    path("me/upload-picture/", views.ProfilePictureUploadView.as_view(), name="profile-upload-picture"),
    path("me/remove-picture/", views.ProfilePictureRemoveView.as_view(), name="profile-remove-picture"),
    path("me/settings/", views.PrivacySettingsView.as_view(), name="profile-settings"),
    path("me/account/", views.AccountView.as_view(), name="profile-account"),
    path("me/email/change/", views.EmailChangeRequestView.as_view(), name="profile-email-change"),
    path("me/email/confirm/", views.EmailChangeConfirmView.as_view(), name="profile-email-confirm"),
    path("me/deactivate/", views.DeactivateAccountView.as_view(), name="profile-deactivate"),
    path("me/dashboard/", views.DashboardView.as_view(), name="profile-dashboard"),
    path("reactivate/", views.ReactivateAccountView.as_view(), name="profile-reactivate"),
    path("<int:user_id>/", views.PublicProfileView.as_view(), name="profile-detail"),
    path("<int:user_id>/achievements/", views.ProfileAchievementsView.as_view(), name="profile-achievements"),
]
