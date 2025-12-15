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
        # 1. LECTURA DEL ARCHIVO
        if archivo.name.endswith('.csv'):
            contenido_bytes = archivo.read()
            # Intentar decodificar (UTF-8 o Latin-1)
            try: texto = contenido_bytes.decode('utf-8-sig')
            except: texto = contenido_bytes.decode('iso-8859-1')
            
            dialect = csv.Sniffer().sniff(texto[:2048])
            df = pd.read_csv(io.StringIO(texto), sep=dialect.delimiter)
        else:
            df = pd.read_excel(archivo)

        # 2. NORMALIZAR COLUMNAS (Mayúsculas y sin espacios)
        df.columns = df.columns.astype(str).str.strip().str.upper()

        # 3. BUSCAR COLUMNAS CLAVE
        def buscar_col(keywords):
            for k in keywords:
                for col in df.columns:
                    if k in col: return col
            return None

        col_inst = buscar_col(['INSTRUMENTO', 'NEMO', 'CODIGO'])
        if not col_inst: raise Exception("No se encontró columna de Instrumento")

        # Columnas nuevas (Opcionales, tienen defaults)
        col_rut = buscar_col(['RUT', 'PROPIETARIO'])
        col_hist = buscar_col(['HISTORICO', 'MONTO HIST'])
        col_factor = buscar_col(['FACTOR', 'ACTUALIZACION'])
        col_fecha = buscar_col(['FECHA', 'PAGO'])
        col_total = buscar_col(['MONTO TOTAL', 'MONTO ACTUALIZADO', 'MONTO']) # Fallback

        # 4. ITERAR
        for index, row in df.iterrows():
            try:
                codigo = str(row.get(col_inst)).strip()
                if not codigo or codigo.lower() == 'nan': continue

                with transaction.atomic():
                    # Buscar Instrumento
                    try:
                        inst = Instrumento.objects.get(codigo__iexact=codigo)
                    except Instrumento.DoesNotExist:
                        # Si no existe, podrías crearlo o saltarlo. Aquí lanzamos error.
                        raise Exception(f"Instrumento '{codigo}' no existe.")

                    obj = CalificacionTributaria()
                    obj.usuario = usuario_actual
                    obj.instrumento = inst
                    obj.origen = 'Carga Masiva'

                    # --- RUT ---
                    if col_rut:
                        obj.rut_propietario = str(row.get(col_rut, '0-0')).strip()

                    # --- FECHA ---
                    if col_fecha:
                        val_fecha = str(row.get(col_fecha)).strip()
                        try:
                            # Intentar DD-MM-YYYY
                            obj.fecha_pago = datetime.strptime(val_fecha, '%d-%m-%Y').strftime('%Y-%m-%d')
                        except:
                            try: obj.fecha_pago = datetime.strptime(val_fecha, '%Y-%m-%d').strftime('%Y-%m-%d')
                            except: pass # Dejar null si falla
                    
                    # --- MONTOS (Lógica Nueva) ---
                    # 1. Intentar leer Histórico y Factor
                    monto_h = Decimal(0)
                    factor = Decimal(1)

                    if col_hist:
                        try: monto_h = Decimal(str(row.get(col_hist, 0)).replace(',','.'))
                        except: pass
                    
                    if col_factor:
                        try: factor = Decimal(str(row.get(col_factor, 1)).replace(',','.'))
                        except: pass

                    # 2. Si no hay Histórico, buscar si viene el Total directo
                    monto_t = Decimal(0)
                    if col_total:
                        try: monto_t = Decimal(str(row.get(col_total, 0)).replace(',','.'))
                        except: pass

                    # 3. Asignación Inteligente
                    if monto_h > 0:
                        obj.monto_historico = monto_h
                        obj.factor_actualizacion = factor
                        obj.monto_total = monto_h * factor # Calculamos el actualizado
                    elif monto_t > 0:
                        # Si solo viene el total, asumimos histórico = total y factor = 1
                        obj.monto_historico = monto_t
                        obj.factor_actualizacion = 1
                        obj.monto_total = monto_t
                    
                    # --- FACTORES F08 - F37 ---
                    suma_bases = Decimal(0)
                    for i in range(8, 38):
                        col_f = buscar_col([f"F{i:02d}", f"FACTOR {i:02d}"])
                        val_f = Decimal(0)
                        if col_f:
                            try: val_f = Decimal(str(row.get(col_f, 0)).replace(',','.'))
                            except: pass
                        
                        setattr(obj, f"factor_{i:02d}", val_f)
                        if 8 <= i <= 19: suma_bases += val_f

                    obj.save()
                    guardados += 1

            except Exception as e:
                errores.append(f"Fila {index+2} ({codigo}): {str(e)}")

    except Exception as e:
        errores.append(f"Error archivo: {str(e)}")

    return guardados, errores
# utils.py

def obtener_configuracion_certificado():
    """
    Retorna la estructura COMPLETA del Certificado N° 70 (Anexo 3, Res. 98).
    Incluye F22 (Tasa Adicional) y F34, F35, F36 (Retiros en Exceso).
    """
    return {
        # ----------------------------------------------------------------------
        # 1. RENTAS AFECTAS (Base Imponible)
        # ----------------------------------------------------------------------
        "SECCION_A_RENTAS_AFECTAS": {
            "titulo": "1. RENTAS AFECTAS A IMPUESTOS",
            "color": "primary",
            "factores": [
                {"id": "f08", "label": "F08 - Con Crédito c/Restitución (14 A)", "ayuda": "Monto base para grandes empresas (27%)."},
                {"id": "f09", "label": "F09 - Con Crédito s/Restitución (Pyme)", "ayuda": "Monto base Pyme o Histórico."},
                {"id": "f10", "label": "F10 - Con Crédito Voluntario", "ayuda": "Crédito pagado voluntariamente."},
                {"id": "f11", "label": "F11 - Sin Derecho a Crédito", "ayuda": "Renta afecta pura."},
            ]
        },

        # ----------------------------------------------------------------------
        # 2. RENTAS EXENTAS / INR
        # ----------------------------------------------------------------------
        "SECCION_A_RENTAS_EXENTAS": {
            "titulo": "2. RENTAS EXENTAS / TRIBUTACIÓN CUMPLIDA",
            "color": "success",
            "factores": [
                {"id": "f12", "label": "F12 - RAP (Rentas Atribuidas)", "ayuda": "Deuda pagada (2017-2019)."},
                {"id": "f13", "label": "F13 - Rentas Presuntas / Otras", "ayuda": "Otras rentas cumplidas."},
                {"id": "f14", "label": "F14 - Rentas Desproporcionadas", "ayuda": "Distribución desigual (Art 14A N°9)."},
                {"id": "f15", "label": "F15 - ISFUT (Ley 20.780)", "ayuda": "FUT Histórico sustitutivo."},
                {"id": "f16", "label": "F16 - ISFUT (Ley 21.210)", "ayuda": "ISFUT Nuevo (Caso 3)."},
                {"id": "f17", "label": "F17 - Rentas Exentas IGC", "ayuda": "Exentas por ley."},
                {"id": "f18", "label": "F18 - Zonas Extremas", "ayuda": "Leyes regionales."},
                {"id": "f19", "label": "F19 - Ingresos No Renta", "ayuda": "Devolución de Capital."},
            ]
        },

        # ----------------------------------------------------------------------
        # 3. CRÉDITOS (SAC y OTROS)
        # ----------------------------------------------------------------------
        "SECCION_4_CREDITOS": {
            "titulo": "3. CRÉDITOS (Cupón de Descuento)",
            "color": "warning",
            "factores": [
                {"id": "f20", "label": "F20 - No Suj. Restitución (< 2019)", "ayuda": "Saldo antiguo SAC."},
                {"id": "f21", "label": "F21 - No Suj. Restitución (> 2020)", "ayuda": "Crédito Pyme (100%)."},
                {"id": "f22", "label": "F22 - Crédito Tasa Adicional (Ex Art.21)", "ayuda": "Impuesto castigo pagado por la empresa."}, # <-- AQUÍ ESTÁ EL F22
                {"id": "f25", "label": "F25 - Sujetos a Restitución (14 A)", "ayuda": "Crédito 27% (Devuelve 35%)."},
                {"id": "f27", "label": "F27 - Restitución (Exentas)", "ayuda": "Asociado a rentas exentas."},
                {"id": "f30", "label": "F30 - Crédito IPE", "ayuda": "Impuesto Extranjero."},
                {"id": "f31", "label": "F31 - Crédito Art. 33 Bis", "ayuda": "Activo Fijo."},
            ]
        },

        # ----------------------------------------------------------------------
        # 4. CRÉDITOS HISTÓRICOS (STUT)
        # ----------------------------------------------------------------------
        "SECCION_4_STUT": {
            "titulo": "4. CRÉDITOS HISTÓRICOS (Hasta 2016)",
            "color": "secondary",
            "factores": [
                {"id": "f26", "label": "F26 - Sin Devolución (Afectos)", "ayuda": "Solo para pago."},
                {"id": "f28", "label": "F28 - Sin Devolución (Exentos)", "ayuda": "Asociado a exentas."},
                {"id": "f29", "label": "F29 - Con Devolución (Afectos)", "ayuda": "Se devuelve en efectivo."},
                {"id": "f32", "label": "F32 - Con Devolución (Exentos)", "ayuda": "Asociado a exentas."},
            ]
        },

        # ----------------------------------------------------------------------
        # 5. SALDOS Y CONTROL (Aquí van los F34, F35, F36)
        # ----------------------------------------------------------------------
        "SECCION_SALDOS": {
            "titulo": "5. INFORMACIÓN DE SALDOS Y EXCESOS",
            "color": "info",
            "factores": [
                {"id": "f23", "label": "F23 - Saldo FUT / STUT", "ayuda": "Utilidad antigua pendiente."},
                {"id": "f24", "label": "F24 - Saldo SAC Total", "ayuda": "Total créditos disponibles."},
                {"id": "f33", "label": "F33 - Exceso Retiros (Del Ejercicio)", "ayuda": "Retiro mayor a la utilidad de este año."},
                {"id": "f34", "label": "F34 - Saldo Excesos (Ejercicio Anterior)", "ayuda": "Deuda de excesos que viene del año pasado."}, # <-- F34
                {"id": "f35", "label": "F35 - Imputación de Excesos", "ayuda": "Excesos cubiertos con utilidad de este año."}, # <-- F35
                {"id": "f36", "label": "F36 - Saldo Excesos (Pendiente Final)", "ayuda": "Exceso que queda debiendo para el próximo año."}, # <-- F36
                {"id": "f37", "label": "F37 - Devolución Capital (Art 17 N7)", "ayuda": "Monto informativo de capital."},
            ]
        }
    }