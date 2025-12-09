from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db import transaction
from decimal import Decimal
import logging

# Importamos tus modelos (Asegúrate de que en models.py sean estos nombres)
from .models import CalificacionTributaria, Instrumento

# Importamos la función de carga masiva (que creamos en el paso anterior)
from .utils import procesar_carga_masiva

logger = logging.getLogger(__name__)

# --- REDIRECCIÓN Y LOGIN ---

def mantenedor_redirect(request):
    if request.user.is_authenticated:
        return redirect('mantenedor')
    return redirect('login')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('mantenedor')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('mantenedor')
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    return render(request, 'core/login.html')

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

# --- VISTA PRINCIPAL (MANTENEDOR) ---

@login_required
def mantenedor_view(request):
    # 1. LOGICA DE ELIMINAR (POST desde el botón de abajo)
    if request.method == 'POST' and 'accion_eliminar' in request.POST:
        id_eliminar = request.POST.get('id_seleccionado')
        if id_eliminar:
            try:
                # Seguridad R1: Solo borra si es del usuario
                calif = CalificacionTributaria.objects.get(id=id_eliminar, usuario=request.user)
                calif.delete()
                messages.success(request, "Registro eliminado correctamente.")
            except CalificacionTributaria.DoesNotExist:
                messages.error(request, "No se encontró el registro o no tienes permiso.")
        return redirect('mantenedor')

    # 2. LOGICA DE FILTROS Y BÚSQUEDA
    calificaciones = CalificacionTributaria.objects.filter(usuario=request.user).order_by('-created_at')
    
    # Capturamos filtros del GET
    q_mercado = request.GET.get('q_mercado')
    q_origen = request.GET.get('q_origen')
    q_ejercicio = request.GET.get('q_ejercicio')

    if q_mercado:
        calificaciones = calificaciones.filter(instrumento__mercado__nombre__icontains=q_mercado)
    if q_origen:
        calificaciones = calificaciones.filter(origen__iexact=q_origen)
    if q_ejercicio:
        calificaciones = calificaciones.filter(ejercicio=q_ejercicio)

    instrumentos = Instrumento.objects.all().order_by('codigo')

    #POST: Guardar nueva calificación manual
    if request.method == 'POST':
        try:
            with transaction.atomic():
                nueva = CalificacionTributaria()
                nueva.usuario = request.user
                
                # --- CAMBIO: RECIBIR ID DIRECTO ---
                inst_id = request.POST.get('instrumento') # Recibe el número (ID)
                
                if not inst_id:
                    raise Exception("Debe seleccionar un instrumento de la lista.")

                # Asignamos el ID directamente (Django lo entiende)
                nueva.instrumento_id = inst_id
                nueva.ejercicio = request.POST.get('ejercicio')
                nueva.fecha_pago = request.POST.get('fecha_pago')
                nueva.descripcion = request.POST.get('descripcion')
                nueva.monto_total = Decimal(request.POST.get('monto_total') or 0)
                nueva.origen = 'Corredor'  # Por defecto

                # Capturar Factores (Del 08 al 37)
                # Usamos un bucle para limpiar el código, o asignación directa
                suma_creditos = Decimal(0)
                
                # Factores Crédito (F08-F19)
                for i in range(8, 20):
                    field_name = f'factor_{i:02d}' # factor_08, factor_09...
                    valor = Decimal(request.POST.get(field_name) or 0)
                    setattr(nueva, field_name, valor)
                    suma_creditos += valor
                
                # Validación R2 (Suma <= 1.0)
                if suma_creditos > Decimal('1.00000000'):
                    messages.error(request, f"Error: La suma de factores (F08-F19) es {suma_creditos} y excede 1.0")
                    # Retornamos sin guardar
                    return render(request, 'core/mantenedor.html', {
                        'calificaciones': calificaciones, 'instrumentos': instrumentos
                    })

                # Factores Restantes (F20-F37)
                for i in range(20, 38):
                    field_name = f'factor_{i:02d}'
                    valor = Decimal(request.POST.get(field_name) or 0)
                    setattr(nueva, field_name, valor)

                nueva.save()
                messages.success(request, "✅ Calificación guardada correctamente.")
                return redirect('mantenedor')

        except Exception as e:
            messages.error(request, f"Error al guardar: {e}")

    return render(request, 'core/mantenedor.html', {
        'calificaciones': calificaciones,
        'instrumentos': instrumentos
    })

# --- VISTA CARGA MASIVA ---

@login_required
def carga_masiva_view(request):
    if request.method == 'POST' and request.FILES.get('archivo_excel'):
        archivo = request.FILES['archivo_excel']
        guardados, errores = procesar_carga_masiva(archivo, request.user)
        
        if guardados > 0:
            messages.success(request, f"✅ Se cargaron {guardados} registros exitosamente.")
        
        if errores:
            for error in errores[:3]: # Mostrar solo primeros 3 errores
                messages.error(request, error)
            if len(errores) > 3:
                messages.warning(request, f"Y {len(errores)-3} errores más.")
    
    return redirect('mantenedor')