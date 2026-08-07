from django.contrib import admin

from .models import DetalleVenta, Producto, Proveedor, Venta


class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 0
    readonly_fields = ('producto', 'cantidad', 'subtotal')


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'contacto')
    search_fields = ('nombre',)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio', 'cantidad_stock', 'proveedor', 'activo')
    list_filter = ('activo', 'proveedor')
    search_fields = ('nombre',)


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'total', 'tipo_entrega', 'es_fiado', 'nombre_cliente_fiado', 'monto_adeudado')
    list_filter = ('tipo_entrega', 'es_fiado')
    inlines = [DetalleVentaInline]
    readonly_fields = ('fecha', 'total')
