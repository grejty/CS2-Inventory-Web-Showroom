from django.urls import path

from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.index, name='index'),
    path('manage/', views.admin_view, name='admin'),
]