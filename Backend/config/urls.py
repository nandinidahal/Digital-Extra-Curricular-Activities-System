"""Root URL configuration. Every app is mounted here and nowhere else."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/profile/", include("profiles.urls")),
    path("api/friends/", include("friends.urls")),
    path("api/messaging/", include("messaging.urls")),
    path("api/social/", include("social.urls")),
    # announcements.urls and achievements.urls define their own "announcements/", "achievements/"
    # and "users/<id>/achievements/" prefixes, so they are mounted at /api/.
    path("api/", include("announcements.urls")),
    path("api/", include("achievements.urls")),
]

if settings.DEBUG:  # profile pictures / cover images / post images use MEDIA_URL in development
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
