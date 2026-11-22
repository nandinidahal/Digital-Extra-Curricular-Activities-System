"""
API views of the Social module (all under /api/social/).

Common rules
* Reading endpoints accept visitors; what they see is decided by social.permissions.
* Every write needs a valid JWT. The author/owner always comes from `request.user`.
* Content the viewer may not see answers 404 (private) or 401 (members-only, visitor).
"""
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from accounts.responses import success_response
from common.permissions import IsModerator
from common.relationships import is_blocked_between
from profiles.authentication import OptionalJWTAuthentication

from . import services
from .exceptions import AuthorNotFound, MediaNotFound, NotOwner, ShareNotFound, UploadTooLarge
from .models import Comment, ContentReport, Post, PostShare
from .pagination import CommentPagination, SocialPagination
from .permissions import ReadPublicWriteAuthenticated, is_admin
from .serializers import (
    CommentSerializer,
    CommentWriteSerializer,
    GenericReportWriteSerializer,
    ReportModerationSerializer,
    ReportReviewSerializer,
    ResourceShareWriteSerializer,
    PostSerializer,
    PostWriteSerializer,
    ReportReceiptSerializer,
    ReportWriteSerializer,
    ShareSerializer,
    ShareWriteSerializer,
)
from .throttles import CommentWriteThrottle, InteractionThrottle, PostWriteThrottle, ReportThrottle
from .validators import MULTIPART_OVERHEAD_BYTES, max_image_bytes, max_images_per_post


class SocialAPIView(APIView):
    """Optional JWT: a missing/expired token means "visitor", and writes then answer 401."""

    authentication_classes = [OptionalJWTAuthentication]
    permission_classes = [ReadPublicWriteAuthenticated]
    parser_classes = [JSONParser]

    @property
    def ctx(self):
        return {"request": self.request}


class AuthenticatedAPIView(SocialAPIView):
    permission_classes = [IsAuthenticated]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _post_data(request, post_id):
    post = services.annotate_posts(services.feed_posts(request.user).filter(pk=post_id), request.user).first()
    if post is None:  # e.g. the author just made it private and an admin edited it: fall back
        post = services.annotate_posts(services.readable_posts(request.user).filter(pk=post_id), request.user).get()
    return PostSerializer(post, context={"request": request}).data


def _comment_data(request, comment_id):
    comment = services.annotate_comments(Comment.objects.filter(pk=comment_id), request.user).get()
    return CommentSerializer(comment, context={"request": request}).data


def _paginated_posts(request, queryset, paginator_class=SocialPagination):
    queryset = services.apply_post_filters(queryset, request.query_params)
    queryset = services.annotate_posts(queryset, request.user)
    paginator = paginator_class()
    page = paginator.paginate_queryset(queryset, request, view=None)
    data = PostSerializer(page, many=True, context={"request": request}).data
    return paginator.get_paginated_response(data)


def _check_upload_size(request):
    """Refuse oversized multipart bodies from the Content-Length header, before parsing them."""
    try:
        length = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    limit = max_images_per_post() * max_image_bytes() + MULTIPART_OVERHEAD_BYTES
    if length > limit:
        raise UploadTooLarge()


def _require_owner(user, owner_id):
    if owner_id != user.pk:
        raise NotOwner()


# ---------------------------------------------------------------------------
# Posts and feeds
# ---------------------------------------------------------------------------
class PostListCreateView(SocialAPIView):
    """
    GET  /api/social/posts/  -> every post the viewer may see, newest first
    POST /api/social/posts/  -> create a post (JSON or multipart)
    """

    parser_classes = [JSONParser, MultiPartParser, FormParser]
    throttle_classes = [PostWriteThrottle]

    def get(self, request):
        return _paginated_posts(request, services.feed_posts(request.user))

    def post(self, request):
        _check_upload_size(request)
        serializer = PostWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = services.create_post(request.user, serializer.validated_data)
        return success_response({"post": _post_data(request, post.pk)}, "Post created.", status.HTTP_201_CREATED)


class FeedView(SocialAPIView):
    """
    GET /api/social/feed/?scope=all|friends&post_type=&shared_type=announcement|achievement
    Own posts + friends' posts (incl. friends-only) + public/members-only posts + shared
    announcements/achievements, newest first. Blocked users never appear. scope=friends keeps
    only the viewer's own and friends' posts (needs login).
    """

    def get(self, request):
        scope = request.query_params.get("scope", "all")
        return _paginated_posts(request, services.scoped_feed(request.user, scope))


class PostDetailView(SocialAPIView):
    """GET / PATCH / DELETE /api/social/posts/<post_id>/"""

    parser_classes = [JSONParser, MultiPartParser, FormParser]
    throttle_classes = [PostWriteThrottle]

    def get(self, request, post_id):
        post = services.get_post(request.user, post_id, annotated=True)
        return success_response({"post": PostSerializer(post, context=self.ctx).data})

    def patch(self, request, post_id):
        post = services.get_post(request.user, post_id, write=True)
        _require_owner(request.user, post.author_id)
        _check_upload_size(request)
        serializer = PostWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_post(post, serializer.validated_data)
        return success_response({"post": _post_data(request, post.pk)}, "Post updated.")

    def delete(self, request, post_id):
        post = services.get_post(request.user, post_id, write=True)
        _require_owner(request.user, post.author_id)
        services.delete_post(post)
        return success_response(message="Post deleted.")


class PostMediaDetailView(AuthenticatedAPIView):
    """DELETE /api/social/posts/<post_id>/media/<media_id>/  -> remove one attachment (owner only)"""

    def delete(self, request, post_id, media_id):
        post = services.get_post(request.user, post_id, write=True)
        _require_owner(request.user, post.author_id)
        media = post.media.filter(pk=media_id).first()
        if media is None:
            raise MediaNotFound()
        services.remove_post_media(post, media)
        return success_response({"post": _post_data(request, post.pk)}, "Attachment removed.")


class UserPostsView(SocialAPIView):
    """GET /api/social/users/<user_id>/posts/  -> that user's posts the viewer may see"""

    def get(self, request, user_id):
        author = get_user_model().objects.filter(pk=user_id, is_active=True).first()
        if author is None or (
            request.user.is_authenticated and not is_admin(request.user) and is_blocked_between(request.user, author)
        ):
            raise AuthorNotFound()
        queryset = services.readable_posts(request.user).filter(author_id=user_id)
        return _paginated_posts(request, queryset)


class MyPostsView(AuthenticatedAPIView):
    """GET /api/social/me/posts/  -> own posts, every visibility, newest first"""

    def get(self, request):
        queryset = Post.objects.filter(author=request.user, is_deleted=False)
        return _paginated_posts(request, queryset)


# ---------------------------------------------------------------------------
# Post likes
# ---------------------------------------------------------------------------
class PostLikeView(AuthenticatedAPIView):
    """POST like (201 new, 200 already liked) / DELETE unlike (always 200). Both idempotent."""

    throttle_classes = [InteractionThrottle]

    def post(self, request, post_id):
        post = services.get_post(request.user, post_id, write=True)
        created = services.like_post(request.user, post)
        return success_response(
            services.post_like_state(request.user, post.pk),
            "Post liked." if created else "You already liked this post.",
            status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, post_id):
        post = services.get_post(request.user, post_id, write=True)
        services.unlike_post(request.user, post)
        return success_response(services.post_like_state(request.user, post.pk), "Like removed.")


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------
class PostCommentsView(SocialAPIView):
    """
    GET  /api/social/posts/<post_id>/comments/  -> top-level comments, oldest first, paginated
    POST /api/social/posts/<post_id>/comments/  -> new top-level comment
    """

    throttle_classes = [CommentWriteThrottle]

    def get(self, request, post_id):
        post = services.get_post(request.user, post_id)
        queryset = services.annotate_comments(services.visible_top_level_comments(post, request.user), request.user)
        paginator = CommentPagination()
        page = paginator.paginate_queryset(queryset, request, view=None)
        return paginator.get_paginated_response(CommentSerializer(page, many=True, context=self.ctx).data)

    def post(self, request, post_id):
        post = services.get_post(request.user, post_id, write=True)
        serializer = CommentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = services.create_comment(request.user, post, serializer.validated_data["content"])
        return success_response(
            {"comment": _comment_data(request, comment.pk)}, "Comment added.", status.HTTP_201_CREATED
        )


class CommentDetailView(AuthenticatedAPIView):
    """PATCH / DELETE /api/social/comments/<comment_id>/  (author only)"""

    throttle_classes = [CommentWriteThrottle]

    def patch(self, request, comment_id):
        comment = services.get_comment(request.user, comment_id, write=True)
        _require_owner(request.user, comment.author_id)
        serializer = CommentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_comment(comment, serializer.validated_data["content"])
        return success_response({"comment": _comment_data(request, comment.pk)}, "Comment updated.")

    def delete(self, request, comment_id):
        comment = services.get_comment(request.user, comment_id, write=True)
        _require_owner(request.user, comment.author_id)
        services.delete_comment(comment)
        return success_response(message="Comment deleted.")


class CommentReplyView(AuthenticatedAPIView):
    """POST /api/social/comments/<comment_id>/reply/"""

    throttle_classes = [CommentWriteThrottle]

    def post(self, request, comment_id):
        parent = services.get_comment(request.user, comment_id, write=True)
        serializer = CommentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reply = services.create_comment(
            request.user, parent.post, serializer.validated_data["content"], parent=parent
        )
        return success_response(
            {"comment": _comment_data(request, reply.pk)}, "Reply added.", status.HTTP_201_CREATED
        )


class CommentRepliesView(SocialAPIView):
    """GET /api/social/comments/<comment_id>/replies/  -> direct replies, oldest first, paginated"""

    def get(self, request, comment_id):
        parent = services.get_comment(request.user, comment_id, allow_deleted=True)
        queryset = services.annotate_comments(services.visible_replies(parent, request.user), request.user)
        paginator = CommentPagination()
        page = paginator.paginate_queryset(queryset, request, view=None)
        return paginator.get_paginated_response(CommentSerializer(page, many=True, context=self.ctx).data)


class CommentLikeView(AuthenticatedAPIView):
    throttle_classes = [InteractionThrottle]

    def post(self, request, comment_id):
        comment = services.get_comment(request.user, comment_id, write=True)
        created = services.like_comment(request.user, comment)
        return success_response(
            services.comment_like_state(request.user, comment.pk),
            "Comment liked." if created else "You already liked this comment.",
            status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, comment_id):
        comment = services.get_comment(request.user, comment_id, write=True)
        services.unlike_comment(request.user, comment)
        return success_response(services.comment_like_state(request.user, comment.pk), "Like removed.")


# ---------------------------------------------------------------------------
# Shares
# ---------------------------------------------------------------------------
def _share_page_payload(request, shares):
    """Serialize shares with their original posts, fetched in ONE annotated query."""
    ids = [share.original_post_id for share in shares]
    posts = services.annotate_posts(services.feed_posts(request.user).filter(pk__in=ids), request.user)
    post_map = {
        post.pk: PostSerializer(post, context={"request": request}).data for post in posts
    }
    return ShareSerializer(shares, many=True, context={"request": request, "post_map": post_map}).data


class PostShareView(AuthenticatedAPIView):
    """POST /api/social/posts/<post_id>/share/  body: {"caption": "optional"}"""

    throttle_classes = [InteractionThrottle]

    def post(self, request, post_id):
        post = services.get_post(request.user, post_id, write=True)
        serializer = ShareWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        share = services.share_post(request.user, post, serializer.validated_data.get("caption", ""))
        data = _share_page_payload(request, [share])[0]
        data["share_count"] = post.shares.count()
        return success_response({"share": data}, "Post shared.", status.HTTP_201_CREATED)


class ShareDetailView(AuthenticatedAPIView):
    """DELETE /api/social/shares/<share_id>/  (the sharer only)"""

    def delete(self, request, share_id):
        share = PostShare.objects.filter(pk=share_id).first()
        if share is None:
            raise ShareNotFound()
        _require_owner(request.user, share.user_id)
        share.delete()
        return success_response(message="Share removed.")


class MySharesView(AuthenticatedAPIView):
    """GET /api/social/me/shares/"""

    def get(self, request):
        queryset = PostShare.objects.filter(user=request.user)
        paginator = SocialPagination()
        page = paginator.paginate_queryset(queryset, request, view=None)
        return paginator.get_paginated_response(_share_page_payload(request, page))


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
class PostReportView(AuthenticatedAPIView):
    """POST /api/social/posts/<post_id>/report/"""

    throttle_classes = [ReportThrottle]

    def post(self, request, post_id):
        post = services.get_post(request.user, post_id, write=True)
        serializer = ReportWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = services.report_content(request.user, post=post, **serializer.validated_data)
        return success_response(
            {"report": ReportReceiptSerializer(report).data},
            "Thank you. Your report was submitted and will be reviewed.",
            status.HTTP_201_CREATED,
        )


class CommentReportView(AuthenticatedAPIView):
    """POST /api/social/comments/<comment_id>/report/"""

    throttle_classes = [ReportThrottle]

    def post(self, request, comment_id):
        comment = services.get_comment(request.user, comment_id, write=True)
        serializer = ReportWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = services.report_content(request.user, comment=comment, **serializer.validated_data)
        return success_response(
            {"report": ReportReceiptSerializer(report).data},
            "Thank you. Your report was submitted and will be reviewed.",
            status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Generic share and report endpoints, report moderation
# ---------------------------------------------------------------------------
class ResourceShareView(AuthenticatedAPIView):
    """
    POST /api/social/shares/
    {"resource_type": "post" | "announcement" | "achievement", "resource_id": "<uuid>",
     "caption": "optional", "visibility": "public|members_only|friends"}
    A post share is a PostShare row (unchanged behaviour). An announcement/achievement share is a
    new post that REFERENCES the original (shown in feeds; the original's visibility is re-checked).
    """

    throttle_classes = [InteractionThrottle]

    def post(self, request):
        serializer = ResourceShareWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        caption = data.get("caption", "")
        if data["resource_type"] == "post":
            post = services.get_post(request.user, data["resource_id"], write=True)
            share = services.share_post(request.user, post, caption)
            payload = _share_page_payload(request, [share])[0]
            payload["share_count"] = post.shares.count()
            return success_response({"share": payload}, "Post shared.", status.HTTP_201_CREATED)
        post = services.share_resource(
            request.user, data["resource_type"], data["resource_id"], caption,
            data.get("visibility", Post.Visibility.PUBLIC),
        )
        return success_response(
            {"post": _post_data(request, post.pk)}, f"{data['resource_type'].capitalize()} shared.", status.HTTP_201_CREATED
        )


class ReportListCreateView(AuthenticatedAPIView):
    """
    POST /api/social/reports/  {"content_type": "post"|"comment", "object_id", "reason", "description"}
    GET  /api/social/reports/?status=pending   (moderators only)
    """

    throttle_classes = [ReportThrottle]

    def get(self, request):
        if not IsModerator().has_permission(request, self):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Only moderators can review reports.")
        queryset = ContentReport.objects.select_related("reporter", "reviewed_by", "post", "comment")
        status_filter = request.query_params.get("status")
        if status_filter in ContentReport.Status.values:
            queryset = queryset.filter(status=status_filter)
        paginator = SocialPagination()
        page = paginator.paginate_queryset(queryset, request, view=None)
        return paginator.get_paginated_response(ReportModerationSerializer(page, many=True).data)

    def post(self, request):
        serializer = GenericReportWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        content_type, object_id = data.pop("content_type"), data.pop("object_id")
        if content_type == ContentReport.ContentType.POST:
            target = {"post": services.get_post(request.user, object_id, write=True)}
        else:
            target = {"comment": services.get_comment(request.user, object_id, write=True)}
        report = services.report_content(request.user, **target, **data)
        return success_response(
            {"report": ReportReceiptSerializer(report).data},
            "Thank you. Your report was submitted and will be reviewed.",
            status.HTTP_201_CREATED,
        )


class ReportModerationView(AuthenticatedAPIView):
    """GET / PATCH /api/social/reports/<id>/  (moderators) {"status", "review_comments", "action": "none"|"content_removed"}"""

    permission_classes = [IsAuthenticated, IsModerator]

    def _get(self, report_id):
        report = ContentReport.objects.select_related("reporter", "reviewed_by", "post", "comment").filter(pk=report_id).first()
        if report is None:
            from common.exceptions import ResourceNotFound

            raise ResourceNotFound("This report does not exist.", code="report_not_found")
        return report

    def get(self, request, report_id):
        return success_response({"report": ReportModerationSerializer(self._get(report_id)).data})

    def patch(self, request, report_id):
        self._get(report_id)
        serializer = ReportReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.review_report(request.user, report_id, **serializer.validated_data)
        return success_response({"report": ReportModerationSerializer(self._get(report_id)).data}, "Report updated.")
