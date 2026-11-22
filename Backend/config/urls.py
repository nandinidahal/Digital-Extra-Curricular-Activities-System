from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def json_not_found(request, exception=None):
    """Return JSON (not an HTML page) so the React app can always parse the response."""
    return JsonResponse(
        {"success": False, "message": "Not found.", "code": "not_found", "errors": {}}, status=404
    )


def json_server_error(request):
    return JsonResponse(
        {
            "success": False,
            "message": "Something went wrong on our side. Please try again later.",
            "code": "server_error",
            "errors": {},
        },
        status=500,
    )


handler404 = json_not_found
handler500 = json_server_error

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/profiles/", include("profiles.urls")),
    path("api/friends/", include("friends.urls")),
    path("api/social/", include("social.urls")),
    path("api/messaging/", include("messaging.urls")),
    path("api/health/", include("common.urls")),
    path("api/announcements/", include("announcements.urls")),
    path("api/categories/", include("announcements.category_urls")),
    path("api/achievements/", include("achievements.urls")),
    path("api/achievement-categories/", include("achievements.category_urls")),
    path("api/notifications/", include("notifications.urls")),
]

# Development only: serve uploaded media. In production the web server or the
# object-storage/CDN serves them instead.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
