import pandas as pd
from decimal import Decimal
from django.db import transaction
from .models import CalificacionTributaria, Instrumento

def procesar_carga_masiva(archivo_excel, usuario_actual):
    """
    Lee un archivo Excel/CSV y guarda las calificaciones en la BD.
    Retorna: (total_procesados, lista_de_errores)
    """
    errores = []
    guardados = 0

    try:
        # 1. LEER EL ARCHIVO CON PANDAS
        # Detectamos si es CSV o Excel por la extensión (nombre del archivo)
        if archivo_excel.name.endswith('.csv'):
            df = pd.read_csv(archivo_excel)
        else:
            # openpyxl es necesario para leer xlsx
            df = pd.read_excel(archivo_excel, engine='openpyxl')

        # 2. LIMPIEZA DE DATOS (MÁGICO)
        # Reemplazar celdas vacías (NaN) por 0, porque la BD no acepta vacíos en factores
        df = df.fillna(0)

        # 3. PROCESAR FILA POR FILA
        # Usamos transaction.atomic para que si hay un error GRAVE, no se guarde nada a medias.
        # Pero aquí lo usaremos por fila para intentar guardar lo que sirva.
        
        for index, row in df.iterrows():
            fila_numero = index + 2 # +2 porque index arranca en 0 y el Excel tiene encabezado
            
            try:
                with transaction.atomic():
                    # A. BUSCAR EL INSTRUMENTO (FK)
                    # Asumimos que en el Excel la columna se llama "NEMO" o "Instrumento"
                    codigo_instrumento = str(row.get('Instrumento', '')).strip()
                    
                    # Buscamos en la BD. Si no existe, lanzamos error.
                    try:
                        inst_obj = Instrumento.objects.get(codigo__iexact=codigo_instrumento)
                    except Instrumento.DoesNotExist:
                        raise Exception(f"El instrumento '{codigo_instrumento}' no existe en el sistema.")

                    # B. PREPARAR EL OBJETO
                    nueva_calif = CalificacionTributaria()
                    nueva_calif.usuario = usuario_actual # Aislamiento R1
                    nueva_calif.instrumento = inst_obj
                    nueva_calif.origen = 'Carga Masiva'
                    
                    # C. LEER DATOS BÁSICOS
                    nueva_calif.ejercicio = int(row.get('Ejercicio', 2025))
                    nueva_calif.fecha_pago = row.get('Fecha Pago') # Debe venir en formato fecha correcto
                    nueva_calif.monto_total = Decimal(str(row.get('Monto Total', 0)))

                    # D. LEER FACTORES (DEL 08 AL 37)
                    # Esto es repetitivo pero seguro. Leemos la columna "F08", "F09", etc.
                    suma_creditos = Decimal(0)
                    
                    # Bucle para leer F08 hasta F19 (Validación Crítica)
                    for i in range(8, 20): 
                        col_name = f"F{i:02d}" # Genera "F08", "F09"...
                        valor = Decimal(str(row.get(col_name, 0))) # Convierte a Decimal seguro
                        
                        # Asignamos dinámicamente: nueva_calif.factor_08 = valor
                        setattr(nueva_calif, f"factor_{i:02d}", valor)
                        
                        suma_creditos += valor

                    # E. VALIDACIÓN DE REGLA DE NEGOCIO (R2)
                    if suma_creditos > Decimal('1.00000000'):
                        raise Exception(f"La suma de factores F08-F19 da {suma_creditos}. Máximo permitido 1.0.")

                    # F. LEER RESTO DE FACTORES (F20 - F37)
                    for i in range(20, 38):
                        col_name = f"F{i:02d}"
                        valor = Decimal(str(row.get(col_name, 0)))
                        setattr(nueva_calif, f"factor_{i:02d}", valor)

                    # G. GUARDAR
                    nueva_calif.save()
                    guardados += 1

            except Exception as e:
                # Si falla una fila, la anotamos en errores pero seguimos con la siguiente
                errores.append(f"Fila {fila_numero}: {str(e)}")

    except Exception as e:
        # Error general al abrir el archivo (ej: formato corrupto)
        errores.append(f"Error crítico de archivo: {str(e)}")

    return guardados, errores