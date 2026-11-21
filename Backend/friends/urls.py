from django.urls import path

from . import views

urlpatterns = [
    path("", views.FriendListView.as_view(), name="friends-list"),
    path("suggestions/", views.SuggestionsView.as_view(), name="friends-suggestions"),
    path("status/<int:user_id>/", views.FriendStatusView.as_view(), name="friends-status"),
    path("mutual/<str:username>/", views.MutualFriendsView.as_view(), name="friends-mutual"),
    path("requests/", views.SendRequestView.as_view(), name="friend-request-send"),
    path("requests/incoming/", views.IncomingRequestsView.as_view(), name="friend-requests-incoming"),
    path("requests/outgoing/", views.OutgoingRequestsView.as_view(), name="friend-requests-outgoing"),
    path("requests/<int:request_id>/accept/", views.RequestActionView.as_view(action_name="accept"), name="friend-request-accept"),
    path("requests/<int:request_id>/reject/", views.RequestActionView.as_view(action_name="reject"), name="friend-request-reject"),
    path("requests/<int:request_id>/ignore/", views.RequestActionView.as_view(action_name="ignore"), name="friend-request-ignore"),
    path("requests/<int:request_id>/cancel/", views.RequestActionView.as_view(action_name="cancel"), name="friend-request-cancel"),
    path("blocks/", views.BlockListView.as_view(), name="blocks"),
    path("blocks/<int:user_id>/", views.BlockDetailView.as_view(), name="block-detail"),
    path("<int:user_id>/", views.FriendDetailView.as_view(), name="friend-detail"),
]
