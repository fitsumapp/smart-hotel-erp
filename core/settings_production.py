"""Production settings entrypoint.

Set DJANGO_SETTINGS_MODULE=core.settings_production and DJANGO_ENV=production.
The base settings module performs the fail-closed environment validation.
"""

import os

os.environ.setdefault("DJANGO_ENV", "production")

from .settings import *  # noqa: F403,E402
