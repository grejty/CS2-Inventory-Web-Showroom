from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),  # Django admin (not our admin interface)
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('inventory.urls')),  # Our app URLs
]