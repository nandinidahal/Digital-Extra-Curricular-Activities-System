from django.urls import path

from . import views

app_name = "social"

urlpatterns = [
    # posts and feeds
    path("posts/", views.PostListCreateView.as_view(), name="post-list"),
    path("feed/", views.FeedView.as_view(), name="feed"),
    path("posts/<uuid:post_id>/", views.PostDetailView.as_view(), name="post-detail"),
    path("posts/<uuid:post_id>/media/<uuid:media_id>/", views.PostMediaDetailView.as_view(), name="post-media"),
    path("users/<uuid:user_id>/posts/", views.UserPostsView.as_view(), name="user-posts"),
    path("me/posts/", views.MyPostsView.as_view(), name="my-posts"),
    # post likes
    path("posts/<uuid:post_id>/like/", views.PostLikeView.as_view(), name="post-like"),
    # comments
    path("posts/<uuid:post_id>/comments/", views.PostCommentsView.as_view(), name="post-comments"),
    path("comments/<uuid:comment_id>/", views.CommentDetailView.as_view(), name="comment-detail"),
    path("comments/<uuid:comment_id>/reply/", views.CommentReplyView.as_view(), name="comment-reply"),
    path("comments/<uuid:comment_id>/replies/", views.CommentRepliesView.as_view(), name="comment-replies"),
    path("comments/<uuid:comment_id>/like/", views.CommentLikeView.as_view(), name="comment-like"),
    # shares
    path("posts/<uuid:post_id>/share/", views.PostShareView.as_view(), name="post-share"),
    path("shares/<uuid:share_id>/", views.ShareDetailView.as_view(), name="share-detail"),
    path("me/shares/", views.MySharesView.as_view(), name="my-shares"),
    path("shares/", views.ResourceShareView.as_view(), name="share-create"),
    # reports
    path("posts/<uuid:post_id>/report/", views.PostReportView.as_view(), name="post-report"),
    path("comments/<uuid:comment_id>/report/", views.CommentReportView.as_view(), name="comment-report"),
    path("reports/", views.ReportListCreateView.as_view(), name="reports"),
    path("reports/<uuid:report_id>/", views.ReportModerationView.as_view(), name="report-detail"),
]
