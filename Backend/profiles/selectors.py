"""Read-side helpers. Who may see what is decided here and in permissions.py, nowhere else."""
from django.db.models import Count, Q
from rest_framework.exceptions import NotFound

from achievements.models import Achievement, Visibility
from achievements.selectors import owned_by, public_of

from .models import UserProfile

RECENT_ACHIEVEMENTS = 10


def ensure_profile(user):
    """The user's profile row, created on the fly for users that somehow have none."""
    profile, _ = UserProfile.objects.select_related("user").get_or_create(user=user)
    return profile


def get_active_profile_or_404(user_id):
    """Profile of an existing, active account; anything else is a 404."""
    profile = UserProfile.objects.select_related("user").filter(user_id=user_id, user__is_active=True).first()
    if profile is None:
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
        if user is None:
            raise NotFound("User not found.")
        profile = ensure_profile(user)
    return profile


def achievement_counts(user):
    """Counts come from the existing Achievement model, in a single query."""
    agg = Achievement.objects.filter(user=user).aggregate(
        total=Count("id"),
        public=Count("id", filter=Q(visibility=Visibility.PUBLIC)),
        private=Count("id", filter=Q(visibility=Visibility.PRIVATE)),
    )
    return {"total": agg["total"], "public": agg["public"], "private": agg["private"]}


def own_achievements(user):
    return owned_by(user)


def public_achievements(user):
    return public_of(user)
