"""
Rutas de la app inventario.
Agrupa facturación, inventario e historial de ventas.
"""
from django.urls import path

from . import views

app_name = 'inventario'

urlpatterns = [
    # Página principal: redirige a facturación
    path('', views.facturacion, name='facturacion'),
    path('offline/', views.offline, name='offline'),
    path('acceso/', views.acceso_restringido, name='acceso_restringido'),

    # API para facturación (SPA con JavaScript)
    path('api/productos/', views.api_listar_productos, name='api_listar_productos'),
    path('api/productos/buscar/', views.api_buscar_productos, name='api_buscar_productos'),
    path('api/ventas/confirmar/', views.api_confirmar_venta, name='api_confirmar_venta'),
    path('api/ventas/anular-ultima/', views.api_anular_ultima_venta, name='api_anular_ultima'),

    # Inventario de productos
    path('inventario/', views.lista_inventario, name='lista_inventario'),
    path('inventario/nuevo/', views.crear_producto, name='crear_producto'),
    path('inventario/editar/<int:producto_id>/', views.editar_producto, name='editar_producto'),
    path('inventario/desactivar/<int:producto_id>/', views.desactivar_producto, name='desactivar_producto'),
    path('inventario/proveedor/nuevo/', views.crear_proveedor_rapido, name='crear_proveedor'),

    # Historial y reportes
    path('historial/', views.historial_ventas, name='historial_ventas'),
    path('historial/<int:venta_id>/', views.detalle_venta, name='detalle_venta'),
    path('historial/reporte-mes/', views.reporte_mensual, name='reporte_mensual'),
]
