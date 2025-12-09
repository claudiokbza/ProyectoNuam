from django.db import models
from django.contrib.auth.models import User

class Mercado(models.Model):
    codigo = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=100)
    def __str__(self): return self.nombre

class Instrumento(models.Model):
    mercado = models.ForeignKey(Mercado, on_delete=models.CASCADE)
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150)
    def __str__(self): return self.codigo

class CalificacionTributaria(models.Model):
    # NOMBRE DEL CAMPO CORREGIDO A 'usuario' PARA QUE COINCIDA CON VIEWS.PY
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    
    instrumento = models.ForeignKey(Instrumento, on_delete=models.CASCADE)
    ejercicio = models.IntegerField(default=2025)
    fecha_pago = models.DateField(null=True, blank=True)
    secuencia = models.IntegerField(default=0)  
    es_isfut = models.BooleanField(default=False)
    factor_actualizacion = models.DecimalField(max_digits=10, decimal_places=6, default=1.0)
    descripcion = models.CharField(max_length=255, blank=True, null=True)
    es_isfut = models.BooleanField(default=False, verbose_name="Acogido a ISFUT/ISIFT")
    factor_actualizacion = models.DecimalField(max_digits=10, decimal_places=6, default=1.0)
    monto_total = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    OPCIONES_ORIGEN = [
        ('Corredor', 'Corredor'),
        ('Entidad Prestadora del Servicio', 'Entidad Prestadora del Servicio'),
    ]
    
    origen = models.CharField(
        max_length=50, 
        choices=OPCIONES_ORIGEN, 
        default="Corredor" # Por defecto, si ingresa manual, es el Corredor
    )
    
    # FACTORES COMO COLUMNAS (ESTO ES LO QUE TE FALTA EN TU BD ACTUAL)
    factor_08 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_09 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_10 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_11 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_12 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_13 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_14 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_15 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_16 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_17 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_18 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_19 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_20 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_20 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_21 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_22 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_23 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_24 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_25 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_26 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_27 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_28 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_29 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_30 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_31 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_32 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_33 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_34 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_35 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_36 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_37 = models.DecimalField(max_digits=18, decimal_places=8, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)