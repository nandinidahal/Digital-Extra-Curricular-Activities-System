from django.urls import path

from . import views

app_name = "announcements"

urlpatterns = [
    path("", views.AnnouncementListCreateView.as_view(), name="list"),
    path("public/", views.PublicAnnouncementListView.as_view(), name="public"),
    path("search/", views.AnnouncementSearchView.as_view(), name="search"),
    path("me/", views.MyAnnouncementsView.as_view(), name="me"),
    path("me/drafts/", views.MyAnnouncementsView.as_view(status_filter="draft"), name="me-drafts"),
    path("me/published/", views.MyAnnouncementsView.as_view(status_filter="published"), name="me-published"),
    path("me/archived/", views.MyAnnouncementsView.as_view(status_filter="archived"), name="me-archived"),
    path("bookmarks/", views.BookmarkListView.as_view(), name="bookmarks"),
    path("reports/", views.ReportListView.as_view(), name="reports"),
    path("reports/<uuid:report_id>/", views.ReportDetailView.as_view(), name="report-detail"),
    path("slug/<slug:slug>/", views.AnnouncementBySlugView.as_view(), name="by-slug"),
    path("<uuid:announcement_id>/", views.AnnouncementDetailView.as_view(), name="detail"),
    path("<uuid:announcement_id>/publish/", views.PublishView.as_view(), name="publish"),
    path("<uuid:announcement_id>/archive/", views.ArchiveView.as_view(), name="archive"),
    path("<uuid:announcement_id>/restore/", views.RestoreView.as_view(), name="restore"),
    path("<uuid:announcement_id>/bookmark/", views.BookmarkView.as_view(), name="bookmark"),
    path("<uuid:announcement_id>/report/", views.ReportCreateView.as_view(), name="report"),
]
