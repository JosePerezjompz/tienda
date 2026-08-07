"""
Modelos de datos del supermercado.
Define Producto, Proveedor, Venta y DetalleVenta.
"""
from django.db import models
from django.utils import timezone


class Proveedor(models.Model):
    """Empresa o persona que suministra productos a la tienda."""

    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    contacto = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Contacto (teléfono o correo)',
    )

    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    """Artículo que se vende en la tienda."""

    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    precio = models.PositiveIntegerField(verbose_name='Precio (pesos)')
    cantidad_stock = models.PositiveIntegerField(
        default=0,
        verbose_name='Cantidad en stock',
    )
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        related_name='productos',
        verbose_name='Proveedor',
    )
    # activo=False significa "eliminado" sin borrar el registro de la base de datos
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Venta(models.Model):
    """Registro de una venta completa (factura)."""

    TIPO_DOMICILIO = 'domicilio'
    TIPO_TIENDA = 'tienda'
    TIPOS_ENTREGA = [
        (TIPO_DOMICILIO, 'Domicilio'),
        (TIPO_TIENDA, 'Comprado en Tienda'),
    ]

    fecha = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha y hora',
    )
    total = models.PositiveIntegerField(default=0, verbose_name='Total')
    tipo_entrega = models.CharField(
        max_length=20,
        choices=TIPOS_ENTREGA,
        default=TIPO_TIENDA,
        verbose_name='Tipo de entrega',
    )
    es_fiado = models.BooleanField(default=False, verbose_name='Venta a crédito (fiado)')
    nombre_cliente_fiado = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Nombre del cliente (fiado)',
    )
    monto_adeudado = models.PositiveIntegerField(
        default=0,
        verbose_name='Monto adeudado',
    )

    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-fecha']

    def __str__(self):
        return f'Venta #{self.pk} - {self.fecha.strftime("%d/%m/%Y %H:%M")}'

    @property
    def tipo_entrega_display(self):
        return dict(self.TIPOS_ENTREGA).get(self.tipo_entrega, self.tipo_entrega)


class DetalleVenta(models.Model):
    """Cada producto incluido en una venta, con cantidad y subtotal."""

    venta = models.ForeignKey(
        Venta,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name='Venta',
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name='detalles_venta',
        verbose_name='Producto',
    )
    cantidad = models.PositiveIntegerField(verbose_name='Cantidad vendida')
    subtotal = models.PositiveIntegerField(verbose_name='Subtotal')

    class Meta:
        verbose_name = 'Detalle de venta'
        verbose_name_plural = 'Detalles de venta'

    def __str__(self):
        return f'{self.producto.nombre} x{self.cantidad}'
