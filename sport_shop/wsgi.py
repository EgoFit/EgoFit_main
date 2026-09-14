"""
WSGI config for sport_shop project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sport_shop.settings')

application = get_wsgi_application()

if os.getenv("DJANGO_AUTO_MIGRATE_ON_STARTUP", "false").strip().lower() in {"1", "true", "yes", "on"}:
    from sport_shop.startup import ensure_database_ready

    ensure_database_ready()

if os.getenv("DJANGO_AUTO_COLLECTSTATIC_ON_STARTUP", "false").strip().lower() in {"1", "true", "yes", "on"}:
    from sport_shop.startup import ensure_static_files_ready

    ensure_static_files_ready()
