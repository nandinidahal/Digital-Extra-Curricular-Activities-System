"""One page shape for every list endpoint, inside the project's success envelope."""
from rest_framework.pagination import PageNumberPagination

from accounts.responses import success_response


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return success_response(
            {
                "results": data,
                "pagination": {
                    "count": self.page.paginator.count,
                    "page": self.page.number,
                    "page_size": self.get_page_size(self.request),
                    "total_pages": self.page.paginator.num_pages,
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                },
            }
        )


def paginate(request, queryset, serializer_class, *, context=None, pagination_class=StandardPagination):
    """Paginate + serialize + envelope in one call (keeps APIViews thin)."""
    paginator = pagination_class()
    page = paginator.paginate_queryset(queryset, request, view=None)
    ctx = {"request": request, **(context or {})}
    return paginator.get_paginated_response(serializer_class(page, many=True, context=ctx).data)
