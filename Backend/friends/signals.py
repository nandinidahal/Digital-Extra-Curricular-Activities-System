"""
Integration events. The Friends module only ANNOUNCES what happened; it stores no
notifications and sends nothing. The future Notifications module (or any other module)
connects a receiver, for example:

    from django.dispatch import receiver
    from friends.signals import friend_request_accepted

    @receiver(friend_request_accepted)
    def notify(sender, friend_request, friendship, **kwargs):
        ...

Rules:
* Signals are sent AFTER the surrounding database transaction commits, so receivers never
  see data that was later rolled back.
* They are sent with `send_robust`: a failing receiver is logged and can never break or roll
  back a friendship operation.
"""
from django.dispatch import Signal

# friend_request=<FriendRequest>
friend_request_sent = Signal()
# friend_request=<FriendRequest>, friendship=<Friendship>, auto_accepted=<bool>
friend_request_accepted = Signal()
# friend_request=<FriendRequest>
friend_request_rejected = Signal()
# friend_request=<FriendRequest>, reason="cancelled_by_sender" | "blocked"
friend_request_cancelled = Signal()
# user_id=<UUID of the user who removed/blocked>, other_user_id=<UUID>, reason="removed" | "blocked"
friend_removed = Signal()
# block=<UserBlock>, friendship_removed=<bool>, requests_cancelled=<int>
user_blocked = Signal()
# blocker_id=<UUID>, blocked_id=<UUID>
user_unblocked = Signal()
