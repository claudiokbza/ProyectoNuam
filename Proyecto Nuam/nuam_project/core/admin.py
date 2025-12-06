# core/admin.py
from django.contrib import admin
from .models import Mercado, Instrumento, CalificacionTributaria

@admin.register(Mercado)
class MercadoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre')

@admin.register(Instrumento)
class InstrumentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'mercado')
    search_fields = ('codigo', 'nombre')

@admin.register(CalificacionTributaria)
class CalificacionAdmin(admin.ModelAdmin):
    # Esto permite ver las columnas clave en la lista
    list_display = ('id', 'instrumento', 'ejercicio', 'usuario', 'monto_total', 'created_at')
    # Filtros laterales
    list_filter = ('ejercicio', 'usuario', 'origen')
    # Barra de búsqueda
    search_fields = ('instrumento__codigo', 'usuario__username')