/**
 * Facturación SPA: carrito, búsqueda en tiempo real y confirmación de ventas.
 * Todas las peticiones incluyen token CSRF de Django.
 */
(function () {
    'use strict';

    // --- Estado del carrito y caché de productos ---
    const carrito = {};  // { producto_id: { producto, cantidad } }
    const productosCache = {};  // { producto_id: producto }

    // --- Referencias al DOM ---
    const buscador = document.getElementById('buscador-productos');
    const listaProductos = document.getElementById('lista-productos');
    const carritoVacio = document.getElementById('carrito-vacio');
    const carritoContenido = document.getElementById('carrito-contenido');
    const carritoItems = document.getElementById('carrito-items');
    const carritoTotal = document.getElementById('carrito-total');
    const btnConfirmar = document.getElementById('btn-confirmar-venta');
    const btnAnular = document.getElementById('btn-anular-ultima');
    const csrfToken = document.getElementById('csrf-token').value;
    const checkFiado = document.getElementById('check-fiado');
    const formularioFiado = document.getElementById('formulario-fiado');
    const nombreClienteFiado = document.getElementById('nombre-cliente-fiado');
    const montoAdeudado = document.getElementById('monto-adeudado');

    const modalConfirmar = new bootstrap.Modal(document.getElementById('modal-confirmar'));
    const modalAnular = new bootstrap.Modal(document.getElementById('modal-anular'));
    const modalFactura = new bootstrap.Modal(document.getElementById('modal-factura'));

    // --- Utilidades ---

    /** Formatea un número como pesos colombianos: $15.000 */
    function formatoPesos(valor) {
        return '$' + Number(valor).toLocaleString('es-CO').replace(/,/g, '.');
    }

    /** Petición fetch con CSRF y manejo de errores amigable */
    async function peticion(url, opciones = {}) {
        const esGet = !opciones.method || opciones.method === 'GET';
        const config = {
            headers: {
                'X-CSRFToken': csrfToken,
            },
            ...opciones,
        };

        if (!esGet) {
            config.headers['Content-Type'] = 'application/json';
        }

        let respuesta;
        try {
            respuesta = await fetch(url, config);
        } catch (err) {
            throw new Error('No se pudo conectar con el servidor. Verifica tu conexión.');
        }

        let datos;
        try {
            datos = await respuesta.json();
        } catch (err) {
            throw new Error('Ocurrió un problema. Por favor, intenta de nuevo.');
        }

        if (!respuesta.ok || !datos.ok) {
            throw new Error(datos.error || 'Ocurrió un problema. Intenta de nuevo.');
        }
        return datos;
    }

    function mostrarError(mensaje) {
        const el = document.getElementById('mensaje-error');
        document.getElementById('mensaje-error-texto').textContent = mensaje;
        el.classList.remove('d-none');
    }

    function ocultarError() {
        document.getElementById('mensaje-error').classList.add('d-none');
    }

    function mostrarExito(mensaje) {
        document.getElementById('mensaje-exito-texto').textContent = mensaje;
        document.getElementById('mensaje-exito').classList.remove('d-none');
    }

    // --- Productos ---

    function renderizarProductos(productos) {
        if (productos.length === 0) {
            listaProductos.innerHTML = '<p class="texto-ayuda">No se encontraron productos.</p>';
            return;
        }

        // Guardar productos en caché local para agregar al carrito sin otra petición
        productos.forEach(function (p) {
            productosCache[p.id] = p;
        });

        listaProductos.innerHTML = productos.map(function (p) {
            const sinStock = p.stock <= 0;
            const enCarrito = carrito[p.id];
            const cantidadEnCarrito = enCarrito ? enCarrito.cantidad : 0;
            const stockDisponible = p.stock - cantidadEnCarrito;

            return `
                <div class="tarjeta-producto ${sinStock ? 'tarjeta-producto-sin-stock' : ''}"
                     tabindex="${sinStock ? '-1' : '0'}"
                     role="button"
                     aria-label="Agregar ${p.nombre}"
                     data-id="${p.id}"
                     ${sinStock ? '' : 'onclick="window.agregarAlCarrito(' + p.id + ')"'}>
                    <div class="tarjeta-producto-nombre">${p.nombre}</div>
                    <div class="tarjeta-producto-info">
                        Precio: ${p.precio_formateado} &nbsp;|&nbsp;
                        Stock: ${p.stock} unidades
                        ${sinStock ? '<span class="text-danger fw-bold"> — Agotado</span>' : ''}
                    </div>
                </div>
            `;
        }).join('');
    }

    async function cargarProductos(consulta) {
        try {
            const url = consulta
                ? `/api/productos/buscar/?q=${encodeURIComponent(consulta)}`
                : '/api/productos/';
            const datos = await peticion(url);
            renderizarProductos(datos.productos);
        } catch (err) {
            listaProductos.innerHTML = `<p class="text-danger">${err.message}</p>`;
        }
    }

    // Búsqueda en tiempo real con pequeño retardo para no saturar el servidor
    let temporizadorBusqueda = null;
    buscador.addEventListener('input', function () {
        clearTimeout(temporizadorBusqueda);
        temporizadorBusqueda = setTimeout(function () {
            cargarProductos(buscador.value.trim());
        }, 300);
    });

    // --- Carrito ---

    window.agregarAlCarrito = function (productoId) {
        ocultarError();
        const tarjeta = document.querySelector(`.tarjeta-producto[data-id="${productoId}"]`);
        if (!tarjeta || tarjeta.classList.contains('tarjeta-producto-sin-stock')) return;

        const producto = productosCache[productoId];
        if (!producto) {
            mostrarError('No se encontró el producto. Actualiza la lista e intenta de nuevo.');
            return;
        }

        if (!carrito[productoId]) {
            carrito[productoId] = { producto: producto, cantidad: 0 };
        }

        const item = carrito[productoId];
        if (item.cantidad >= producto.stock) {
            mostrarError(`No hay más stock de "${producto.nombre}". Disponible: ${producto.stock} unidades.`);
            return;
        }

        item.cantidad += 1;
        item.producto = producto;
        actualizarCarrito();
        cargarProductos(buscador.value.trim());
    };

    function cambiarCantidad(productoId, delta) {
        ocultarError();
        const item = carrito[productoId];
        if (!item) return;

        const nuevaCantidad = item.cantidad + delta;
        if (nuevaCantidad <= 0) {
            delete carrito[productoId];
        } else if (nuevaCantidad > item.producto.stock) {
            mostrarError(
                `No hay suficiente stock de "${item.producto.nombre}". ` +
                `Disponible: ${item.producto.stock} unidades.`
            );
            return;
        } else {
            item.cantidad = nuevaCantidad;
        }

        actualizarCarrito();
        cargarProductos(buscador.value.trim());
    }

    window.quitarDelCarrito = function (productoId) {
        delete carrito[productoId];
        actualizarCarrito();
        cargarProductos(buscador.value.trim());
    };

    function actualizarCarrito() {
        const ids = Object.keys(carrito);
        const hayItems = ids.length > 0;

        carritoVacio.classList.toggle('d-none', hayItems);
        carritoContenido.classList.toggle('d-none', !hayItems);
        btnConfirmar.disabled = !hayItems;

        if (!hayItems) {
            carritoTotal.textContent = '$0';
            return;
        }

        let total = 0;
        carritoItems.innerHTML = ids.map(function (id) {
            const item = carrito[id];
            const subtotal = item.producto.precio * item.cantidad;
            total += subtotal;

            return `
                <tr>
                    <td class="fw-semibold">${item.producto.nombre}</td>
                    <td>${item.producto.precio_formateado}</td>
                    <td>
                        <div class="control-cantidad">
                            <button type="button" class="btn btn-outline-secondary btn-cantidad"
                                    onclick="window.cambiarCantidadCarrito(${id}, -1)"
                                    aria-label="Quitar una unidad">−</button>
                            <span class="cantidad-display">${item.cantidad}</span>
                            <button type="button" class="btn btn-outline-secondary btn-cantidad"
                                    onclick="window.cambiarCantidadCarrito(${id}, 1)"
                                    aria-label="Agregar una unidad">+</button>
                        </div>
                    </td>
                    <td class="fw-bold">${formatoPesos(subtotal)}</td>
                    <td>
                        <button type="button" class="btn btn-outline-danger btn-accion"
                                onclick="window.quitarDelCarrito(${id})">
                            Quitar
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        carritoTotal.textContent = formatoPesos(total);
        actualizarMontoFiado();
    }

    window.cambiarCantidadCarrito = cambiarCantidad;

    // --- Opciones de venta: entrega y fiado ---

    function obtenerTipoEntrega() {
        const seleccionado = document.querySelector('input[name="tipo-entrega"]:checked');
        return seleccionado ? seleccionado.value : 'tienda';
    }

    function obtenerTotalCarrito() {
        let total = 0;
        Object.values(carrito).forEach(function (item) {
            total += item.producto.precio * item.cantidad;
        });
        return total;
    }

    function actualizarMontoFiado() {
        if (checkFiado.checked && !montoAdeudado.dataset.editado) {
            montoAdeudado.value = obtenerTotalCarrito();
        }
    }

    checkFiado.addEventListener('change', function () {
        formularioFiado.classList.toggle('d-none', !this.checked);
        if (this.checked) {
            actualizarMontoFiado();
            nombreClienteFiado.focus();
        } else {
            nombreClienteFiado.value = '';
            montoAdeudado.value = '';
            delete montoAdeudado.dataset.editado;
        }
    });

    montoAdeudado.addEventListener('input', function () {
        montoAdeudado.dataset.editado = '1';
    });

    // --- Confirmar venta ---

    btnConfirmar.addEventListener('click', function () {
        if (Object.keys(carrito).length === 0) {
            mostrarError('No puedes confirmar una venta con el carrito vacío.');
            return;
        }

        if (checkFiado.checked) {
            if (!nombreClienteFiado.value.trim()) {
                mostrarError('Ingresa el nombre del cliente para la venta a crédito.');
                nombreClienteFiado.focus();
                return;
            }
            const monto = parseInt(montoAdeudado.value, 10);
            if (!monto || monto <= 0) {
                mostrarError('La cantidad adeudada debe ser mayor a cero.');
                montoAdeudado.focus();
                return;
            }
        }

        const total = obtenerTotalCarrito();
        document.getElementById('modal-total-texto').textContent =
            'Total a registrar: ' + formatoPesos(total);

        const tipoEntrega = obtenerTipoEntrega();
        const esFiado = checkFiado.checked;
        let resumenHtml = '<div class="mt-3 pt-3 border-top">';
        resumenHtml += '<p class="mb-1"><strong>Entrega:</strong> ' +
            (tipoEntrega === 'domicilio' ? 'Domicilio' : 'Comprado en Tienda') + '</p>';
        if (esFiado) {
            resumenHtml += '<p class="mb-1 text-warning-emphasis"><strong>Fiado:</strong> ' +
                nombreClienteFiado.value.trim() + '</p>';
            resumenHtml += '<p class="mb-0"><strong>Adeudado:</strong> ' +
                formatoPesos(parseInt(montoAdeudado.value, 10)) + '</p>';
        }
        resumenHtml += '</div>';
        document.getElementById('modal-resumen-opciones').innerHTML = resumenHtml;

        modalConfirmar.show();
    });

    document.getElementById('btn-modal-si').addEventListener('click', async function () {
        const btnSi = this;
        btnSi.disabled = true;
        btnConfirmar.disabled = true;

        const items = Object.values(carrito).map(function (item) {
            return { producto_id: item.producto.id, cantidad: item.cantidad };
        });

        const payload = {
            items: items,
            tipo_entrega: obtenerTipoEntrega(),
            es_fiado: checkFiado.checked,
        };

        if (checkFiado.checked) {
            payload.nombre_cliente_fiado = nombreClienteFiado.value.trim();
            payload.monto_adeudado = parseInt(montoAdeudado.value, 10);
        }

        try {
            const datos = await peticion('/api/ventas/confirmar/', {
                method: 'POST',
                body: JSON.stringify(payload),
            });

            modalConfirmar.hide();

            // Limpiar carrito y opciones
            Object.keys(carrito).forEach(function (k) { delete carrito[k]; });
            checkFiado.checked = false;
            formularioFiado.classList.add('d-none');
            nombreClienteFiado.value = '';
            montoAdeudado.value = '';
            delete montoAdeudado.dataset.editado;
            document.getElementById('entrega-tienda').checked = true;
            actualizarCarrito();
            cargarProductos('');

            // Mostrar factura
            mostrarFactura(datos.venta);

            // Mensaje de éxito grande
            mostrarExito(datos.mensaje);

        } catch (err) {
            modalConfirmar.hide();
            mostrarError(err.message);
        } finally {
            btnSi.disabled = false;
            btnConfirmar.disabled = Object.keys(carrito).length === 0;
        }
    });

    function mostrarFactura(venta) {
        let infoExtra = '<p class="fs-5 mb-1"><strong>Entrega:</strong> ' + venta.tipo_entrega_display + '</p>';
        if (venta.es_fiado) {
            infoExtra += '<div class="alert alert-warning mt-2 mb-3">';
            infoExtra += '<strong>Venta a crédito (Fiado)</strong><br>';
            infoExtra += 'Cliente: ' + venta.nombre_cliente_fiado + '<br>';
            infoExtra += 'Monto adeudado: ' + venta.monto_adeudado_formateado;
            infoExtra += '</div>';
        }

        const html = `
            <div id="area-imprimir">
                <h3 class="mb-3">Factura #${venta.id}</h3>
                <p class="fs-5">Fecha: ${venta.fecha}</p>
                ${infoExtra}
                <table class="table table-lg">
                    <thead>
                        <tr>
                            <th>Producto</th>
                            <th>Cant.</th>
                            <th>Precio</th>
                            <th>Subtotal</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${venta.detalles.map(function (d) {
                            return `<tr>
                                <td>${d.nombre}</td>
                                <td>${d.cantidad}</td>
                                <td>${d.precio_unitario_formateado}</td>
                                <td>${d.subtotal_formateado}</td>
                            </tr>`;
                        }).join('')}
                    </tbody>
                    <tfoot>
                        <tr class="fila-total">
                            <td colspan="3" class="text-end fw-bold fs-4">Total:</td>
                            <td class="fw-bold fs-4">${venta.total_formateado}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        `;
        document.getElementById('contenido-factura').innerHTML = html;
        modalFactura.show();
    }

    document.getElementById('btn-imprimir-factura').addEventListener('click', function () {
        window.print();
    });

    // --- Anular última venta ---

    btnAnular.addEventListener('click', function () {
        modalAnular.show();
    });

    document.getElementById('btn-modal-anular-si').addEventListener('click', async function () {
        const btnSi = this;
        btnSi.disabled = true;

        try {
            const datos = await peticion('/api/ventas/anular-ultima/', { method: 'POST' });
            modalAnular.hide();
            mostrarExito(datos.mensaje);
            cargarProductos(buscador.value.trim());
        } catch (err) {
            modalAnular.hide();
            mostrarError(err.message);
        } finally {
            btnSi.disabled = false;
        }
    });

    // --- Cerrar mensajes ---

    document.getElementById('btn-cerrar-exito').addEventListener('click', function () {
        document.getElementById('mensaje-exito').classList.add('d-none');
    });

    document.getElementById('btn-cerrar-error').addEventListener('click', ocultarError);

    // --- Inicio: cargar productos al abrir la página ---
    cargarProductos('');

})();
