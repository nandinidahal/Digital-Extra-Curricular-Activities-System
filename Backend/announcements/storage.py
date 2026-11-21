"""Private storage for announcement attachments.

Attachments must never be reachable through a public MEDIA_URL: by default they live in
ANNOUNCEMENT_PRIVATE_ROOT (outside MEDIA_ROOT, default ``<BASE_DIR>/private_media``) and are only
served by the authenticated download endpoint, which re-checks announcement visibility.

If settings.STORAGES defines an alias called "announcements" (e.g. a private S3 bucket), it is used
instead. Cover images are NOT private; they use the project's default storage.
"""
import os
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage, storages


class PrivateFileSystemStorage(FileSystemStorage):
    @property
    def base_location(self):
        default = Path(settings.BASE_DIR) / "private_media"
        return getattr(settings, "ANNOUNCEMENT_PRIVATE_ROOT", default)

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Announcement attachments are private and have no public URL.")


def get_private_storage():
    if "announcements" in getattr(settings, "STORAGES", {}):
        return storages["announcements"]
    return PrivateFileSystemStorage()
