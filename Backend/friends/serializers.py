"""
Serializers for the Friends API.

Input serializers are strict: unknown keys (for example `sender_id`, `status`, `blocker_id`)
produce a 400 instead of being silently ignored. Output serializers list fields explicitly.

Privacy rule for every "person card" (see `build_user_card`): account identity (id, username,
full name) is always shown, because the viewer needs it to act on a request. Profile content
(picture, headline) is shown only when the person's profile is not private, or the viewer is the
person or an admin. Nothing else from the profile or account is ever included.
"""
from collections.abc import Mapping

from rest_framework import serializers

from accounts.models import User
from profiles.models import Profile

from .models import FriendRequest, Friendship

_DATETIME = serializers.DateTimeField()


def _iso(value):
    return _DATETIME.to_representation(value) if value else None


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
class StrictFieldsMixin:
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({"non_field_errors": ["Expected a JSON object."]})
        writable = {name for name, field in self.fields.items() if not field.read_only}
        errors = {
            key: ["This field cannot be set or changed here."] for key in data.keys() if key not in writable
        }
        if errors:
            raise serializers.ValidationError(errors)
        return super().to_internal_value(data)


class FriendRequestCreateSerializer(StrictFieldsMixin, serializers.Serializer):
    receiver_id = serializers.UUIDField()


class BlockCreateSerializer(StrictFieldsMixin, serializers.Serializer):
    user_id = serializers.UUIDField()


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def _absolute_url(file_field, request):
    if not file_field:
        return None
    try:
        url = file_field.url
    except ValueError:
        return None
    if request is not None and url.startswith("/"):
        return request.build_absolute_uri(url)
    return url


def build_user_card(user, viewer, request=None):
    """
    Minimal public view of a user. Callers must load users with `select_related("profile")`
    so building a list of cards costs no extra queries.
    """
    profile = getattr(user, "profile", None)  # missing profile -> None
    may_see_profile = (
        profile is None
        or profile.profile_visibility != Profile.Visibility.PRIVATE
        or viewer.pk == user.pk
        or viewer.role == User.Role.ADMIN
    )
    picture = headline = None
    if profile is not None and may_see_profile:
        picture = _absolute_url(profile.profile_picture, request)
        headline = profile.headline or None
    return {
        "user_id": str(user.pk),
        "username": user.username,
        "full_name": user.full_name,
        "profile_picture": picture,
        "headline": headline,
    }


class FriendRequestSerializer(serializers.ModelSerializer):
    """
    Context: `request`; optional `include_user` = "sender" | "receiver" adds that person's card
    (the list endpoints use it; it needs `select_related` on the queryset).
    """

    sender_id = serializers.UUIDField(read_only=True)
    receiver_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = FriendRequest
        fields = ("id", "sender_id", "receiver_id", "status", "created_at", "updated_at", "responded_at")
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        include = self.context.get("include_user")
        if include in ("sender", "receiver"):
            request = self.context.get("request")
            data[include] = build_user_card(getattr(instance, include), request.user, request)
        return data


class FriendshipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Friendship
        fields = ("id", "created_at")
        read_only_fields = fields


class FriendSerializer(serializers.Serializer):
    """One entry of the friends list. Input is a Friendship; the friend is the OTHER side."""

    def to_representation(self, friendship):
        request = self.context["request"]
        me = request.user
        other = friendship.user2 if friendship.user1_id == me.pk else friendship.user1
        data = build_user_card(other, me, request)
        data["friendship_id"] = str(friendship.id)
        data["friendship_created_at"] = _iso(friendship.created_at)
        data["friendship_status"] = "friends"
        return data


class MutualFriendSerializer(serializers.Serializer):
    def to_representation(self, user):
        request = self.context["request"]
        return build_user_card(user, request.user, request)


class BlockedUserSerializer(serializers.Serializer):
    """One entry of the viewer's own block list (input is a UserBlock)."""

    def to_representation(self, block):
        request = self.context["request"]
        data = build_user_card(block.blocked, request.user, request)
        data["blocked_at"] = _iso(block.created_at)
        return data


class DiscoverUserSerializer(serializers.Serializer):
    """Context: `request` and `statuses` ({user_id: relationship status})."""

    def to_representation(self, user):
        request = self.context["request"]
        data = build_user_card(user, request.user, request)
        data["friendship_status"] = self.context["statuses"].get(user.pk, "not_friends")
        return data
