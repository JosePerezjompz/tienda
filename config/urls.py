"""Rutas principales del proyecto."""
from django.contrib import admin
from django.urls import include, path

from inventario import views as inventario_views

urlpatterns = [
    path('sw.js', inventario_views.service_worker, name='service_worker'),
    path('admin/', admin.site.urls),
    path('', include('inventario.urls')),
]
