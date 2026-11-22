from django.urls import path

from . import views

app_name = "friends"

urlpatterns = [
    # Friend requests
    path("requests/", views.SendFriendRequestView.as_view(), name="request-send"),
    path("requests/received/", views.ReceivedRequestsView.as_view(), name="requests-received"),
    path("requests/sent/", views.SentRequestsView.as_view(), name="requests-sent"),
    path("requests/<uuid:request_id>/accept/", views.AcceptFriendRequestView.as_view(), name="request-accept"),
    path("requests/<uuid:request_id>/reject/", views.RejectFriendRequestView.as_view(), name="request-reject"),
    path("requests/<uuid:request_id>/cancel/", views.CancelFriendRequestView.as_view(), name="request-cancel"),
    # Friendships
    path("", views.FriendListView.as_view(), name="list"),
    path("count/", views.FriendCountView.as_view(), name="count"),
    path("status/<uuid:user_id>/", views.FriendStatusView.as_view(), name="status"),
    path("mutual/<uuid:user_id>/", views.MutualFriendsView.as_view(), name="mutual"),
    path("discover/", views.DiscoverUsersView.as_view(), name="discover"),
    # Blocking
    path("blocked/", views.BlockedListCreateView.as_view(), name="blocked"),
    path("blocked/status/<uuid:user_id>/", views.BlockStatusView.as_view(), name="block-status"),
    path("blocked/<uuid:user_id>/", views.BlockedDetailView.as_view(), name="unblock"),
    # Must stay last among the <uuid> routes
    path("<uuid:user_id>/", views.FriendDetailView.as_view(), name="remove"),
]
