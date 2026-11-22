"""
Who may see / touch what. All rules live here so views, serializers and tests
share one definition.

Viewer levels (same idea as profiles.permissions):
    owner   - the viewer wrote the post
    admin   - viewer has the `admin` role in Accounts. Admins may READ any non-deleted
              post (detail, comments, an author's posts) for moderation, but they take
              part in the feed and in write interactions like everybody else.
    friend  - authenticated user who is a friend of the author (Friends module)
    member  - any other authenticated user
    visitor - anonymous

Post visibility
    public        everyone
    members_only  logged-in users (visitors get 401)
    friends       the author's friends (visitors get 401, other members 404)
    private       the author only (404 for everybody else)

Blocking (Friends module, either direction): the other person's posts, comments and
interactions are invisible (404) to a logged-in viewer. Admin moderation reads are exempt.
"""
from django.db.models import Q
from rest_framework.permissions import BasePermission

from accounts.models import User
from common.relationships import are_friends, friend_ids, hidden_user_ids, is_blocked_between

from .exceptions import AuthenticationRequired, PostNotFound
from .models import Post


def is_authenticated(user):
    return bool(user and user.is_authenticated)


def is_admin(user):
    return is_authenticated(user) and user.role == User.Role.ADMIN


def visibility_filter(user):
    """Q object: posts `user` may interact with / see in feeds (no admin override)."""
    if not is_authenticated(user):
        return Q(visibility=Post.Visibility.PUBLIC)
    allowed = Q(visibility__in=[Post.Visibility.PUBLIC, Post.Visibility.MEMBERS_ONLY]) | Q(author=user)
    friends = friend_ids(user)
    if friends:
        allowed |= Q(visibility=Post.Visibility.FRIENDS, author_id__in=friends)
    hidden = hidden_user_ids(user)
    if hidden:
        allowed &= ~Q(author_id__in=hidden)
    return allowed


def check_post_visible(user, post, *, admin_override):
    """
    Single-object version of `visibility_filter`. Raises:
      AuthenticationRequired (401) - members-only / friends-only post, viewer is a visitor
      PostNotFound (404)           - private / not a friend / blocked (existence is not revealed)
    """
    if is_authenticated(user):
        if post.author_id == user.pk:
            return
        if admin_override and is_admin(user):
            return
        if is_blocked_between(user, post.author_id):
            raise PostNotFound()
    if post.visibility == Post.Visibility.PUBLIC:
        return
    if post.visibility in (Post.Visibility.MEMBERS_ONLY, Post.Visibility.FRIENDS):
        if not is_authenticated(user):
            raise AuthenticationRequired()
        if post.visibility == Post.Visibility.MEMBERS_ONLY or are_friends(user, post.author_id):
            return
    raise PostNotFound()


class ReadPublicWriteAuthenticated(BasePermission):
    """Safe methods: anyone (visibility is enforced per object). Writes: logged-in users."""

    message = "Authentication credentials were not provided."

    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return is_authenticated(request.user)
