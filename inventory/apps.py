from django.apps import AppConfig
from django.conf import settings
import os


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'

    def ready(self):
        """Ensure local cache directory exists; refresh runs via admin panel."""
        cache_dir = os.path.dirname(settings.LOCAL_DATA_FILE)
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
