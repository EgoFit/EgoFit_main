#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sport_shop.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    auto_migrate = os.getenv("DJANGO_AUTO_MIGRATE_ON_STARTUP", "false").strip().lower() in {"1", "true", "yes", "on"}
    auto_collectstatic = os.getenv("DJANGO_AUTO_COLLECTSTATIC_ON_STARTUP", "false").strip().lower() in {"1", "true", "yes", "on"}
    if len(sys.argv) > 1 and sys.argv[1] == "runserver" and os.environ.get("RUN_MAIN") != "true":
        if auto_migrate:
            execute_from_command_line([sys.argv[0], "migrate", "--noinput", "--verbosity", "0"])
        if auto_collectstatic:
            execute_from_command_line([sys.argv[0], "collectstatic", "--noinput", "--verbosity", "0"])
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
