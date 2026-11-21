from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Page-number pagination shared by every list endpoint.

    NOTE: ``achievements.views`` already imports this class from ``announcements.pagination``,
    so the name and location must stay stable.
    """

    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 50
