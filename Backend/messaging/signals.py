from django.conf import settings
from django.dispatch import receiver

from friends.signals import friendship_removed

from .models import Conversation


@receiver(friendship_removed)
def on_friendship_removed(sender, user_ids, **kwargs):
    """
    History is never deleted. By default the pre-friendship counter keeps its value (so un-friending
    cannot be used to farm fresh free messages). Set MESSAGING_RESET_LIMIT_ON_UNFRIEND = True to give
    ex-friends a fresh allowance of MESSAGING_PRE_FRIEND_LIMIT messages instead.
    """
    if getattr(settings, "MESSAGING_RESET_LIMIT_ON_UNFRIEND", False):
        low, high = sorted(user_ids)
        Conversation.objects.filter(user_low_id=low, user_high_id=high).update(restricted_message_count=0)
