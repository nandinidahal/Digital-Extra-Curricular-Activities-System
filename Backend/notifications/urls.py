from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="list"),
    path("unread-count/", views.UnreadCountView.as_view(), name="unread-count"),
    path("read-all/", views.MarkAllReadView.as_view(), name="read-all"),
    path("clear/", views.ClearNotificationsView.as_view(), name="clear"),
    path("preferences/", views.PreferencesView.as_view(), name="preferences"),
    path("<uuid:notification_id>/", views.NotificationDetailView.as_view(), name="detail"),
    path("<uuid:notification_id>/read/", views.MarkReadView.as_view(), name="read"),
    path("<uuid:notification_id>/unread/", views.MarkUnreadView.as_view(), name="unread"),
]
