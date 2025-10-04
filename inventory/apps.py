import logging
import os

from django.apps import AppConfig
from django.conf import settings


logger = logging.getLogger(__name__)


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'

    def ready(self):
        """Ensure local cache directory exists and provision admin credentials if supplied."""
        cache_dir = os.path.dirname(settings.LOCAL_DATA_FILE)
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

        self._ensure_admin_user()

    def _ensure_admin_user(self):
        username = settings.ADMIN_USERNAME
        password = settings.ADMIN_PASSWORD

        if not username or not password:
            return

        from django.contrib.auth import get_user_model
        from django.db import OperationalError, ProgrammingError

        User = get_user_model()

        try:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'is_staff': True,
                    'is_superuser': True,
                }
            )

            updated_fields = set()

            if created:
                logger.info("Created inventory admin user from environment: %s", username)
            else:
                if not user.is_staff:
                    user.is_staff = True
                    updated_fields.add('is_staff')

                if not user.is_superuser:
                    user.is_superuser = True
                    updated_fields.add('is_superuser')

            if not user.check_password(password):
                user.set_password(password)
                updated_fields.add('password')

            if updated_fields:
                user.save(update_fields=list(updated_fields))

        except (OperationalError, ProgrammingError):
            # Database tables might not be ready yet (e.g., during migrate)
            logger.debug("Inventory admin bootstrap skipped; auth tables unavailable.")
