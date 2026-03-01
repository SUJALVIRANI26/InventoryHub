from django.apps import AppConfig

class InventoryManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory_manager'

    def ready(self):
        import inventory_manager.signals
