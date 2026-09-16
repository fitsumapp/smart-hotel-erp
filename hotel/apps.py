from django.apps import AppConfig


class HotelConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hotel"
    verbose_name = "Hotel — Tenant Data"

    def ready(self) -> None:
        # Import signals so that all receivers are registered at app startup.
        # This must live here (not at module level) to avoid AppRegistryNotReady.
        import hotel.signals  # noqa: F401
        import apps.audit.signals  # noqa: F401
