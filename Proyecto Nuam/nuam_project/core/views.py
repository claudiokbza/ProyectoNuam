# core/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.db import transaction
from django.contrib import messages
from decimal import Decimal
import logging

from .models import (
    CalificacionTributaria,
    Instrumento,
    Factor,
    CalificacionFactor,
    Cliente
)

from .utils import procesar_carga_masiva
from django.contrib.auth.forms import AuthenticationForm

# Configuración básica del logger
logger = logging.getLogger(__name__)

# -------------------------
# REDIRECCIÓN INICIAL
# -------------------------
def mantenedor_redirect(request):
    if request.user.is_authenticated:
        return redirect('mantenedor')
    return redirect('login')


# -------------------------
# LOGIN
# -------------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect('mantenedor')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('mantenedor')
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")

    return render(request, 'core/login.html')


# -------------------------
# LOGOUT
# -------------------------
@login_required
def logout_view(request):
    logger.info(f"Usuario {request.user.username} ha cerrado sesión.")
    logout(request)
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect('login')


# -------------------------
# VISTA PRINCIPAL
# -------------------------
@login_required
def mantenedor_view(request):

    # Obtener datos existentes
    calificaciones = CalificacionTributaria.objects.all().order_by('-fecha_creacion')
    instrumentos = Instrumento.objects.all()
    clientes = Cliente.objects.all()
    factores = Factor.objects.all().order_by('order_index')

    if request.method == 'POST':

        try:
            with transaction.atomic():

                cliente_id = request.POST.get('cliente')
                instrumento_id = request.POST.get('instrumento')
                fecha_pago = request.POST.get('fecha_pago')
                descripcion = request.POST.get('descripcion', '')

                nueva_calificacion = CalificacionTributaria.objects.create(
                    cliente_id=cliente_id,
                    instrumento_id=instrumento_id if instrumento_id else None,
                    fecha_pago=fecha_pago,
                    descripcion=descripcion,
                    usuario_crea=None  # opcional, puedes enlazar después
                )

                # -------- VALIDACIÓN FACTORES CRÍTICOS F08 - F19 --------
                suma_credito = Decimal('0.0')
                factores_criticos = [
                    f.codigo_factor for f in Factor.objects.filter(
                        codigo_factor__in=[f"F{str(i).zfill(2)}" for i in range(8, 20)]
                    )
                ]

                for codigo in factores_criticos:
                    field_name = f"factor_{int(codigo[1:])}"
                    valor = Decimal(request.POST.get(field_name) or '0.0')
                    suma_credito += valor

                if suma_credito > Decimal('1.0'):
                    messages.error(
                        request,
                        f"⚠️ La suma de factores F08-F19 es {suma_credito} y no puede ser mayor a 1.0"
                    )
                    transaction.set_rollback(True)
                    return redirect('mantenedor')

                # -------- GUARDADO DE FACTORES --------
                for factor in factores:
                    field_name = f"factor_{factor.codigo_factor[1:]}"
                    valor = request.POST.get(field_name)

                    if valor:
                        CalificacionFactor.objects.create(
                            calificacion=nueva_calificacion,
                            factor=factor,
                            valor=Decimal(valor)
                        )

                messages.success(request, "✅ Calificación guardada con éxito.")
                logger.info(f"Calificación creada por {request.user.username}")

        except Exception as e:
            logger.error(f"❌ Error al guardar: {e}")
            messages.error(request, f"Error al guardar: {e}")

        return redirect('mantenedor')

    return render(request, 'core/mantenedor.html', {
        'calificaciones': calificaciones,
        'instrumentos': instrumentos,
        'clientes': clientes,
        'factores': factores
    })


# -------------------------
# CARGA MASIVA
# -------------------------
@login_required
def carga_masiva_view(request):

    if request.method == 'POST' and request.FILES.get('archivo_excel'):

        archivo = request.FILES['archivo_excel']

        guardados, errores = procesar_carga_masiva(archivo, request.user)

        if guardados > 0:
            messages.success(request, f"✅ Se cargaron {guardados} registros correctamente.")

        if errores:
            for error in errores[:5]:
                messages.error(request, error)

            if len(errores) > 5:
                messages.warning(request, f"Y {len(errores)-5} errores más.")

    return redirect('mantenedor')
