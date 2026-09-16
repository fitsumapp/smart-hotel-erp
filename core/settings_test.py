"""Settings used exclusively by the automated test suite.

The test configuration is deliberately self-contained: it never reads or
writes the development/production PostgreSQL database and it never sends
email to external recipients.
"""

import os

os.environ.setdefault("DJANGO_ENV", "test")

from .settings import *  # noqa: F403,E402


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

