"""Storage for profile pictures.

By default pictures use the project's default storage (MEDIA_ROOT), under random,
unguessable file names, so they can be shown with a plain <img src> tag.

If the project defines a storage alias called "profiles" in settings.STORAGES (for example a
private S3 bucket with signed URLs) that backend is used instead.
"""
from django.conf import settings
from django.core.files.storage import default_storage, storages


def get_profile_storage():
    if "profiles" in getattr(settings, "STORAGES", {}):
        return storages["profiles"]
    return default_storage
