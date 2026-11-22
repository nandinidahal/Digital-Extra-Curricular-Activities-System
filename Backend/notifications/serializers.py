from collections.abc import Mapping

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from .models import Notification, NotificationPreference
from .types import CATEGORIES, TYPES


def _actor_card(actor, request=None):
    """Minimal actor card. A private profile's picture is not shown (same rule as Friends)."""
    if actor is None:
        return None
    picture = None
    try:
        profile = actor.profile
        if profile.profile_visibility != "private" and profile.profile_picture:
            picture = profile.profile_picture.url
            if request is not None and picture.startswith("/"):
                picture = request.build_absolute_uri(picture)
    except (ObjectDoesNotExist, ValueError):
        picture = None
    return {"id": str(actor.pk), "username": actor.username, "full_name": actor.full_name, "profile_picture": picture}


class NotificationSerializer(serializers.ModelSerializer):
    """Expects `actor__profile` to be select_related."""

    type = serializers.CharField(source="notification_type", read_only=True)
    actor = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            "id", "type", "category", "title", "message", "actor", "metadata",
            "target_type", "target_id", "action_url", "is_read", "read_at",
            "created_at", "updated_at", "expires_at",
        )
        read_only_fields = fields

    def get_actor(self, obj):
        return _actor_card(obj.actor, self.context.get("request"))


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """PATCH accepts only the switches; unknown keys are rejected (no mass assignment)."""

    class Meta:
        model = NotificationPreference
        fields = NotificationPreference.SWITCHES + ("updated_at",)
        read_only_fields = ("updated_at",)

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({"non_field_errors": ["Expected a JSON object."]})
        unknown = {k: ["This field cannot be set or changed here."] for k in data if k not in NotificationPreference.SWITCHES}
        if unknown:
            raise serializers.ValidationError(unknown)
        for key, value in data.items():
            if not isinstance(value, bool):
                raise serializers.ValidationError({key: ["Must be true or false."]})
        return super().to_internal_value(data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["always_on"] = ["account.password_changed", "account.security_alert"]
        return data


class NotificationFilterSerializer(serializers.Serializer):
    is_read = serializers.BooleanField(required=False, allow_null=True, default=None)
    category = serializers.ChoiceField(choices=CATEGORIES, required=False)
    type = serializers.ChoiceField(choices=sorted(TYPES), required=False)
