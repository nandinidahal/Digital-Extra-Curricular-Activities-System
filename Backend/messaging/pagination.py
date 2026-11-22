"""
* Conversations / search: page-number pagination, same envelope as Friends and Social.
* Message history: CURSOR pagination (newest first). Stable while new messages arrive - a
  page-number scheme would shift and repeat messages every time someone sends one.
"""
from rest_framework.pagination import CursorPagination

from accounts.responses import success_response
from friends.pagination import FriendsPagination


class ConversationPagination(FriendsPagination):
    page_size = 20


class SearchPagination(FriendsPagination):
    page_size = 20


class MessageCursorPagination(CursorPagination):
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = ("-created_at", "-id")

    def get_paginated_response(self, data):
        return success_response(
            {
                "results": data,
                "pagination": {
                    "page_size": self.get_page_size(self.request),
                    "next": self.get_next_link(),  # older messages
                    "previous": self.get_previous_link(),  # newer messages
                },
            }
        )
