from django.urls import path

from . import views

app_name = "achievements"

urlpatterns = [
    path("", views.AchievementListCreateView.as_view(), name="list"),
    path("me/", views.MyAchievementsView.as_view(), name="me"),
    path("featured/", views.FeaturedAchievementsView.as_view(), name="featured"),
    path("pending/", views.PendingReviewView.as_view(), name="pending"),
    path("stats/", views.StatsView.as_view(), name="stats"),
    path("search/", views.SearchView.as_view(), name="search"),
    path("users/<uuid:user_id>/", views.UserAchievementsView.as_view(), name="user"),
    path("evidence/<uuid:evidence_id>/", views.EvidenceDeleteView.as_view(), name="evidence-delete"),
    path("evidence/<uuid:evidence_id>/download/", views.EvidenceDownloadView.as_view(), name="evidence-download"),
    path("<uuid:achievement_id>/", views.AchievementDetailView.as_view(), name="detail"),
    path("<uuid:achievement_id>/feature/", views.FeatureView.as_view(), name="feature"),
    path("<uuid:achievement_id>/evidence/", views.EvidenceUploadView.as_view(), name="evidence"),
    path("<uuid:achievement_id>/resubmit/", views.ResubmitView.as_view(), name="resubmit"),
    path("<uuid:achievement_id>/verify/", views.VerifyView.as_view(), name="verify"),
    path("<uuid:achievement_id>/reject/", views.RejectView.as_view(), name="reject"),
    path("<uuid:achievement_id>/request-information/", views.RequestInformationView.as_view(), name="request-information"),
    path("<uuid:achievement_id>/history/", views.HistoryView.as_view(), name="history"),
]
