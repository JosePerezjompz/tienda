"""
Funciones auxiliares reutilizables en vistas y templates.
"""
from django.conf import settings


def formato_pesos(valor):
    """
    Formatea un número entero como pesos colombianos.
    Ejemplo: 15000 -> "$15.000"
    """
    if valor is None:
        valor = 0
    return f'${int(valor):,}'.replace(',', '.')


def estado_stock(cantidad):
    """
    Devuelve el color Bootstrap y el texto descriptivo según el stock.
    Usado en la lista de inventario para indicadores visuales claros.
    """
    if cantidad < settings.STOCK_CRITICO:
        return 'danger', f'Stock crítico: {cantidad} unidades'
    if cantidad < settings.STOCK_BAJO:
        return 'warning', 'Stock bajo'
    if cantidad < settings.STOCK_ATENCION:
        return 'yellow', 'Atención'
    return 'success', 'Stock normal'
