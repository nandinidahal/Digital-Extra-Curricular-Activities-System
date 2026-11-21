"""Every queryset that decides who may see what lives here, so the rules exist in one place."""
from django.db.models import Q

from .models import Achievement, AchievementDocument, Visibility


def _achievements():
    return Achievement.objects.select_related("category", "user").prefetch_related("documents")


def owned_by(user):
    """All of a user's own achievements, public and private."""
    return _achievements().filter(user=user)


def visible_to(user):
    """Achievements `user` may read: their own, plus anyone's PUBLIC ones."""
    return _achievements().filter(Q(user=user) | Q(visibility=Visibility.PUBLIC, user__is_active=True))


def public_of(owner):
    """Only the PUBLIC achievements of `owner` (what appears on their profile)."""
    return _achievements().filter(user=owner, user__is_active=True, visibility=Visibility.PUBLIC)


def documents_visible_to(user):
    return AchievementDocument.objects.select_related("achievement").filter(
        Q(achievement__user=user)
        | Q(achievement__visibility=Visibility.PUBLIC, achievement__user__is_active=True)
    )
