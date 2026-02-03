"""
WSGI config for timeline-atlas API.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.config.settings")

application = get_wsgi_application()
