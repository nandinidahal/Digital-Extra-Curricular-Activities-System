# Test-only settings overlay used by the e2e suite (not used in development or production):
# e-mails (OTP codes) are written to files so the test can read them instead of using SMTP.
import os

from config.settings import *  # noqa: F401,F403

EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = os.environ.get("E2E_MAIL_DIR", "/tmp/deas-mail")
NOTIFICATIONS_EMAIL_ENABLED = True
