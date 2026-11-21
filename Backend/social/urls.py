from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("posts", views.PostViewSet, basename="social-post")
router.register("comments", views.CommentViewSet, basename="social-comment")
router.register("notifications", views.NotificationViewSet, basename="social-notification")

urlpatterns = [
    path("home/", views.HomeView.as_view(), name="social-home"),
    path("feed/", views.FeedView.as_view(), name="social-feed"),
    path("profiles/me/", views.MyProfileView.as_view(), name="social-profile-me"),
    path("profiles/<str:username>/", views.ProfileView.as_view(), name="social-profile"),
    path("profiles/<str:username>/posts/", views.ProfilePostsView.as_view(), name="social-profile-posts"),
    path("profiles/<str:username>/achievements/", views.ProfileAchievementsView.as_view(),
         name="social-profile-achievements"),
] + router.urls
