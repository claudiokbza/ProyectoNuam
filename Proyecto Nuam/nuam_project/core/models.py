from django.db import models
from django.conf import settings

class Rol(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    def __str__(self): return self.nombre

class Cliente(models.Model):
    rut = models.CharField(max_length=32, unique=True, null=True, blank=True)
    razon_social = models.CharField(max_length=250)
    tipo_cliente = models.CharField(max_length=50, blank=True, null=True)
    segmento = models.CharField(max_length=80, blank=True, null=True)
    estado = models.CharField(max_length=20, default='Activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.razon_social

class Mercado(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    descripcion = models.CharField(max_length=150, blank=True, null=True)
    def __str__(self): return self.codigo

class Instrumento(models.Model):
    codigo = models.CharField(max_length=80, unique=True)
    descripcion = models.CharField(max_length=250, blank=True, null=True)
    tipo_instrumento = models.CharField(max_length=80, blank=True, null=True)
    mercado = models.ForeignKey(Mercado, on_delete=models.PROTECT, null=True, blank=True)
    def __str__(self): return self.codigo

class Evento(models.Model):
    nombre_evento = models.CharField(max_length=150, blank=True, null=True)
    secuencia = models.BigIntegerField(null=True, blank=True)
    fecha_pago = models.DateField(null=True, blank=True)
    anio = models.IntegerField(null=True, blank=True)
    def __str__(self): return f"{self.nombre_evento} ({self.anio})"

class Usuario(models.Model):
    # Si usas django.contrib.auth.User, puedes enlazar a ese en lugar de crear uno nuevo.
    nombre = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT)
    estado = models.CharField(max_length=20, default='Activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.nombre

class CalificacionTributaria(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    instrumento = models.ForeignKey(Instrumento, on_delete=models.SET_NULL, null=True, blank=True)
    mercado = models.ForeignKey(Mercado, on_delete=models.SET_NULL, null=True, blank=True)
    evento = models.ForeignKey(Evento, on_delete=models.SET_NULL, null=True, blank=True)
    secuencia_evento = models.BigIntegerField(null=True, blank=True)
    fecha_pago = models.DateField(null=True, blank=True)
    anio = models.IntegerField(null=True, blank=True)
    descripcion = models.TextField(blank=True, null=True)
    valor_historico = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    ingreso_por_montos = models.BooleanField(default=False)
    factor_actualizacion = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    es_isfut = models.BooleanField(default=False)
    usuario_crea = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='calificaciones_creadas')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    usuario_modifica = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='calificaciones_modificadas')
    fecha_modificacion = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=30, default='Vigente')
    def __str__(self): return f"Calif {self.id} - {self.cliente}"

class Factor(models.Model):
    codigo_factor = models.CharField(max_length=32, unique=True)
    descripcion_factor = models.TextField(blank=True, null=True)
    tipo_valor = models.CharField(max_length=20, default='NUMERIC')
    order_index = models.IntegerField(default=0)
    def __str__(self): return self.codigo_factor

class CalificacionFactor(models.Model):
    calificacion = models.ForeignKey(CalificacionTributaria, on_delete=models.CASCADE, related_name='factores')
    factor = models.ForeignKey(Factor, on_delete=models.PROTECT)
    valor = models.DecimalField(max_digits=30, decimal_places=8, null=True, blank=True)
    unidad = models.CharField(max_length=30, blank=True, null=True)
    comentario = models.TextField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('calificacion', 'factor')

    def __str__(self): return f"{self.calificacion.id} - {self.factor.codigo_factor}"
