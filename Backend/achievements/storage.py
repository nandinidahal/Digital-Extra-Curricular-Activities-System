"""Private storage for achievement documents.

Achievement files must never be reachable through a public MEDIA_URL, so by default they
live in ACHIEVEMENT_PRIVATE_ROOT (outside MEDIA_ROOT) and are only ever served through the
authenticated download endpoint.

If the project defines a storage alias called "achievements" in settings.STORAGES (for
example a private S3 bucket) that backend is used instead, so cloud storage keeps working.
"""
import os
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage, storages


class PrivateFileSystemStorage(FileSystemStorage):
    """File system storage rooted at ACHIEVEMENT_PRIVATE_ROOT, read lazily from settings."""

    @property
    def base_location(self):
        default = Path(settings.BASE_DIR) / "private_media"
        return getattr(settings, "ACHIEVEMENT_PRIVATE_ROOT", default)

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Achievement documents are private and have no public URL.")


def get_private_storage():
    if "achievements" in getattr(settings, "STORAGES", {}):
        return storages["achievements"]
    return PrivateFileSystemStorage()
