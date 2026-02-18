from django.apps import AppConfig

class InventoryManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory_manager'
    verbose_name = 'Inventory Management System'

    def ready(self):
        """
        Initialize app when Django starts.
        Import signals to ensure they are registered.
        """
        try:
            import inventory_manager.signals  # noqa
        except ImportError:
            pass