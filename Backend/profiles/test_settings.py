"""Settings used ONLY to test this module without a PostgreSQL server.

    python manage.py test profiles --settings=profiles.test_settings

Imports the project's real settings and overrides the database and file locations; the
project's settings.py is not touched. Run the suite with the normal settings as well to test
against PostgreSQL:  python manage.py test profiles
"""
import tempfile

from config.settings import *  # noqa: F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MEDIA_ROOT = tempfile.mkdtemp(prefix="profile_media_")
ACHIEVEMENT_PRIVATE_ROOT = tempfile.mkdtemp(prefix="profile_ach_private_")
