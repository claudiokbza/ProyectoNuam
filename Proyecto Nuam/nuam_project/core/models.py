from django.db import models
from django.contrib.auth.models import User

# --- Modelos de Tablas Maestras (Para Filtros del Mantenedor) ---

class Mercado(models.Model):
    codigo = models.CharField(max_length=10, unique=True) # Ej: AC, CFI
    nombre = models.CharField(max_length=100)
    def __str__(self): return self.nombre

class Instrumento(models.Model):
    mercado = models.ForeignKey(Mercado, on_delete=models.CASCADE)
    codigo = models.CharField(max_length=50, unique=True) # NEMO
    nombre = models.CharField(max_length=150)
    def __str__(self): return self.codigo

# --- Modelo Principal: Calificaciones Tributarias ---

class CalificacionTributaria(models.Model):
    # 1. Seguridad y Contexto (Informe R1)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, 
                                verbose_name="Corredor Asociado", 
                                help_text="Aislamiento de datos: Sólo el dueño puede ver/editar.")
    
    # 2. Datos Maestros (Identificador Único)
    instrumento = models.ForeignKey(Instrumento, on_delete=models.CASCADE)
    ejercicio = models.IntegerField(default=2025)
    fecha_pago = models.DateField()
    secuencia = models.IntegerField(default=0, help_text="Secuencia del evento de capital.")
    origen = models.CharField(max_length=20, default="Manual", 
                              choices=[('Manual', 'Ingreso Manual'), 
                                       ('Carga', 'Carga Masiva'),
                                       ('Sistema', 'Sistema Central')])

    # 3. Datos Descriptivos y Financieros
    descripcion = models.CharField(max_length=255, blank=True, null=True)
    monto_total = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    valor_historico = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    factor_actualizacion = models.DecimalField(max_digits=10, decimal_places=6, default=1.0)
    
    # 4. FACTORES (Decimal Field con 8 decimales de precisión)
    
    # PESTAÑA 2: Factores de Crédito (08 al 19)
    # Requisito R2: La suma de estos debe ser <= 1.0 (Validación en la vista)
    factor_08 = models.DecimalField(max_digits=18, decimal_places=8, default=0, verbose_name="F08: Con Crédito IDPC")
    factor_09 = models.DecimalField(max_digits=18, decimal_places=8, default=0, verbose_name="F09: Créditos Acum. 2016")
    factor_10 = models.DecimalField(max_digits=18, decimal_places=8, default=0, verbose_name="F10: IDPC Voluntario")
    factor_11 = models.DecimalField(max_digits=18, decimal_places=8, default=0, verbose_name="F11: Sin derecho a crédito")
    factor_12 = models.DecimalField(max_digits=18, decimal_places=8, default=0, verbose_name="F12: Rentas RAP")
    factor_13 = models.DecimalField(max_digits=18, decimal_places=8, default=0, verbose_name="F13: Otras rentas percibidas")
    factor_14 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_15 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_16 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_17 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_18 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_19 = models.DecimalField(max_digits=18, decimal_places=8, default=0)

    # PESTAÑA 3: Factores de Rentas (20 al 29)
    factor_20 = models.DecimalField(max_digits=18, decimal_places=8, default=0, verbose_name="F20: ISFUT Ley N°20.780")
    factor_21 = models.DecimalField(max_digits=18, decimal_places=8, default=0, verbose_name="F21: Rentas hasta 31.12.1983")
    factor_22 = models.DecimalField(max_digits=18, decimal_places=8, default=0, verbose_name="F22: Rentas Exentas IGC/IA")
    factor_23 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_24 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_25 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_26 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_27 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_28 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_29 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    
    # PESTAÑA 4: Otros Factores (30 al 37)
    factor_30 = models.DecimalField(max_digits=18, decimal_places=8, default=0, verbose_name="F30: Rentas Afectas c/Derecho")
    factor_31 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_32 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_33 = models.DecimalField(max_digits=18, decimal_places=8, default=0, verbose_name="F33: Crédito por IPE")
    factor_34 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_35 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_36 = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    factor_37 = models.DecimalField(max_digits=18, decimal_places=8, default=0, verbose_name="F37: Otros Créditos")

    # 5. Metadatos de Auditoría (Informe)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Calificación Tributaria"
        verbose_name_plural = "Calificaciones Tributarias"
        unique_together = ('instrumento', 'ejercicio', 'secuencia', 'usuario')

    def __str__(self):
        return f"{self.instrumento.codigo} - {self.ejercicio} ({self.usuario.username})"