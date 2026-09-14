from django.apps import AppConfig


class HomeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'home'

    def ready(self):
        from sport_shop.sqlite_compat import register_sqlite_functions
        from . import signals  # noqa: F401
        register_sqlite_functions()
