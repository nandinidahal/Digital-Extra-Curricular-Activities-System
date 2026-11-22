from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Profile
from .services import create_profile_for_user


@receiver(
    post_save,
    sender=settings.AUTH_USER_MODEL,
    dispatch_uid="profiles_create_profile_for_new_user",
)
def create_profile_on_user_creation(sender, instance, created, raw=False, **kwargs):
    """
    Runs inside the same database transaction as the user insert. Registration
    (`accounts.services.register_user`) is atomic, so if this raises, the new
    account is rolled back too: no account without profile, no half-registration.
    Accounts created outside a transaction are healed lazily by
    `services.get_or_create_profile` or by `manage.py create_missing_profiles`.
    """
    if created and not raw:
        create_profile_for_user(instance)


@receiver(post_delete, sender=Profile, dispatch_uid="profiles_cleanup_images_on_delete")
def delete_images_with_profile(sender, instance, **kwargs):
    """Deleting a profile (or its user) must not leave image files behind."""
    for field_name in ("profile_picture", "cover_photo"):
        file_field = getattr(instance, field_name)
        if file_field and file_field.name:
            try:
                file_field.storage.delete(file_field.name)
            except Exception:  # cleanup must never break a delete
                pass
