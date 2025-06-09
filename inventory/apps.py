from django.apps import AppConfig
from django.conf import settings
import os

class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'
    
    def ready(self):
        # Only run this when the server actually starts, not for management commands
        if os.environ.get('RUN_MAIN', None) == 'true' or not settings.DEBUG:
            # Import here to avoid circular imports
            from .steam_api import update_inventory
            try:
                # Try to update inventory on startup
                update_inventory()
            except Exception as e:
                # Store error to display in the UI
                global startup_error
                from . import views
                views.startup_error = str(e)