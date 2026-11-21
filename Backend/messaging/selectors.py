from django.db.models import Q

from .models import Conversation, Message


def conversations_for(user):
    return Conversation.objects.filter(Q(user_low=user) | Q(user_high=user))


def unread_message_count(user):
    return (Message.objects.filter(conversation__in=conversations_for(user).values("pk"), read_at__isnull=True,
                                   deleted_at__isnull=True).exclude(sender=user).count())
