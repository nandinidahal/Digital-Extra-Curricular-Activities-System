from rest_framework.pagination import CursorPagination, PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 50


class FeedCursorPagination(CursorPagination):
    """Keyset pagination on (created_at, id): constant cost per page, no skipped/duplicated rows
    when new posts arrive while the user is scrolling."""
    ordering = ("-created_at", "-id")
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 30


class NotificationCursorPagination(FeedCursorPagination):
    page_size = 20
