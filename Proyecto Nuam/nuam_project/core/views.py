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

# --- FUNCIONES DE APOYO ---

def limpiar_tributario(valor):
    """
    Elimina puntos de miles y convierte comas en puntos decimales 
    para asegurar que la magnitud del número sea correcta.
    """
    if not valor: return Decimal('0')
    # Quitamos TODOS los puntos (separadores de miles) para evitar que 1.040 sea 1,04
    v = str(valor).strip().replace('.', '') 
    if "," in v:
        v = v.replace(",", ".") # La coma se vuelve el punto decimal técnico
    try:
        return Decimal(v)
    except (InvalidOperation, ValueError):
        return Decimal('0')

# --- AJAX: OBTENER DATOS PARA MODIFICAR ---
@login_required
def obtener_detalle_view(request, id):
    try:
        calif = CalificacionTributaria.objects.get(id=id) if request.user.is_superuser else CalificacionTributaria.objects.get(id=id, usuario=request.user)
        
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
            # CORRECCIÓN: Forzamos exactamente 6 decimales para el modal
            **{f'factor_{i:02d}': "{:.6f}".format(getattr(calif, f'factor_{i:02d}')).replace('.', ',') for i in range(8, 38)}
        }
        return JsonResponse({'status': 'ok', 'data': data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'msg': str(e)})

# --- VISTA PRINCIPAL (MANTENEDOR) ---

@login_required
def mantenedor_view(request):
    if request.method == 'POST':
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
        
        else:
            try:
                with transaction.atomic():
                    id_edicion = request.POST.get('id_edicion')
                    if id_edicion:
                        nueva = get_object_or_404(CalificacionTributaria, id=id_edicion) if request.user.is_superuser else get_object_or_404(CalificacionTributaria, id=id_edicion, usuario=request.user)
                    else:
                        nueva = CalificacionTributaria(usuario=request.user, origen='Corredor')

                    # 1. Asignación de datos básicos
                    nueva.rut_propietario = request.POST.get('rut_propietario')
                    nueva.instrumento_id = request.POST.get('instrumento')
                    nueva.ejercicio = request.POST.get('ejercicio')
                    nueva.fecha_pago = request.POST.get('fecha_pago') or None
                    nueva.descripcion = request.POST.get('descripcion')
                    nueva.secuencia = request.POST.get('secuencia') or 0
                    nueva.es_isfut = request.POST.get('es_isfut') == 'on'
                    nueva.monto_historico = limpiar_tributario(request.POST.get('monto_historico'))
                    nueva.factor_actualizacion = limpiar_tributario(request.POST.get('factor_actualizacion'))
                    
                    # GUARDADO 1: Activa el cálculo de monto_total en el modelo
                    nueva.save() 

                    # 2. Cálculo de factores con precisión de 6 decimales
                    seis_dec = Decimal('0.000001') 

                    for i in range(8, 38):
                        # Obtenemos monto de entrada y lo limpiamos
                        monto_f = limpiar_tributario(request.POST.get(f'f{i:02d}'))
                        
                        if nueva.monto_total > 0:
                            # Calculamos y redondeamos a 6 decimales
                            factor_calc = (monto_f / nueva.monto_total).quantize(seis_dec, rounding='ROUND_HALF_UP')
                            setattr(nueva, f'factor_{i:02d}', factor_calc)
                        else:
                            setattr(nueva, f'factor_{i:02d}', Decimal('0.000000'))

                    # GUARDADO FINAL
                    nueva.save() 
                    messages.success(request, "✅ Registro guardado con éxito.")
                    return redirect('mantenedor')

            except Exception as e:
                messages.error(request, f"Error al guardar: {e}")
                return redirect('mantenedor')

    # Lógica GET para cargar la tabla
    calificaciones = CalificacionTributaria.objects.all() if request.user.is_superuser else CalificacionTributaria.objects.filter(usuario=request.user)
    calificaciones = calificaciones.order_by('-created_at')
    
    # Filtros (Mantenidos igual)
    q_mercado = request.GET.get('q_mercado')
    if q_mercado: calificaciones = calificaciones.filter(instrumento__mercado__nombre__icontains=q_mercado)

    return render(request, 'core/mantenedor.html', {
        'calificaciones': calificaciones,
        'instrumentos': Instrumento.objects.all().order_by('codigo'),
        'grupos': obtener_configuracion_certificado(), 
        'rango_factores': range(8, 38),
        'proximo_id': (CalificacionTributaria.objects.aggregate(Max('id'))['id__max'] or 0) + 1
    })

# --- OTRAS VISTAS ---
def mantenedor_redirect(request): return redirect('mantenedor')

def login_view(request):
    if request.user.is_authenticated: return redirect('mantenedor')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('mantenedor')
        else: messages.error(request, "Usuario o contraseña incorrectos.")
    return render(request, 'core/login.html')

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def carga_masiva_view(request):
    if request.method == 'POST' and request.FILES.get('archivo_excel'):
        guardados, errores = procesar_carga_masiva(request.FILES['archivo_excel'], request.user)
        if guardados > 0: messages.success(request, f"✅ Se cargaron {guardados} registros.")
        if errores: 
            for error in errores[:3]: messages.error(request, error)
    return redirect('mantenedor')