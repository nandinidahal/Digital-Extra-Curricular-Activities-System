"""
Registry of every notification type DEAS sends. Adding a type = adding one entry here.

Naming convention: "<area>.<event>" in lower snake case (e.g. "friend_request.received").

Fields
* category   - which preference switch controls it (see PREFERENCE_FIELDS)
* title      - default title; `{actor}` and caller-supplied context keys are substituted
* message    - default body (same substitution)
* email      - eligible for an e-mail copy (only important, low-volume events)
* essential  - security/account notices that users can NOT switch off
"""
from dataclasses import dataclass

ACCOUNT = "account"
FRIENDS = "friends"
MESSAGES = "messages"
SOCIAL = "social"
ANNOUNCEMENTS = "announcements"
ACHIEVEMENTS = "achievements"
SYSTEM = "system"

CATEGORIES = (ACCOUNT, FRIENDS, MESSAGES, SOCIAL, ANNOUNCEMENTS, ACHIEVEMENTS, SYSTEM)

# category -> NotificationPreference field (account has none: always on)
PREFERENCE_FIELDS = {
    FRIENDS: "friend_requests",
    MESSAGES: "messages",
    SOCIAL: "social_interactions",
    ANNOUNCEMENTS: "announcements",
    ACHIEVEMENTS: "achievements",
    SYSTEM: "system_notifications",
}


@dataclass(frozen=True)
class NotificationType:
    key: str
    category: str
    title: str
    message: str
    email: bool = False
    essential: bool = False


_TYPES = [
    # Account
    NotificationType("account.welcome", ACCOUNT, "Welcome to DEAS", "Your account is ready. Complete your profile to get started."),
    NotificationType("account.email_verified", ACCOUNT, "Email verified", "Your email address was verified."),
    NotificationType(
        "account.password_changed", ACCOUNT, "Password changed",
        "Your password was changed. If this was not you, reset your password immediately.",
        email=True, essential=True,
    ),
    NotificationType(
        "account.security_alert", ACCOUNT, "Security alert", "{detail}", email=True, essential=True,
    ),
    # Friends
    NotificationType("friend_request.received", FRIENDS, "New friend request", "{actor} sent you a friend request."),
    NotificationType("friend_request.accepted", FRIENDS, "Friend request accepted", "{actor} accepted your friend request."),
    NotificationType("friend_request.rejected", FRIENDS, "Friend request declined", "{actor} declined your friend request."),
    NotificationType("friend.removed", FRIENDS, "Friend removed", "{actor} is no longer in your friends list."),
    # Messaging
    NotificationType("message.received", MESSAGES, "New message", "{actor} sent you a message."),
    # Social
    NotificationType("post.liked", SOCIAL, "New like", "{actor} liked your post."),
    NotificationType("post.commented", SOCIAL, "New comment", "{actor} commented on your post."),
    NotificationType("post.shared", SOCIAL, "Shared", "{actor} shared your {resource}."),
    NotificationType("comment.replied", SOCIAL, "New reply", "{actor} replied to your comment."),
    # Announcements
    NotificationType("announcement.created", ANNOUNCEMENTS, "Announcement saved", "Your announcement \"{title}\" was saved as a draft."),
    NotificationType("announcement.published", ANNOUNCEMENTS, "New announcement", "{actor} published \"{title}\"."),
    NotificationType("announcement.updated", ANNOUNCEMENTS, "Announcement updated", "\"{title}\" was updated: {changes}."),
    NotificationType("announcement.archived", ANNOUNCEMENTS, "Announcement archived", "\"{title}\" was archived."),
    NotificationType(
        "announcement.reminder", ANNOUNCEMENTS, "Upcoming event", "\"{title}\" starts {when}.", email=True,
    ),
    # Achievements
    NotificationType("achievement.submitted", ACHIEVEMENTS, "Achievement awaiting review", "{actor} submitted \"{title}\" for verification."),
    NotificationType("achievement.verified", ACHIEVEMENTS, "Achievement verified", "Your achievement \"{title}\" was verified.", email=True),
    NotificationType("achievement.rejected", ACHIEVEMENTS, "Achievement not verified", "Your achievement \"{title}\" was not verified.", email=True),
    NotificationType(
        "achievement.more_information_required", ACHIEVEMENTS, "More information needed",
        "A reviewer needs more information about \"{title}\".", email=True,
    ),
    NotificationType("achievement.featured", ACHIEVEMENTS, "Achievement featured", "Your achievement \"{title}\" is now featured."),
    # System
    NotificationType("system.announcement", SYSTEM, "{title}", "{detail}", email=True),
    NotificationType("system.maintenance", SYSTEM, "Scheduled maintenance", "{detail}", email=True),
]

TYPES = {t.key: t for t in _TYPES}
TYPE_CHOICES = [(t.key, t.key) for t in _TYPES]


def get_type(key):
    try:
        return TYPES[key]
    except KeyError:
        raise ValueError(f"Unknown notification type: {key!r}") from None


class _SafeDict(dict):
    def __missing__(self, key):
        return ""


def render(template, context, max_length):
    text = template.format_map(_SafeDict(context)).strip()
    return text if len(text) <= max_length else text[: max_length - 1].rstrip() + "…"
