import pandas as pd
from decimal import Decimal
from django.db import transaction
from .models import CalificacionTributaria, Instrumento
import csv

def procesar_carga_masiva(archivo, usuario_actual):
    """
    Lee un archivo Excel/CSV y guarda las calificaciones en la BD.
    Retorna: (total_procesados, lista_de_errores)
    """
    errores = []
    guardados = 0

    try:
        # 1. LEER EL ARCHIVO (SOPORTE PARA EXCEL Y CSV CHILENO)
        if archivo.name.endswith('.csv'):
            # Truco para detectar si es coma (,) o punto y coma (;)
            # Leemos los primeros 1024 bytes para olfatear el formato
            sample = archivo.read(1024).decode('iso-8859-1') 
            archivo.seek(0) # Rebobinar el archivo al principio
            
            # Detectar separador
            dialect = csv.Sniffer().sniff(sample)
            
            # Leemos con Pandas usando el separador detectado
            df = pd.read_csv(archivo, sep=dialect.delimiter, encoding='iso-8859-1')
        else:
            # Es Excel (.xlsx)
            df = pd.read_excel(archivo, engine='openpyxl')

        # 2. LIMPIEZA DE DATOS
        df = df.fillna(0) # Rellenar vacíos con 0
        
        # Normalizar nombres de columnas (Quitar espacios extra y pasar a mayúsculas para buscar mejor)
        # Esto ayuda si el CSV dice " Instrumento " en lugar de "Instrumento"
        df.columns = df.columns.str.strip()

        # 3. PROCESAR FILA POR FILA
        for index, row in df.iterrows():
            fila_numero = index + 2 
            
            try:
                with transaction.atomic():
                    # A. BUSCAR INSTRUMENTO
                    # Intentamos leer 'Instrumento' o 'Nemo'
                    codigo_instrumento = str(row.get('Instrumento') or row.get('Nemo', '')).strip()
                    
                    if not codigo_instrumento:
                        continue # Saltar filas vacías

                    try:
                        inst_obj = Instrumento.objects.get(codigo__iexact=codigo_instrumento)
                    except Instrumento.DoesNotExist:
                        raise Exception(f"El instrumento '{codigo_instrumento}' no existe en el sistema.")

                    # B. PREPARAR OBJETO
                    nueva = CalificacionTributaria()
                    nueva.usuario = usuario_actual
                    nueva.instrumento = inst_obj
                    nueva.origen = 'Carga Masiva' # HDU 6
                    
                    # C. DATOS BASICOS
                    nueva.ejercicio = int(row.get('Ejercicio', 2025))
                    # Intentar leer fecha, si falla dejar None o fecha actual
                    nueva.fecha_pago = row.get('Fecha Pago') 
                    nueva.monto_total = Decimal(str(row.get('Monto Total', 0)).replace(',', '.')) # Reemplazar coma decimal por punto

                    # D. LEER FACTORES (F08 - F37)
                    # El CSV puede tener "0,123" (español) o "0.123" (inglés). Arreglamos eso.
                    
                    suma_creditos = Decimal(0)

                    for i in range(8, 38):
                        col_name = f"F{i:02d}" # Busca "F08", "F09"...
                        
                        # Obtener valor, convertir a string, cambiar coma por punto (para Python)
                        val_str = str(row.get(col_name, 0)).replace(',', '.')
                        try:
                            valor = Decimal(val_str)
                        except:
                            valor = Decimal(0)

                        setattr(nueva, f"factor_{i:02d}", valor)
                        
                        # Validar suma F08-F16 (HDU 6)
                        if 8 <= i <= 16:
                            suma_creditos += valor

                    # E. VALIDACIÓN DE REGLA DE NEGOCIO
                    if suma_creditos > Decimal('1.00000001'):
                        raise Exception(f"Suma de factores F08-F16 es {suma_creditos} (mayor a 1.0)")

                    nueva.save()
                    guardados += 1

            except Exception as e:
                errores.append(f"Fila {fila_numero} ({codigo_instrumento}): {str(e)}")

    except Exception as e:
        errores.append(f"Error crítico al leer archivo: {str(e)}")

    return guardados, errores