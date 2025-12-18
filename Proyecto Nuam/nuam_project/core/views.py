from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from decimal import Decimal, InvalidOperation
import logging
from .models import CalificacionTributaria, Instrumento
from .utils import obtener_configuracion_certificado, procesar_carga_masiva
from django.db.models import Max

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
            'monto_historico': str(calif.monto_historico),
            # Factores (08-37)
            **{f'factor_{i:02d}': str(getattr(calif, f'factor_{i:02d}')) for i in range(8, 38)}
        }
        return JsonResponse({'status': 'ok', 'data': data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'msg': str(e)})

# --- VISTA PRINCIPAL (MANTENEDOR) ---

@login_required
def mantenedor_view(request):
    
    # 1. FUNCIÓN DE LIMPIEZA ROBUSTA
    def limpiar_tributario(valor):
        if not valor: return Decimal('0')
        v = str(valor).strip()
        # Caso 1: Tiene puntos y comas (ej: 1.234,56) -> Quitamos puntos, cambiamos coma
        if "." in v and "," in v:
            v = v.replace(".", "").replace(",", ".")
        # Caso 2: Solo tiene coma (ej: 1,037) -> Cambiamos coma por punto
        elif "," in v:
            v = v.replace(",", ".")
        # Caso 3: Solo tiene puntos (ej: 25.190.244 o 1.037)
        elif "." in v:
            # Si hay más de un punto, son separadores de miles
            if v.count(".") > 1:
                v = v.replace(".", "")
            # Si hay un solo punto, pero es una cifra grande (más de 3 dígitos tras el punto), es miles
            # O si el input es de Monto Histórico (donde no solemos usar decimales)
            # Para mayor seguridad, si el número resultante es > 1000 sin el punto, lo tratamos como miles
            # Pero la regla más segura es: si viene de un input "text" formateado por JS, el punto es MILES.
            else:
                # Si el usuario ingresó 1.037 en el factor, Decimal() lo toma bien como decimal.
                # Si ingresó 25.190 como monto, Decimal() lo toma como 25 coma 19. 
                # Por eso es mejor que el JS en el front elimine puntos al enviar o usar una lógica aquí.
                pass 
        return Decimal(v)

    if request.method == 'POST':
        # A) ELIMINAR
        if 'accion_eliminar' in request.POST:
            id_eliminar = request.POST.get('id_seleccionado')
            if id_eliminar:
                try:
                    obj = CalificacionTributaria.objects.get(id=id_eliminar) if request.user.is_superuser else CalificacionTributaria.objects.get(id=id_eliminar, usuario=request.user)
                    obj.delete()
                    messages.success(request, "Registro eliminado correctamente.")
                except CalificacionTributaria.DoesNotExist:
                    messages.error(request, "Error: No se encontró el registro.")
            return redirect('mantenedor')
        
        # B) GUARDAR
        else:
            try:
                with transaction.atomic():
                    id_edicion = request.POST.get('id_edicion')
                    if id_edicion:
                        nueva = get_object_or_404(CalificacionTributaria, id=id_edicion) if request.user.is_superuser else get_object_or_404(CalificacionTributaria, id=id_edicion, usuario=request.user)
                    else:
                        nueva = CalificacionTributaria(usuario=request.user, origen='Corredor')

                    # --- 1. DATOS BÁSICOS ---
                    nueva.rut_propietario = request.POST.get('rut_propietario')
                    nueva.instrumento_id = request.POST.get('instrumento')
                    nueva.ejercicio = request.POST.get('ejercicio')
                    nueva.fecha_pago = request.POST.get('fecha_pago')
                    nueva.descripcion = request.POST.get('descripcion')
                    nueva.secuencia = request.POST.get('secuencia') or 0
                    nueva.es_isfut = request.POST.get('es_isfut') == 'on'

                    # --- 2. LÓGICA DE MONTOS (LIMPIEZA APLICADA) ---
                    nueva.monto_historico = limpiar_tributario(request.POST.get('monto_historico'))
                    nueva.factor_actualizacion = limpiar_tributario(request.POST.get('factor_actualizacion'))
                    
                    # Recalculamos el total en el servidor para evitar errores del front
                    nueva.monto_total = nueva.monto_historico * nueva.factor_actualizacion

                    # --- 3. CÁLCULO DE FACTORES (Paso 2) ---
                    suma_bases = Decimal(0)
                    for i in range(8, 38):
                        input_name = f'f{i:02d}'
                        db_field = f'factor_{i:02d}'
                        monto_ingresado = limpiar_tributario(request.POST.get(input_name))
                        
                        if nueva.monto_total > 0:
                            factor_calculado = monto_ingresado / nueva.monto_total
                        else:
                            factor_calculado = Decimal('0')
                        
                        setattr(nueva, db_field, factor_calculado)
                        if 8 <= i <= 19: suma_bases += factor_calculado

                    if suma_bases > Decimal('1.0001'): 
                        messages.warning(request, f"Advertencia: Suma de rentas supera 100% ({suma_bases:.4f}).")

                    nueva.save()
                    messages.success(request, "✅ Registro guardado correctamente.")
                    return redirect('mantenedor')

            except Exception as e:
                messages.error(request, f"Error al guardar: {e}")
                return redirect('mantenedor')

    # 2. LOGICA GET
    calificaciones = CalificacionTributaria.objects.all() if request.user.is_superuser else CalificacionTributaria.objects.filter(usuario=request.user)
    calificaciones = calificaciones.order_by('-created_at')
    
    # Filtros
    q_mercado = request.GET.get('q_mercado')
    q_origen = request.GET.get('q_origen')
    q_ejercicio = request.GET.get('q_ejercicio')

    if q_mercado: calificaciones = calificaciones.filter(instrumento__mercado__nombre__icontains=q_mercado)
    if q_origen: calificaciones = calificaciones.filter(origen__iexact=q_origen)
    if q_ejercicio: calificaciones = calificaciones.filter(ejercicio=q_ejercicio)

    instrumentos = Instrumento.objects.all().order_by('codigo')
    max_id = CalificacionTributaria.objects.aggregate(Max('id'))['id__max'] or 0
    
    return render(request, 'core/mantenedor.html', {
        'calificaciones': calificaciones,
        'instrumentos': instrumentos,
        'grupos': obtener_configuracion_certificado(), 
        'rango_factores': range(8, 38),
        'proximo_id': max_id + 1
    })

@login_required
def carga_masiva_view(request):
    if request.method == 'POST' and request.FILES.get('archivo_excel'):
        archivo = request.FILES['archivo_excel']
        guardados, errores = procesar_carga_masiva(archivo, request.user)
        if guardados > 0: messages.success(request, f"✅ Se cargaron {guardados} registros.")
        if errores:
            for error in errores[:3]: messages.error(request, error)
    return redirect('mantenedor')