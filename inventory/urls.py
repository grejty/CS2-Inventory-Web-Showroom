from django.urls import path

from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.landing, name='landing'),
    path('buy/', views.index, name='index'),
    path('sell/', views.sell, name='sell'),
    path('manage/', views.admin_view, name='admin'),
]