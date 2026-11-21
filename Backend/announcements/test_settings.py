"""Settings used ONLY to test this module in isolation (no PostgreSQL server needed).

    python manage.py test announcements --settings=announcements.test_settings

It imports the project's real settings and overrides the database and file locations; the
project's settings.py is not modified. Run the suite with the normal settings as well to test
against PostgreSQL:  python manage.py test announcements
"""
import tempfile

from config.settings import *  # noqa: F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MEDIA_ROOT = tempfile.mkdtemp(prefix="ann_media_")
ANNOUNCEMENT_PRIVATE_ROOT = tempfile.mkdtemp(prefix="ann_private_")
