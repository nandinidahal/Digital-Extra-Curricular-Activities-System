from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from achievements import selectors as achievement_selectors
from achievements.serializers import OwnerAchievementSerializer, PublicAchievementSerializer
from friends.models import Friendship
from friends.selectors import blocked_id_subqueries, mutual_friends
from friends.services import get_relationship

from . import feed, services
from profiles.models import UserProfile
from .models import Comment, CommentLike, Notification, Post, PostLike, Visibility
from .pagination import FeedCursorPagination, NotificationCursorPagination, StandardPagination
from .serializers import (CommentSerializer, CommentWriteSerializer, NotificationSerializer,
                          PostSerializer, PostWriteSerializer, ProfileSerializer, ProfileUpdateSerializer,
                          ShareSerializer, UserBriefSerializer)
from .visibility import (annotate_for_viewer, can_view_user_content, get_visible_post_or_404, visible_posts,
                         visible_posts_q)

User = get_user_model()
WRITE_PARSERS = [MultiPartParser, FormParser, JSONParser]


def _post_response(request, post_id, status_code=200):
    post = annotate_for_viewer(visible_posts(request.user).filter(pk=post_id), request.user).first()
    return Response(PostSerializer(post, context={"request": request}).data, status=status_code)


# ---------------------------------------------------------------- home + feed
class FeedView(GenericAPIView):
    """
    GET /api/social/feed/?mode=latest|ranked&scope=all|friends
    latest: cursor pagination ({next, previous, results}); ranked: page-number pagination.
    """
    serializer_class = PostSerializer

    def get(self, request):
        mode = request.query_params.get("mode", "latest")
        scope = request.query_params.get("scope", "all")
        if scope not in ("all", "friends"):
            scope = "all"
        ctx = {"request": request}
        if mode == "ranked":
            paginator = StandardPagination()
            page = paginator.paginate_queryset(feed.ranked_feed(request.user, scope), request, view=self)
            return paginator.get_paginated_response(PostSerializer(page, many=True, context=ctx).data)
        paginator = FeedCursorPagination()
        page = paginator.paginate_queryset(feed.latest_feed(request.user, scope), request, view=self)
        return paginator.get_paginated_response(PostSerializer(page, many=True, context=ctx).data)


class HomeView(APIView):
    """One call for the landing page chrome: badges + suggestions. The feed is loaded separately."""

    def get(self, request):
        from friends.models import FriendRequest, RequestStatus
        from friends.suggestions import suggest_friends
        from messaging.selectors import unread_message_count

        user = request.user
        ctx = {"request": request}
        suggestions = suggest_friends(user, limit=5)
        return Response({
            "me": UserBriefSerializer(User.objects.select_related("user_profile").get(pk=user.pk), context=ctx).data,
            "unread_notifications": Notification.objects.filter(recipient=user, is_read=False).count(),
            "pending_friend_requests": FriendRequest.objects.filter(
                receiver=user, status=RequestStatus.PENDING, is_ignored=False).count(),
            "unread_messages": unread_message_count(user),
            "suggested_friends": [
                {"user": UserBriefSerializer(s["user"], context=ctx).data, "reasons": s["reasons"]}
                for s in suggestions
            ],
        })


# ---------------------------------------------------------------- posts
class PostViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                  mixins.DestroyModelMixin, viewsets.GenericViewSet):
    parser_classes = WRITE_PARSERS
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "social_write"

    def get_throttles(self):
        # reads are never throttled by the write scope
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return []
        return super().get_throttles()

    def get_queryset(self):
        user = self.request.user
        if self.action in ("update", "partial_update", "destroy"):
            return Post.objects.filter(author=user)          # only the author can modify; others get 404
        return annotate_for_viewer(visible_posts(user), user)  # everyone else: strictly visible posts

    def get_serializer_class(self):
        return PostWriteSerializer if self.action in ("create", "update", "partial_update") else PostSerializer

    def create(self, request, *args, **kwargs):
        s = PostWriteSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        v = s.validated_data
        post = services.create_post(request.user, caption=v["caption"], visibility=v["visibility"], kind=v["kind"],
                                    images=v.get("images", []), achievement=v.get("achievement"),
                                    announcement=v.get("announcement"))
        return _post_response(request, post.pk, status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        post = self.get_object()
        s = PostWriteSerializer(post, data=request.data, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        v = s.validated_data
        services.update_post(post, caption=v.get("caption"), visibility=v.get("visibility"),
                             add_images=v.get("images", []), remove_image_ids=v.get("remove_image_ids", []))
        return _post_response(request, post.pk)

    def perform_destroy(self, instance):
        services.delete_post(instance)

    # ---- likes
    @action(detail=True, methods=["post", "delete"], url_path="like")
    def like(self, request, pk=None):
        fn = services.like_post if request.method == "POST" else services.unlike_post
        post = fn(request.user, int(pk))
        return Response({"liked": request.method == "POST", "like_count": post.like_count})

    @action(detail=True, methods=["get"], url_path="likes", throttle_classes=[])
    def likes(self, request, pk=None):
        post = get_visible_post_or_404(request.user, pk)
        ba, bb = blocked_id_subqueries(request.user)
        qs = (PostLike.objects.filter(post=post).exclude(user_id__in=ba).exclude(user_id__in=bb)
              .select_related("user", "user__user_profile").order_by("-created_at", "-id"))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = UserBriefSerializer([l.user for l in page], many=True, context={"request": request}).data
        return paginator.get_paginated_response(data)

    # ---- comments
    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        if request.method == "POST":
            s = CommentWriteSerializer(data=request.data)
            s.is_valid(raise_exception=True)
            comment = services.add_comment(request.user, int(pk), s.validated_data["body"],
                                           s.validated_data.get("parent"))
            return Response(self._comments(request, Comment.objects.filter(pk=comment.pk))[0],
                            status=status.HTTP_201_CREATED)
        post = get_visible_post_or_404(request.user, pk)
        qs = Comment.objects.filter(post=post, parent__isnull=True)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(self._visible_comments(request, qs), request, view=self)
        return paginator.get_paginated_response(CommentSerializer(page, many=True, context={"request": request}).data)

    @staticmethod
    def _visible_comments(request, qs):
        ba, bb = blocked_id_subqueries(request.user)
        return (qs.exclude(author_id__in=ba).exclude(author_id__in=bb)
                .select_related("author", "author__user_profile")
                .annotate(liked_by_me=Exists(CommentLike.objects.filter(comment=OuterRef("pk"), user=request.user)),
                          replies_total=Count("replies", distinct=True))
                .order_by("created_at", "id"))

    def _comments(self, request, qs):
        return CommentSerializer(self._visible_comments(request, qs), many=True, context={"request": request}).data

    # ---- share
    @action(detail=True, methods=["post"], url_path="share")
    def share(self, request, pk=None):
        s = ShareSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        share = services.share_post(request.user, int(pk), s.validated_data["caption"].strip(),
                                    s.validated_data["visibility"])
        return _post_response(request, share.pk, status.HTTP_201_CREATED)


class CommentViewSet(viewsets.GenericViewSet):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "social_write"
    queryset = Comment.objects.none()

    def get_throttles(self):
        return [] if self.request.method in ("GET", "HEAD", "OPTIONS") else super().get_throttles()

    def _one(self, request, comment_id):
        qs = PostViewSet._visible_comments(request, Comment.objects.filter(pk=comment_id))
        return CommentSerializer(qs.get(), context={"request": request}).data

    def partial_update(self, request, pk=None):
        s = CommentWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.edit_comment(request.user, int(pk), s.validated_data["body"])
        return Response(self._one(request, pk))

    def destroy(self, request, pk=None):
        services.delete_comment(request.user, int(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post", "delete"], url_path="like")
    def like(self, request, pk=None):
        fn = services.like_comment if request.method == "POST" else services.unlike_comment
        comment = fn(request.user, int(pk))
        return Response({"liked": request.method == "POST", "like_count": comment.like_count})

    @action(detail=True, methods=["get"], url_path="replies")
    def replies(self, request, pk=None):
        parent = services.get_comment_for_user(request.user, int(pk))
        qs = PostViewSet._visible_comments(request, Comment.objects.filter(parent=parent))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(CommentSerializer(page, many=True, context={"request": request}).data)


# ---------------------------------------------------------------- profiles
def _get_profile_user(viewer, username):
    target = User.objects.select_related("user_profile").filter(username__iexact=username).first()
    if target is None or not can_view_user_content(viewer, target):
        raise NotFound("User not found.")
    return target


class MyProfileView(APIView):
    parser_classes = WRITE_PARSERS

    def get(self, request):
        return ProfileView().get(request, request.user.username)

    def patch(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        s = ProfileUpdateSerializer(profile, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return ProfileView().get(request, request.user.username)


class ProfileView(APIView):
    def get(self, request, username):
        viewer = request.user
        target = _get_profile_user(viewer, username)
        is_self = target.pk == viewer.pk
        friends_count = Friendship.objects.filter(Q(user_low=target) | Q(user_high=target)).count()
        achievements = (achievement_selectors.owned_by(target) if is_self
                        else achievement_selectors.public_of(target))
        rel = get_relationship(viewer, target)
        stats = {
            "is_self": is_self,
            "friends_count": friends_count,
            "posts_count": visible_posts(viewer).filter(author=target).count(),
            "achievements_count": achievements.count(),
            "mutual_friends_count": 0 if is_self else mutual_friends(viewer, target).count(),
            "relationship": rel,
            "is_friend": rel["state"] == "FRIENDS",
            # Non-friends may message (limited to 4 messages until friends); only blocks stop it.
            "can_message": not is_self and rel["state"] not in ("BLOCKED", "BLOCKED_BY"),
        }
        return Response(ProfileSerializer(target, context={"request": request, "stats": stats}).data)


class ProfilePostsView(GenericAPIView):
    serializer_class = PostSerializer

    def get(self, request, username):
        target = _get_profile_user(request.user, username)
        qs = annotate_for_viewer(visible_posts(request.user).filter(author=target), request.user)
        paginator = FeedCursorPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(PostSerializer(page, many=True, context={"request": request}).data)


class ProfileAchievementsView(GenericAPIView):
    """Achievements shown on a profile; backed by the achievements app (single Achievement model)."""
    serializer_class = PublicAchievementSerializer

    def get(self, request, username):
        target = _get_profile_user(request.user, username)
        is_self = target.pk == request.user.pk
        # private achievements are never exposed to others
        qs = achievement_selectors.owned_by(target) if is_self else achievement_selectors.public_of(target)
        serializer_class = OwnerAchievementSerializer if is_self else PublicAchievementSerializer
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(serializer_class(page, many=True, context={"request": request}).data)


# ---------------------------------------------------------------- notifications
class NotificationViewSet(viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    pagination_class = NotificationCursorPagination
    queryset = Notification.objects.none()

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related("actor", "actor__user_profile")

    def list(self, request):
        qs = self.get_queryset()
        if request.query_params.get("unread") in ("1", "true"):
            qs = qs.filter(is_read=False)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return Response({"unread": self.get_queryset().filter(is_read=False).count()})

    @action(detail=True, methods=["post"], url_path="read")
    def read(self, request, pk=None):
        updated = self.get_queryset().filter(pk=pk).update(is_read=True)
        if not updated:
            raise NotFound("Notification not found.")
        return Response({"read": True})

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        n = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"marked_read": n})
