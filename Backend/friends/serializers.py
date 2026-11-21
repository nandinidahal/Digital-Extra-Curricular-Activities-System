from rest_framework import serializers

from social.serializers import UserBriefSerializer

from .models import Block, FriendRequest


class FriendRequestSerializer(serializers.ModelSerializer):
    sender = UserBriefSerializer(read_only=True)
    receiver = UserBriefSerializer(read_only=True)

    class Meta:
        model = FriendRequest
        fields = ("id", "sender", "receiver", "status", "is_ignored", "created_at", "responded_at")
        read_only_fields = fields


class SendRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class BlockSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(source="blocked", read_only=True)

    class Meta:
        model = Block
        fields = ("id", "user", "created_at")
        read_only_fields = fields
