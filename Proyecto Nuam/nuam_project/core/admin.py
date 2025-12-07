from django.contrib import admin
from .models import Mercado, Instrumento, CalificacionTributaria

admin.site.register(Mercado)
admin.site.register(Instrumento)
admin.site.register(CalificacionTributaria)
