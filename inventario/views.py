"""
Vistas del sistema de inventario.
Incluye facturación (SPA), gestión de inventario e historial de ventas.
"""
import json
from functools import wraps

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .forms import FiltroFechasForm, ProductoForm, ReporteMesForm
from .models import DetalleVenta, Producto, Proveedor, Venta
from .utils import estado_stock, formato_pesos


def _respuesta_error(mensaje, status=400):
    """Respuesta JSON amigable en español (sin detalles técnicos)."""
    return JsonResponse({'ok': False, 'error': mensaje}, status=status)


def acceso_interno_requerido(vista):
    """Exige la clave interna para secciones distintas a ventas."""
    @wraps(vista)
    def wrapper(request, *args, **kwargs):
        autorizado_hasta = request.session.get('acceso_interno_autorizado_hasta', 0)

        if (
            request.session.get('acceso_interno_autorizado')
            and autorizado_hasta > timezone.now().timestamp()
        ):
            return vista(request, *args, **kwargs)

        request.session.pop('acceso_interno_autorizado', None)
        request.session.pop('acceso_interno_autorizado_hasta', None)
        login_url = reverse('inventario:acceso_restringido')
        return redirect(f'{login_url}?next={request.get_full_path()}')

    return wrapper


def _next_seguro(request, valor_por_defecto):
    """Evita redirecciones externas despues de escribir la clave."""
    next_url = (
        request.POST.get('next')
        or request.GET.get('next')
        or valor_por_defecto
    )
    es_seguro = url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )
    return next_url if es_seguro else valor_por_defecto


def _producto_a_dict(producto):
    """Convierte un producto a diccionario para la API de facturación."""
    return {
        'id': producto.id,
        'nombre': producto.nombre,
        'precio': producto.precio,
        'precio_formateado': formato_pesos(producto.precio),
        'stock': producto.cantidad_stock,
    }


# ---------------------------------------------------------------------------
# PÁGINA 1: FACTURACIÓN
# ---------------------------------------------------------------------------

def facturacion(request):
    """Página principal de ventas (SPA con JavaScript)."""
    return render(request, 'inventario/facturacion.html')


@require_GET
def service_worker(request):
    """Sirve el Service Worker desde /sw.js con el tipo MIME correcto."""
    response = render(
        request,
        'inventario/sw.js',
        content_type='application/javascript',
    )
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response


@require_GET
def offline(request):
    """Página amable para navegación sin conexión."""
    return render(request, 'inventario/offline.html')


@require_http_methods(['GET', 'POST'])
def acceso_restringido(request):
    """Pide la clave para entrar a Inventario e Historial."""
    destino_por_defecto = reverse('inventario:lista_inventario')
    next_url = _next_seguro(request, destino_por_defecto)
    error = ''

    if request.method == 'POST':
        clave = request.POST.get('password', '')
        if check_password(clave, settings.INTERNAL_ACCESS_PASSWORD_HASH):
            request.session['acceso_interno_autorizado'] = True
            request.session['acceso_interno_autorizado_hasta'] = (
                timezone.now().timestamp() + settings.INTERNAL_ACCESS_SESSION_SECONDS
            )
            return redirect(next_url)

        error = 'Contraseña incorrecta. Intenta de nuevo.'

    return render(request, 'inventario/acceso_restringido.html', {
        'next': next_url,
        'error': error,
    })


@require_GET
def api_buscar_productos(request):
    """Busca productos activos por nombre (tiempo real desde el frontend)."""
    consulta = request.GET.get('q', '').strip()
    productos = Producto.objects.filter(activo=True)

    if consulta:
        productos = productos.filter(nombre__icontains=consulta)

    productos = productos.select_related('proveedor').order_by('nombre')[:50]
    return JsonResponse({
        'ok': True,
        'productos': [_producto_a_dict(p) for p in productos],
    })


@require_GET
def api_listar_productos(request):
    """Lista todos los productos activos disponibles para vender."""
    productos = Producto.objects.filter(activo=True).order_by('nombre')
    return JsonResponse({
        'ok': True,
        'productos': [_producto_a_dict(p) for p in productos],
    })


@require_POST
def api_confirmar_venta(request):
    """
    Registra una venta completa.
    Valida stock en el backend y resta cantidades automáticamente.
    """
    try:
        datos = json.loads(request.body)
    except json.JSONDecodeError:
        return _respuesta_error('Los datos enviados no son válidos. Intenta de nuevo.')

    items = datos.get('items', [])
    if not items:
        return _respuesta_error('No puedes confirmar una venta con el carrito vacío.')

    tipo_entrega = datos.get('tipo_entrega', Venta.TIPO_TIENDA)
    if tipo_entrega not in (Venta.TIPO_DOMICILIO, Venta.TIPO_TIENDA):
        return _respuesta_error('Selecciona un tipo de entrega válido.')

    es_fiado = bool(datos.get('es_fiado', False))
    nombre_cliente_fiado = datos.get('nombre_cliente_fiado', '').strip()
    monto_adeudado = datos.get('monto_adeudado', 0)

    if es_fiado:
        if not nombre_cliente_fiado:
            return _respuesta_error('Ingresa el nombre del cliente para la venta a crédito.')
        try:
            monto_adeudado = int(monto_adeudado)
        except (TypeError, ValueError):
            return _respuesta_error('La cantidad adeudada debe ser un número válido.')
        if monto_adeudado <= 0:
            return _respuesta_error('La cantidad adeudada debe ser mayor a cero.')
    else:
        nombre_cliente_fiado = ''
        monto_adeudado = 0

    # Validar estructura de cada ítem antes de tocar la base de datos
    items_validados = []
    for item in items:
        try:
            producto_id = int(item.get('producto_id'))
            cantidad = int(item.get('cantidad'))
        except (TypeError, ValueError):
            return _respuesta_error('Hay un producto con datos incorrectos en el carrito.')

        if cantidad <= 0:
            return _respuesta_error('La cantidad debe ser al menos 1 unidad.')

        items_validados.append({'producto_id': producto_id, 'cantidad': cantidad})

    try:
        with transaction.atomic():
            total_venta = 0
            detalles_a_crear = []

            for item in items_validados:
                producto = Producto.objects.select_for_update().get(
                    pk=item['producto_id'],
                    activo=True,
                )

                if producto.cantidad_stock < item['cantidad']:
                    return _respuesta_error(
                        f'No hay suficiente stock de "{producto.nombre}". '
                        f'Disponible: {producto.cantidad_stock} unidades.'
                    )

                subtotal = producto.precio * item['cantidad']
                total_venta += subtotal
                detalles_a_crear.append({
                    'producto': producto,
                    'cantidad': item['cantidad'],
                    'subtotal': subtotal,
                })

            venta = Venta.objects.create(
                total=total_venta,
                tipo_entrega=tipo_entrega,
                es_fiado=es_fiado,
                nombre_cliente_fiado=nombre_cliente_fiado,
                monto_adeudado=monto_adeudado if es_fiado else 0,
            )

            detalles_respuesta = []
            for detalle in detalles_a_crear:
                producto = detalle['producto']
                producto.cantidad_stock -= detalle['cantidad']
                producto.save(update_fields=['cantidad_stock'])

                DetalleVenta.objects.create(
                    venta=venta,
                    producto=producto,
                    cantidad=detalle['cantidad'],
                    subtotal=detalle['subtotal'],
                )

                detalles_respuesta.append({
                    'nombre': producto.nombre,
                    'cantidad': detalle['cantidad'],
                    'precio_unitario': producto.precio,
                    'precio_unitario_formateado': formato_pesos(producto.precio),
                    'subtotal': detalle['subtotal'],
                    'subtotal_formateado': formato_pesos(detalle['subtotal']),
                })

    except Producto.DoesNotExist:
        return _respuesta_error(
            'Uno de los productos ya no está disponible. Actualiza la lista e intenta de nuevo.'
        )
    except Exception:
        return _respuesta_error(
            'Ocurrió un problema al registrar la venta. Por favor, intenta de nuevo.',
            status=500,
        )

    fecha_local = timezone.localtime(venta.fecha)
    return JsonResponse({
        'ok': True,
        'mensaje': '¡Venta registrada correctamente!',
        'venta': {
            'id': venta.id,
            'fecha': fecha_local.strftime('%d/%m/%Y %H:%M'),
            'total': venta.total,
            'total_formateado': formato_pesos(venta.total),
            'tipo_entrega': venta.tipo_entrega,
            'tipo_entrega_display': venta.tipo_entrega_display,
            'es_fiado': venta.es_fiado,
            'nombre_cliente_fiado': venta.nombre_cliente_fiado,
            'monto_adeudado': venta.monto_adeudado,
            'monto_adeudado_formateado': formato_pesos(venta.monto_adeudado) if venta.es_fiado else '',
            'detalles': detalles_respuesta,
        },
    })


@require_POST
def api_anular_ultima_venta(request):
    """
    Anula la venta más reciente y devuelve el stock a cada producto.
    """
    ultima_venta = Venta.objects.order_by('-fecha').first()
    if not ultima_venta:
        return _respuesta_error('No hay ventas recientes para anular.')

    try:
        with transaction.atomic():
            detalles = ultima_venta.detalles.select_related('producto').all()
            productos_restaurados = []

            for detalle in detalles:
                producto = Producto.objects.select_for_update().get(pk=detalle.producto_id)
                producto.cantidad_stock += detalle.cantidad
                producto.save(update_fields=['cantidad_stock'])
                productos_restaurados.append(producto.nombre)

            venta_id = ultima_venta.id
            ultima_venta.delete()

    except Exception:
        return _respuesta_error(
            'No se pudo anular la venta. Intenta de nuevo.',
            status=500,
        )

    return JsonResponse({
        'ok': True,
        'mensaje': f'Se anuló la venta #{venta_id} y se restauró el stock.',
        'productos_restaurados': productos_restaurados,
    })


# ---------------------------------------------------------------------------
# PÁGINA 2: INVENTARIO
# ---------------------------------------------------------------------------

@acceso_interno_requerido
def lista_inventario(request):
    """Lista paginada de productos con filtro de activos/inactivos."""
    filtro = request.GET.get('filtro', 'todos')
    productos = Producto.objects.select_related('proveedor').all()

    if filtro == 'activos':
        productos = productos.filter(activo=True)
    elif filtro == 'inactivos':
        productos = productos.filter(activo=False)

    paginator = Paginator(productos, settings.PRODUCTOS_POR_PAGINA)
    pagina = request.GET.get('pagina', 1)
    productos_pagina = paginator.get_page(pagina)

    # Agregar estado de stock a cada producto para el template
    productos_con_estado = []
    for producto in productos_pagina:
        color, texto = estado_stock(producto.cantidad_stock)
        productos_con_estado.append({
            'obj': producto,
            'color': color,
            'texto_stock': texto,
            'precio_formateado': formato_pesos(producto.precio),
        })

    return render(request, 'inventario/inventario_lista.html', {
        'productos_pagina': productos_pagina,
        'productos_con_estado': productos_con_estado,
        'filtro': filtro,
    })


@acceso_interno_requerido
def crear_producto(request):
    """Formulario para agregar un producto nuevo (un paso a la vez)."""
    if not Proveedor.objects.exists():
        return render(request, 'inventario/sin_proveedor.html')

    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('inventario:lista_inventario')
    else:
        form = ProductoForm()

    return render(request, 'inventario/producto_form.html', {
        'form': form,
        'titulo': 'Agregar producto nuevo',
        'boton': 'Guardar producto',
    })


@acceso_interno_requerido
def editar_producto(request, producto_id):
    """Editar producto existente (incluye sumar stock de mercancía nueva)."""
    producto = get_object_or_404(Producto, pk=producto_id)

    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            return redirect('inventario:lista_inventario')
    else:
        form = ProductoForm(instance=producto)

    return render(request, 'inventario/producto_form.html', {
        'form': form,
        'titulo': f'Editar: {producto.nombre}',
        'boton': 'Guardar cambios',
        'producto': producto,
    })


@acceso_interno_requerido
def desactivar_producto(request, producto_id):
    """Desactiva un producto (eliminación lógica, no borrado físico)."""
    producto = get_object_or_404(Producto, pk=producto_id)

    if request.method == 'POST':
        producto.activo = False
        producto.save(update_fields=['activo'])
        return redirect('inventario:lista_inventario')

    return render(request, 'inventario/desactivar_producto.html', {
        'producto': producto,
    })


@acceso_interno_requerido
def crear_proveedor_rapido(request):
    """Permite crear un proveedor antes de agregar productos."""
    from .forms import ProveedorForm

    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('inventario:crear_producto')
    else:
        form = ProveedorForm()

    return render(request, 'inventario/proveedor_form.html', {
        'form': form,
    })


# ---------------------------------------------------------------------------
# PÁGINA 3: HISTORIAL DE VENTAS
# ---------------------------------------------------------------------------

@acceso_interno_requerido
def historial_ventas(request):
    """Lista de facturas con filtro por rango de fechas."""
    ventas = Venta.objects.all()
    form_filtro = FiltroFechasForm(request.GET or None)
    filtro_entrega = request.GET.get('tipo_entrega', '')

    if form_filtro.is_valid():
        desde = form_filtro.cleaned_data.get('fecha_desde')
        hasta = form_filtro.cleaned_data.get('fecha_hasta')
        if desde:
            ventas = ventas.filter(fecha__date__gte=desde)
        if hasta:
            ventas = ventas.filter(fecha__date__lte=hasta)

    if filtro_entrega in (Venta.TIPO_DOMICILIO, Venta.TIPO_TIENDA):
        ventas = ventas.filter(tipo_entrega=filtro_entrega)

    ventas_filtradas = ventas
    total_domicilio = ventas_filtradas.filter(tipo_entrega=Venta.TIPO_DOMICILIO).aggregate(
        suma=Sum('total')
    )['suma'] or 0
    total_tienda = ventas_filtradas.filter(tipo_entrega=Venta.TIPO_TIENDA).aggregate(
        suma=Sum('total')
    )['suma'] or 0
    cantidad_domicilio = ventas_filtradas.filter(tipo_entrega=Venta.TIPO_DOMICILIO).count()
    cantidad_tienda = ventas_filtradas.filter(tipo_entrega=Venta.TIPO_TIENDA).count()

    cuentas_por_cobrar = (
        ventas_filtradas.filter(es_fiado=True, monto_adeudado__gt=0)
        .values('nombre_cliente_fiado')
        .annotate(
            total_adeudado=Sum('monto_adeudado'),
            cantidad_ventas=Count('id'),
        )
        .order_by('-total_adeudado')
    )
    total_fiados = sum(c['total_adeudado'] for c in cuentas_por_cobrar)

    ventas_lista = []
    for venta in ventas[:100]:
        fecha_local = timezone.localtime(venta.fecha)
        ventas_lista.append({
            'obj': venta,
            'fecha_formateada': fecha_local.strftime('%d/%m/%Y %H:%M'),
            'total_formateado': formato_pesos(venta.total),
            'tipo_entrega_display': venta.tipo_entrega_display,
            'es_fiado': venta.es_fiado,
            'monto_adeudado_formateado': formato_pesos(venta.monto_adeudado) if venta.es_fiado else '',
        })

    # Formulario de reporte mensual (mes/año actual por defecto)
    ahora = timezone.localtime()
    form_reporte = ReporteMesForm(initial={
        'mes': ahora.month,
        'anio': ahora.year,
    })

    return render(request, 'inventario/historial_ventas.html', {
        'ventas_lista': ventas_lista,
        'form_filtro': form_filtro,
        'form_reporte': form_reporte,
        'filtro_entrega': filtro_entrega,
        'total_domicilio': total_domicilio,
        'total_domicilio_formateado': formato_pesos(total_domicilio),
        'total_tienda': total_tienda,
        'total_tienda_formateado': formato_pesos(total_tienda),
        'cantidad_domicilio': cantidad_domicilio,
        'cantidad_tienda': cantidad_tienda,
        'cuentas_por_cobrar': [
            {
                'cliente': c['nombre_cliente_fiado'],
                'total_adeudado': c['total_adeudado'],
                'total_adeudado_formateado': formato_pesos(c['total_adeudado']),
            }
            for c in cuentas_por_cobrar
        ],
        'total_fiados': total_fiados,
        'total_fiados_formateado': formato_pesos(total_fiados),
    })


@acceso_interno_requerido
def detalle_venta(request, venta_id):
    """Muestra el detalle completo de una factura."""
    venta = get_object_or_404(Venta.objects.prefetch_related('detalles__producto'), pk=venta_id)
    fecha_local = timezone.localtime(venta.fecha)

    detalles = []
    for detalle in venta.detalles.all():
        detalles.append({
            'nombre': detalle.producto.nombre,
            'cantidad': detalle.cantidad,
            'precio_unitario_formateado': formato_pesos(detalle.producto.precio),
            'subtotal_formateado': formato_pesos(detalle.subtotal),
        })

    return render(request, 'inventario/detalle_venta.html', {
        'venta': venta,
        'detalles': detalles,
        'fecha_formateada': fecha_local.strftime('%d/%m/%Y %H:%M'),
        'total_formateado': formato_pesos(venta.total),
        'tipo_entrega_display': venta.tipo_entrega_display,
        'monto_adeudado_formateado': formato_pesos(venta.monto_adeudado) if venta.es_fiado else '',
    })


@acceso_interno_requerido
def reporte_mensual(request):
    """Genera reporte del mes seleccionado bajo demanda (al hacer clic)."""
    if request.method != 'POST':
        return redirect('inventario:historial_ventas')

    form = ReporteMesForm(request.POST)
    if not form.is_valid():
        return redirect('inventario:historial_ventas')

    mes = int(form.cleaned_data['mes'])
    anio = form.cleaned_data['anio']

    ventas = Venta.objects.filter(
        fecha__year=anio,
        fecha__month=mes,
    ).prefetch_related('detalles__producto')

    total_mes = ventas.aggregate(suma=Sum('total'))['suma'] or 0
    cantidad_ventas = ventas.count()

    total_domicilio = ventas.filter(tipo_entrega=Venta.TIPO_DOMICILIO).aggregate(
        suma=Sum('total')
    )['suma'] or 0
    total_tienda = ventas.filter(tipo_entrega=Venta.TIPO_TIENDA).aggregate(
        suma=Sum('total')
    )['suma'] or 0
    cantidad_domicilio = ventas.filter(tipo_entrega=Venta.TIPO_DOMICILIO).count()
    cantidad_tienda = ventas.filter(tipo_entrega=Venta.TIPO_TIENDA).count()

    cuentas_por_cobrar = (
        ventas.filter(es_fiado=True, monto_adeudado__gt=0)
        .values('nombre_cliente_fiado')
        .annotate(total_adeudado=Sum('monto_adeudado'))
        .order_by('-total_adeudado')
    )
    total_fiados = sum(c['total_adeudado'] for c in cuentas_por_cobrar)

    # Productos más vendidos del mes
    productos_vendidos = (
        DetalleVenta.objects
        .filter(venta__fecha__year=anio, venta__fecha__month=mes)
        .values('producto__nombre')
        .annotate(total_unidades=Sum('cantidad'), total_pesos=Sum('subtotal'))
        .order_by('-total_unidades')[:10]
    )

    nombres_mes = dict(ReporteMesForm.MESES)
    return render(request, 'inventario/reporte_mensual.html', {
        'mes_nombre': nombres_mes.get(mes, str(mes)),
        'anio': anio,
        'total_mes': total_mes,
        'total_mes_formateado': formato_pesos(total_mes),
        'cantidad_ventas': cantidad_ventas,
        'total_domicilio': total_domicilio,
        'total_domicilio_formateado': formato_pesos(total_domicilio),
        'total_tienda': total_tienda,
        'total_tienda_formateado': formato_pesos(total_tienda),
        'cantidad_domicilio': cantidad_domicilio,
        'cantidad_tienda': cantidad_tienda,
        'cuentas_por_cobrar': [
            {
                'cliente': c['nombre_cliente_fiado'],
                'total_adeudado': c['total_adeudado'],
                'total_adeudado_formateado': formato_pesos(c['total_adeudado']),
            }
            for c in cuentas_por_cobrar
        ],
        'total_fiados': total_fiados,
        'total_fiados_formateado': formato_pesos(total_fiados),
        'productos_vendidos': [
            {
                'nombre': p['producto__nombre'],
                'unidades': p['total_unidades'],
                'total_formateado': formato_pesos(p['total_pesos']),
            }
            for p in productos_vendidos
        ],
    })
