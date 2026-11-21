from django.urls import path

from . import views

# Intended mount point (NOT done yet - see API_DOCUMENTATION.md):
#     path("api/", include("announcements.urls"))
# Static routes come before <int:pk> for readability (an int converter never matches them anyway).
urlpatterns = [
    path("announcements/", views.AnnouncementListCreateView.as_view(), name="announcement-list"),
    path("announcements/landing/", views.LandingView.as_view(), name="announcement-landing"),
    path("announcements/latest/", views.LatestAnnouncementsView.as_view(), name="announcement-latest"),
    path("announcements/featured/", views.FeaturedAnnouncementsView.as_view(), name="announcement-featured"),
    path("announcements/recommended/", views.RecommendedAnnouncementsView.as_view(), name="announcement-recommended"),
    path("announcements/upcoming/", views.UpcomingEventsView.as_view(), name="announcement-upcoming"),
    path("announcements/deadlines/", views.UpcomingDeadlinesView.as_view(), name="announcement-deadlines"),
    path("announcements/important/", views.ImportantAnnouncementsView.as_view(), name="announcement-important"),
    path("announcements/search/", views.SearchAnnouncementsView.as_view(), name="announcement-search"),
    path("announcements/categories/", views.CategoryListView.as_view(), name="announcement-categories"),
    path("announcements/my-announcements/", views.MyAnnouncementsView.as_view(), name="announcement-mine"),
    path("announcements/drafts/", views.MyDraftsView.as_view(), name="announcement-drafts"),
    path("announcements/bookmarks/", views.BookmarkedAnnouncementsView.as_view(), name="announcement-bookmarks"),
    path("announcements/authors/<int:user_id>/", views.AuthorAnnouncementsView.as_view(), name="announcement-by-author"),
    path("announcements/shared/<uuid:share_id>/", views.SharedAnnouncementView.as_view(), name="announcement-shared"),
    path("announcements/<int:pk>/", views.AnnouncementDetailView.as_view(), name="announcement-detail"),
    path("announcements/<int:pk>/bookmark/", views.BookmarkView.as_view(), name="announcement-bookmark"),
    path("announcements/<int:pk>/share/", views.ShareInfoView.as_view(), name="announcement-share"),
    path("announcements/<int:pk>/attachment/", views.AttachmentDownloadView.as_view(), name="announcement-attachment"),
]
