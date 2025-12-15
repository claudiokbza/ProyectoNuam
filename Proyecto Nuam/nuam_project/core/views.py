from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from decimal import Decimal
import logging
from django.shortcuts import render, redirect
from .models import CalificacionTributaria
from .utils import obtener_configuracion_certificado 
from django.db.models import Max

from .models import CalificacionTributaria, Instrumento
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

# --- AJAX: OBTENER DATOS PARA MODIFICAR ---
@login_required
def obtener_detalle_view(request, id):
    try:
        # NEW LOGIC: Si es Admin, puede pedir cualquier ID. Si no, solo los suyos.
        if request.user.is_superuser:
            calif = CalificacionTributaria.objects.get(id=id)
        else:
            calif = CalificacionTributaria.objects.get(id=id, usuario=request.user)
        
        data = {
            'id': calif.id,
            'instrumento_id': calif.instrumento.id,
            'ejercicio': calif.ejercicio,
            'fecha_pago': calif.fecha_pago.strftime('%Y-%m-%d') if calif.fecha_pago else '',
            'monto_total': str(calif.monto_total),
            'descripcion': calif.descripcion or '',
            'secuencia': calif.secuencia,
            'es_isfut': calif.es_isfut,
            'factor_actualizacion': str(calif.factor_actualizacion),
            # Factores
            'factor_08': str(calif.factor_08),
            'factor_09': str(calif.factor_09),
            'factor_10': str(calif.factor_10),
            'factor_11': str(calif.factor_11),
            'factor_12': str(calif.factor_12),
            'factor_13': str(calif.factor_13),
            'factor_14': str(calif.factor_14),
            'factor_15': str(calif.factor_15),
            'factor_16': str(calif.factor_16),
            'factor_17': str(calif.factor_17),
            'factor_18': str(calif.factor_18),
            'factor_19': str(calif.factor_19),
            'factor_20': str(calif.factor_20),
            'factor_21': str(calif.factor_21),
            'factor_22': str(calif.factor_22),
            'factor_23': str(calif.factor_23),
            'factor_24': str(calif.factor_24),
            'factor_25': str(calif.factor_25),
            'factor_26': str(calif.factor_26),
            'factor_27': str(calif.factor_27),
            'factor_28': str(calif.factor_28),
            'factor_29': str(calif.factor_29),
            'factor_30': str(calif.factor_30),
            'factor_31': str(calif.factor_31),
            'factor_32': str(calif.factor_32),
            'factor_33': str(calif.factor_33),
            'factor_34': str(calif.factor_34),
            'factor_35': str(calif.factor_35),
            'factor_36': str(calif.factor_36),
            'factor_37': str(calif.factor_37),
        }
        return JsonResponse({'status': 'ok', 'data': data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'msg': str(e)})

# --- VISTA PRINCIPAL (MANTENEDOR) ---

@login_required
def mantenedor_view(request):
    
    # 1. LOGICA POST (GUARDAR / ELIMINAR)
    if request.method == 'POST':
        
        # A) ELIMINAR (Se mantiene igual)
        if 'accion_eliminar' in request.POST:
            id_eliminar = request.POST.get('id_seleccionado')
            if id_eliminar:
                try:
                    if request.user.is_superuser:
                        obj = CalificacionTributaria.objects.get(id=id_eliminar)
                    else:
                        obj = CalificacionTributaria.objects.get(id=id_eliminar, usuario=request.user)
                    
                    obj.delete()
                    messages.success(request, "Registro eliminado correctamente.")
                except CalificacionTributaria.DoesNotExist:
                    messages.error(request, "Error: No se encontró el registro o no tienes permiso.")
            return redirect('mantenedor')

        # B) GUARDAR
        try:
            with transaction.atomic():
                id_edicion = request.POST.get('id_edicion')
                
                if id_edicion:
                    if request.user.is_superuser:
                        nueva = get_object_or_404(CalificacionTributaria, id=id_edicion)
                    else:
                        nueva = get_object_or_404(CalificacionTributaria, id=id_edicion, usuario=request.user)
                else:
                    nueva = CalificacionTributaria()
                    nueva.usuario = request.user
                    nueva.origen = 'Corredor'

                # --- 1. DATOS NUEVOS ---
                nueva.rut_propietario = request.POST.get('rut_propietario') # <--- NUEVO
                nueva.instrumento_id = request.POST.get('instrumento')
                nueva.ejercicio = request.POST.get('ejercicio') # Lo guardamos aunque no lo mostremos
                nueva.fecha_pago = request.POST.get('fecha_pago')
                nueva.descripcion = request.POST.get('descripcion')
                nueva.secuencia = request.POST.get('secuencia') or 0
                nueva.es_isfut = True if request.POST.get('es_isfut') == 'on' else False

                # --- 2. LÓGICA DE MONTOS ---
                # Ahora recibimos Monto Histórico y Factor
                monto_hist = Decimal(request.POST.get('monto_historico') or 0)
                factor_act = Decimal(request.POST.get('factor_actualizacion') or 1)
                
                nueva.monto_historico = monto_hist
                nueva.factor_actualizacion = factor_act
                
                # Calculamos el Actualizado (Base para los factores)
                monto_actualizado_calc = monto_hist * factor_act
                nueva.monto_total = monto_actualizado_calc # Guardamos el actualizado en monto_total

                # --- 3. CÁLCULO DE FACTORES ---
                # Factor = Input ($) / Monto Actualizado
                suma_bases = Decimal(0)
                for i in range(8, 38):
                    input_name = f'f{i:02d}'
                    db_field = f'factor_{i:02d}'
                    monto_ingresado = Decimal(request.POST.get(input_name) or 0)
                    
                    if monto_actualizado_calc > 0:
                        factor_calculado = monto_ingresado / monto_actualizado_calc
                    else:
                        factor_calculado = 0
                    
                    setattr(nueva, db_field, factor_calculado)
                    
                    if 8 <= i <= 19:
                        suma_bases += factor_calculado

                if suma_bases > Decimal('1.0001'): 
                    messages.warning(request, f"Advertencia: Suma de rentas supera 100% ({suma_bases:.4f}).")

                nueva.save()
                messages.success(request, "✅ Registro guardado correctamente.")
                return redirect('mantenedor')

        except Exception as e:
            messages.error(request, f"Error: {e}")
            return redirect('mantenedor')

    # 2. LOGICA GET (MOSTRAR DATOS)
    
    if request.user.is_superuser:
        calificaciones = CalificacionTributaria.objects.all().order_by('-created_at')
    else:
        calificaciones = CalificacionTributaria.objects.filter(usuario=request.user).order_by('-created_at')
    
    # Filtros (Se mantienen igual)
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
    # 🔴 AGREGAR ESTE BLOQUE: CALCULAR EL PRÓXIMO ID 🔴
    max_id_dict = CalificacionTributaria.objects.aggregate(Max('id'))
    max_id = max_id_dict['id__max'] or 0
    proximo_id = max_id + 1

    # 🔴 4. INYECTAR LA CONFIGURACIÓN DE GRUPOS
    grupos_certificado = obtener_configuracion_certificado()

    return render(request, 'core/mantenedor.html', {
        'calificaciones': calificaciones,
        'instrumentos': instrumentos,
        'grupos': grupos_certificado, 
        'rango_factores': range(8, 38),
        'proximo_id': proximo_id
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
            for error in errores[:3]:
                messages.error(request, error)
            if len(errores) > 3:
                messages.warning(request, f"Y {len(errores)-3} errores más.")
    
    return redirect('mantenedor')