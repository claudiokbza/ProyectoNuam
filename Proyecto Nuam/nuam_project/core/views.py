# core/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.db import transaction
from django.contrib import messages
from decimal import Decimal
import logging
from .models import CalificacionTributaria, Instrumento
from .utils import procesar_carga_masiva

# Configuración básica del logger para LogAuditoria (Informe Punto 5.2)
logger = logging.getLogger(__name__)

# --- VISTAS DE AUTENTICACIÓN ---

# Esta vista redirige al login si no está autenticado
def mantenedor_redirect(request):
    if request.user.is_authenticated:
        return redirect('mantenedor')
    return redirect('login')


def login_view(request):
    # Usen el sistema de autenticación de Django aquí
    # (Usar una vista simple para el proyecto es suficiente)
    if request.method == 'POST':
        # ... lógica de autenticación ...
        pass
    return render(request, 'core/login.html') # Crear este template es tarea pendiente

@login_required
def logout_view(request):
    logger.info(f"Usuario {request.user.username} ha cerrado sesión.")
    logout(request)
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect('login')

# --- VISTA PRINCIPAL (EL CORAZÓN DEL PROYECTO) ---

@login_required # Seguridad: Solo usuarios logueados pueden acceder
def mantenedor_view(request):
    
    # 1. SEGURIDAD R1: AISLAMIENTO DE DATOS (MÉTODO GET: MOSTRAR DATOS)
    # Solo mostramos las calificaciones que pertenecen al usuario actual.
    calificaciones = CalificacionTributaria.objects.filter(usuario=request.user).order_by('-ejercicio', '-fecha_pago')
    
    # Necesitamos cargar los Instrumentos para el SELECT del formulario
    instrumentos = Instrumento.objects.all()

    # -----------------------------------------------------
    # 2. CREACIÓN (MÉTODO POST: GUARDAR DATOS)
    # -----------------------------------------------------
    if request.method == 'POST':
        
        # Obtenemos los datos del formulario (Modal)
        instrumento_id = request.POST.get('instrumento')
        ejercicio = request.POST.get('ejercicio')
        fecha_pago = request.POST.get('fecha_pago')
        
        # Lista de factores críticos para la validación (Informe R2)
        factores_criticos = [f'factor_{i}' for i in range(8, 20)] # F08 a F19

        try:
            # Transacción (Mitigación R3): Si algo falla, se revierte todo
            with transaction.atomic():
                
                nueva_calificacion = CalificacionTributaria()
                
                # 2.1. APLICAR SEGURIDAD R1 (Asignar Dueño)
                nueva_calificacion.usuario = request.user 
                
                # 2.2. Asignar datos maestros
                nueva_calificacion.instrumento_id = instrumento_id
                nueva_calificacion.ejercicio = ejercicio
                nueva_calificacion.fecha_pago = fecha_pago
                nueva_calificacion.origen = 'Manual'
                
                # 2.3. Asignar Factores y VALIDAR R2 (Suma <= 1.0)
                suma_factores_credito = Decimal('0.0')

                for factor_name in factores_criticos:
                    valor_str = request.POST.get(factor_name) or '0.0'
                    valor_decimal = Decimal(valor_str)
                    
                    # Asignar el valor al modelo
                    setattr(nueva_calificacion, factor_name, valor_decimal)
                    
                    # Sumar para la validación crítica
                    suma_factores_credito += valor_decimal
                
                # VALIDACIÓN CRÍTICA R2: Suma de factores de crédito
                if suma_factores_credito > Decimal('1.00000000'):
                    messages.error(request, f"Error de Regla de Negocio: La suma de factores (F08-F19) es {suma_factores_credito.quantize(Decimal('0.00000001'))} y excede el 1.0 permitido.")
                    # Como estamos en transaction.atomic(), la BD se mantiene limpia
                    return render(request, 'core/mantenedor.html', {'calificaciones': calificaciones, 'instrumentos': instrumentos})

                # PESTAÑA 3: RENTAS (F20 - F29)
                nueva_calificacion.factor_20 = Decimal(request.POST.get('factor_20') or '0.0')
                nueva_calificacion.factor_21 = Decimal(request.POST.get('factor_21') or '0.0')
                nueva_calificacion.factor_22 = Decimal(request.POST.get('factor_22') or '0.0')
                nueva_calificacion.factor_23 = Decimal(request.POST.get('factor_23') or '0.0')
                nueva_calificacion.factor_24 = Decimal(request.POST.get('factor_24') or '0.0')
                nueva_calificacion.factor_25 = Decimal(request.POST.get('factor_25') or '0.0')
                nueva_calificacion.factor_26 = Decimal(request.POST.get('factor_26') or '0.0')
                nueva_calificacion.factor_27 = Decimal(request.POST.get('factor_27') or '0.0')
                nueva_calificacion.factor_28 = Decimal(request.POST.get('factor_28') or '0.0')
                nueva_calificacion.factor_29 = Decimal(request.POST.get('factor_29') or '0.0')

                # PESTAÑA 4: OTROS (F30 - F37)
                nueva_calificacion.factor_30 = Decimal(request.POST.get('factor_30') or '0.0')
                nueva_calificacion.factor_31 = Decimal(request.POST.get('factor_31') or '0.0')
                nueva_calificacion.factor_32 = Decimal(request.POST.get('factor_32') or '0.0')
                nueva_calificacion.factor_33 = Decimal(request.POST.get('factor_33') or '0.0')
                nueva_calificacion.factor_34 = Decimal(request.POST.get('factor_34') or '0.0')
                nueva_calificacion.factor_35 = Decimal(request.POST.get('factor_35') or '0.0')
                nueva_calificacion.factor_36 = Decimal(request.POST.get('factor_36') or '0.0')
                nueva_calificacion.factor_37 = Decimal(request.POST.get('factor_37') or '0.0')

                # Asignar datos monetarios (Pestaña 1 - Generales)
                # Ojo: Asegúrense de que en el HTML el input se llame "monto_total"
                nueva_calificacion.monto_total = Decimal(request.POST.get('monto_total') or '0.0')
                nueva_calificacion.descripcion = request.POST.get('descripcion', '')
                
                nueva_calificacion.save()
                logger.info(f"Calificación creada por {request.user.username}: {nueva_calificacion.id}")
                messages.success(request, "Calificación tributaria guardada con éxito.")

        except Exception as e:
            # Manejo de error genérico (Mitigación E4)
            logger.error(f"Error al guardar calificación por {request.user.username}: {e}")
            messages.error(request, f"Ocurrió un error al guardar: {e}")
            
        return redirect('mantenedor')

    # Retorna la página al método GET
    return render(request, 'core/mantenedor.html', {
        'calificaciones': calificaciones,
        'instrumentos': instrumentos # Pasamos los instrumentos al template
    })

# --- VISTA DE CARGA MASIVA (ARCHIVO EXCEL) ---
@login_required
def carga_masiva_view(request):
    if request.method == 'POST' and request.FILES.get('archivo_excel'):
        archivo = request.FILES['archivo_excel']
        
        # LLAMAMOS A LA FUNCIÓN DE PANDAS
        guardados, errores = procesar_carga_masiva(archivo, request.user)
        
        # Feedback al usuario
        if guardados > 0:
            messages.success(request, f"Se cargaron {guardados} registros correctamente.")
        
        if errores:
            # Mostrar errores (podrían ser muchos, mostramos los primeros 5)
            for error in errores[:5]:
                messages.error(request, error)
            if len(errores) > 5:
                messages.warning(request, f"Y {len(errores)-5} errores más.")
                
    return redirect('mantenedor')