"""One pagination shape for every list endpoint, wrapped in the project's envelope."""
from common.pagination import StandardPagination


class SocialPagination(StandardPagination):
    """Shared page shape from common; Social keeps its smaller page sizes."""

    page_size = 10
    max_page_size = 50


class CommentPagination(SocialPagination):
    page_size = 10
