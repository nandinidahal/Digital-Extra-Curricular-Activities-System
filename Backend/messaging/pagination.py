from rest_framework.pagination import CursorPagination


class MessageCursorPagination(CursorPagination):
    """Newest first; the client asks for `next` to load older messages."""
    ordering = "-id"
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100
