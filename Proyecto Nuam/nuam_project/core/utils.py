import pandas as pd
from decimal import Decimal
from django.db import transaction
from .models import CalificacionTributaria, Instrumento
import csv
import io
from datetime import datetime

def procesar_carga_masiva(archivo, usuario_actual):
    errores = []
    guardados = 0

    try:
        # 1. LECTURA ROBUSTA DEL ARCHIVO (Detecta UTF-8 BOM, UTF-8 y Latin-1)
        if archivo.name.endswith('.csv'):
            contenido_bytes = archivo.read()
            
            # Intento 1: UTF-8 con BOM (Excel moderno)
            try:
                texto = contenido_bytes.decode('utf-8-sig')
            except UnicodeDecodeError:
                try:
                    # Intento 2: UTF-8 normal
                    texto = contenido_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    # Intento 3: Latin-1 (Excel antiguo / Windows)
                    texto = contenido_bytes.decode('iso-8859-1')

            # Detectar separador (; o ,)
            dialect = csv.Sniffer().sniff(texto[:2048]) # Leemos un poco más por si acaso
            
            # Crear DataFrame
            df = pd.read_csv(io.StringIO(texto), sep=dialect.delimiter)
            
        else:
            # Es Excel (.xlsx)
            df = pd.read_excel(archivo, engine='openpyxl')

        # 2. LIMPIEZA DE COLUMNAS
        # Normalizar nombres: mayúsculas, quitar espacios y BOM invisible
        df.columns = df.columns.astype(str).str.strip().str.upper().str.replace('Ï»¿', '')
        
        # Buscar columna Instrumento
        col_instrumento = next((c for c in df.columns if 'INSTRUMENTO' in c or 'NEMO' in c), None)
        
        if not col_instrumento:
            raise Exception(f"No se encontró la columna 'Instrumento'. Cabeceras detectadas: {list(df.columns)}")

        # 3. PROCESAR FILA POR FILA
        for index, row in df.iterrows():
            fila_numero = index + 2 
            
            try:
                # --- A. VALIDAR INSTRUMENTO (Saltar vacíos) ---
                raw_codigo = row.get(col_instrumento)
                # Si es nan, None, vacío o 'nan' (texto), saltamos la fila
                if pd.isna(raw_codigo) or str(raw_codigo).strip() == '' or str(raw_codigo).lower() == 'nan':
                    continue
                
                codigo_instrumento = str(raw_codigo).strip()

                with transaction.atomic():
                    try:
                        inst_obj = Instrumento.objects.get(codigo__iexact=codigo_instrumento)
                    except Instrumento.DoesNotExist:
                        raise Exception(f"El instrumento '{codigo_instrumento}' no existe en el sistema (Admin).")

                    # --- B. CREAR OBJETO ---
                    nueva = CalificacionTributaria()
                    nueva.usuario = usuario_actual
                    nueva.instrumento = inst_obj
                    nueva.origen = 'Carga Masiva'
                    
                    # --- C. ARREGLO DE FECHAS (Nuevo!) ---
                    # El CSV trae: "09-12-2025" (DD-MM-YYYY)
                    # Django quiere: "2025-12-09" (YYYY-MM-DD)
                    
                    # Buscamos la columna que contenga "FECHA"
                    col_fecha = next((c for c in df.columns if 'FECHA' in c), None)
                    raw_fecha = row.get(col_fecha) if col_fecha else None

                    if raw_fecha:
                        fecha_str = str(raw_fecha).strip()
                        try:
                            # Intentamos parsear formato Chileno (Día-Mes-Año)
                            fecha_obj = datetime.strptime(fecha_str, '%d-%m-%Y')
                            nueva.fecha_pago = fecha_obj.strftime('%Y-%m-%d')
                        except ValueError:
                            # Si falla, intentamos formato ISO por si acaso (Año-Mes-Día)
                            try:
                                fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d')
                                nueva.fecha_pago = fecha_obj.strftime('%Y-%m-%d')
                            except:
                                # Si falla todo, lanzamos error o dejamos None
                                raise Exception(f"Formato de fecha inválido: '{fecha_str}'. Use DD-MM-YYYY.")
                    
                    # --- D. MONTO Y EJERCICIO ---
                    col_ejercicio = next((c for c in df.columns if 'EJERCICIO' in c), None)
                    nueva.ejercicio = int(row.get(col_ejercicio, 2025))

                    col_monto = next((c for c in df.columns if 'MONTO' in c), None)
                    monto_str = str(row.get(col_monto, 0)).replace('.', '').replace(',', '.')
                    try:
                        nueva.monto_total = Decimal(monto_str)
                    except:
                        nueva.monto_total = Decimal(0)

                    # --- E. FACTORES ---
                    suma_creditos = Decimal(0)
                    for i in range(8, 38):
                        col_key = f"F{i:02d}" # Buscamos F08, F09...
                        # Buscamos la columna real en el DF
                        col_real = next((c for c in df.columns if col_key == c), None)
                        
                        val_str = str(row.get(col_real, 0)).replace(',', '.')
                        try:
                            valor = Decimal(val_str)
                        except:
                            valor = Decimal(0)

                        setattr(nueva, f"factor_{i:02d}", valor)
                        
                        if 8 <= i <= 16:
                            suma_creditos += valor

                    # Validar Suma > 1.0
                    if suma_creditos > Decimal('1.00000001'):
                        raise Exception(f"Suma de factores F08-F16 es {suma_creditos} (mayor a 1.0)")

                    nueva.save()
                    guardados += 1

            except Exception as e:
                errores.append(f"Fila {fila_numero} ({codigo_instrumento if 'codigo_instrumento' in locals() else 'Desc.'}): {str(e)}")

    except Exception as e:
        errores.append(f"Error crítico al leer archivo: {str(e)}")

    return guardados, errores