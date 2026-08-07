"""
Formularios con validaciones claras para el inventario.
Todas las reglas importantes se repiten aquí (no solo en JavaScript).
"""
from django import forms

from .models import Producto, Proveedor


class ProveedorForm(forms.ModelForm):
    """Formulario simple para crear o editar un proveedor."""

    class Meta:
        model = Proveedor
        fields = ['nombre', 'contacto']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Nombre del proveedor',
            }),
            'contacto': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Teléfono o correo',
            }),
        }


class ProductoForm(forms.ModelForm):
    """Formulario para agregar o editar productos del inventario."""

    class Meta:
        model = Producto
        fields = ['nombre', 'precio', 'cantidad_stock', 'proveedor', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Nombre del producto',
            }),
            'precio': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'min': '0',
                'step': '1',
                'placeholder': 'Precio en pesos',
            }),
            'cantidad_stock': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'min': '0',
                'step': '1',
                'placeholder': 'Cantidad disponible',
            }),
            'proveedor': forms.Select(attrs={
                'class': 'form-select form-select-lg',
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input fs-4',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo mostrar "activo" al editar (para reactivar productos desactivados)
        if not self.instance.pk:
            self.fields.pop('activo')

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre', '').strip()
        if not nombre:
            raise forms.ValidationError('Debes escribir el nombre del producto.')
        return nombre

    def clean_precio(self):
        precio = self.cleaned_data.get('precio')
        if precio is not None and precio < 0:
            raise forms.ValidationError('El precio no puede ser negativo.')
        return precio

    def clean_cantidad_stock(self):
        cantidad = self.cleaned_data.get('cantidad_stock')
        if cantidad is not None and cantidad < 0:
            raise forms.ValidationError('La cantidad no puede ser negativa.')
        return cantidad


class FiltroFechasForm(forms.Form):
    """Filtro por rango de fechas en el historial de ventas."""

    fecha_desde = forms.DateField(
        required=False,
        label='Desde',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control form-control-lg',
        }),
    )
    fecha_hasta = forms.DateField(
        required=False,
        label='Hasta',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control form-control-lg',
        }),
    )

    def clean(self):
        datos = super().clean()
        desde = datos.get('fecha_desde')
        hasta = datos.get('fecha_hasta')
        if desde and hasta and desde > hasta:
            raise forms.ValidationError(
                'La fecha "Desde" no puede ser posterior a la fecha "Hasta".'
            )
        return datos


class ReporteMesForm(forms.Form):
    """Selección de mes y año para generar reporte bajo demanda."""

    MESES = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
    ]

    mes = forms.ChoiceField(
        choices=MESES,
        label='Mes',
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
    )
    anio = forms.IntegerField(
        label='Año',
        min_value=2020,
        max_value=2100,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Ej: 2026',
        }),
    )
