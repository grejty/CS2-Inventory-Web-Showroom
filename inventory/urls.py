from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.index, name='index'),  # Public view
    path('manage/', views.admin_view, name='admin'),  # Admin interface (renamed to avoid conflict)
]