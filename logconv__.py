import sys
import json
import re
import argparse
import os
import requests 

# Archivo de almacenamiento persistente de la licencia (Máquina Cazadora CRC)
LICENSE_FILE = '.crc_license.json'

# =================================================================
# GESTIÓN DE LICENCIAS VÁLIDAS - (SOLO PARA PRUEBA INTERNA)
# =================================================================
VALID_LICENSES = [
    "LIC-PROD-9876",
    "LIC-PROD-0001",
    "ABC-123-XYZ" # Clave de prueba para validaciones
]

# =================================================================
# UTILIDADES DE LICENCIAMIENTO
# =================================================================

def guardar_licencia(key):
    """Guarda la clave de licencia válida en un archivo local."""
    try:
        with open(LICENSE_FILE, 'w', encoding='utf-8') as f:
            json.dump({"active_key": key}, f)
        sys.stdout.write(f"\n✅ LICENCIA ACTIVADA: Clave '{key}' guardada con éxito.\n")
        sys.stdout.write("   Ahora puede usar los comandos 'logconv convertir' o 'logconv enviar'.\n\n")
    except Exception as e:
        sys.stderr.write(f"ERROR FATAL: No se pudo escribir el archivo de licencia: {e}\n")

def cargar_licencia():
    """Carga y retorna la clave de licencia activa."""
    if not os.path.exists(LICENSE_FILE):
        return None
    try:
        with open(LICENSE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("active_key")
    except Exception:
        return None

def verificar_licencia_y_fallar():
    """Verifica la licencia antes de la conversión o el envío. Ejecuta la Máquina Cazadora CRC."""
    active_key = cargar_licencia()
    if not active_key or active_key not in VALID_LICENSES:
        sys.stderr.write("\n🚨 MÁQUINA CAZADORA CRC ACTIVADA: LICENCIA REQUERIDA.\n")
        sys.stderr.write("   Ejecute: 'logconv activar [SU_CLAVE_AQUÍ]' para continuar.\n")
        sys.stderr.write("   Obtenga su clave en: https://echek7.github.io/logpattern_converter/\n\n")
        sys.exit(2)

# =================================================================
# LÓGICA DE CONVERSIÓN DE LOGS
# =================================================================

def convertir_log_a_json(linea_log):
    # Esta función transforma una línea de log sucia en un diccionario (objeto JSON)
    match_complex = re.search(r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s+(\w+)\s+-\s+(.+)', linea_log)
    
    if match_complex:
        try:
            timestamp_raw = match_complex.group(1)
            severity = match_complex.group(2)
            message_raw = match_complex.group(3)

            duration_match = re.search(r'duration=(\d+\.?\d*)s', linea_log)
            user_id_match = re.search(r'(?:ID:\s*|user_id=)(\d+)', linea_log) 
            code_match = re.search(r'code=(\d+)', linea_log)

            output_data = {
                "timestamp": timestamp_raw.replace(' ', 'T') + 'Z',
                "severity": severity,
                "message": message_raw.split('(')[0].strip(),
                "attributes": {
                    "duration_s": float(duration_match.group(1)) if duration_match else None,
                    "user_id": int(user_id_match.group(1)) if user_id_match else None, 
                    "response_code": int(code_match.group(1)) if code_match else None,
                    "conversion_status": "FULL_CONVERSION_SUCCESSFUL"
                }
            }
            return output_data # Devolvemos DICCIONARIO
        except Exception:
            return {"status": "ERROR_PARSING", "raw_log": linea_log.strip()}
    return {"status": "NOT_PARSED", "raw_log": linea_log.strip()} # Devolvemos DICCIONARIO

# =================================================================
# MANEJADORES DE SUB-COMANDOS
# =================================================================

def handle_activar(args):
    """Lógica para el comando 'logconv activar [CLAVE]'"""
    key = args.license_key
    if key in VALID_LICENSES:
        guardar_licencia(key)
    else:
        sys.stderr.write("\n❌ ERROR DE LICENCIA: La clave proporcionada no es válida.\n")
        sys.stderr.write("   Por favor, visite nuestro Vendedor M2M para obtener una licencia.\n\n")
        sys.exit(2)

def handle_convertir(args):
    """Lógica para el comando 'logconv convertir [ARCHIVO]'"""
    
    verificar_licencia_y_fallar() # Verifica si hay licencia

    file_path = args.file_path
    line_count = 0 

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line_count += 1
                line = line.strip()
                if line:
                    # Convertimos a diccionario, luego a JSON para imprimir
                    data_dict = convertir_log_a_json(line)
                    print(json.dumps(data_dict)) 
            
    except FileNotFoundError:
        sys.stderr.write(f"ERROR FATAL: Archivo no encontrado: {file_path}. Verifique la ruta.\n")
        sys.exit(3)
    except Exception as e:
        sys.stderr.write(f"FATAL_ERROR: Error de procesamiento interno en línea {line_count}: {e}\n")
        sys.exit(4)

def handle_enviar(args):
    """Lógica para el comando 'logconv enviar [ARCHIVO] [URL]' (Feature Premium)"""
    
    verificar_licencia_y_fallar() # Verifica si hay licencia

    file_path = args.file_path
    webhook_url = args.webhook_url
    
    line_count = 0 
    
    sys.stdout.write(f"⚙️ Iniciando procesamiento y envío de logs a: {webhook_url}\n")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line_count += 1
                line = line.strip()
                if line:
                    data_dict = convertir_log_a_json(line)
                    
                    # Enviar el log procesado inmediatamente (Zapier/Webhook)
                    try:
                        response = requests.post(webhook_url, json=data_dict, timeout=10)
                        response.raise_for_status() # Lanza excepción para códigos 4xx/5xx
                        sys.stdout.write(f".") # Indicador de progreso exitoso
                        sys.stdout.flush() 
                        
                    except requests.exceptions.Timeout:
                        sys.stderr.write(f"\n[ERROR - Línea {line_count}] Tiempo de espera agotado (Timeout) al intentar enviar a Webhook. Saltando esta línea.\n")
                    except requests.exceptions.RequestException as req_e:
                        sys.stderr.write(f"\n[ERROR - Línea {line_count}] Error de red o Webhook (Código HTTP incorrecto): {req_e}. Saltando esta línea.\n")
                    except Exception as general_e:
                        sys.stderr.write(f"\n[ERROR - Línea {line_count}] Error inesperado durante el envío: {general_e}. Saltando esta línea.\n")
                        
        sys.stdout.write("\n\n✅ PROCESO COMPLETADO: Se intentó enviar la conversión de logs.\n")
        sys.stdout.write("   Verifique el estado de los logs en su plataforma de destino.\n\n")
        
    except FileNotFoundError:
        sys.stderr.write(f"\nERROR FATAL: Archivo no encontrado: {file_path}. Verifique la ruta.\n")
        sys.exit(3)
    except Exception as e:
        sys.stderr.write(f"\nFATAL_ERROR: Error de procesamiento interno en línea {line_count}: {e}\n")
        sys.exit(4)


# =================================================================
# LÓGICA PRINCIPAL (CONTROL DE COMANDOS)
# =================================================================
def main():
    """Función principal para el punto de entrada de la CLI."""
    parser = argparse.ArgumentParser(
        description="LogPattern Converter: Herramienta profesional de refactorización de logs.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    # Configuración de sub-comandos
    subparsers = parser.add_subparsers(dest='command', required=True, help='Comandos disponibles')

    # --- COMANDO ACTIVAR ---
    parser_activar = subparsers.add_parser('activar', help='Activa la licencia para uso de por vida.')
    parser_activar.add_argument('license_key', type=str, help='Clave de licencia de 12 dígitos.')
    parser_activar.set_defaults(func=handle_activar)

    # --- COMANDO CONVERTIR ---
    parser_convertir = subparsers.add_parser('convertir', help='Convierte logs sucios a formato JSON estructurado (salida local).')
    parser_convertir.add_argument('file_path', type=str, help='Ruta del archivo de logs de entrada (ej: logs_sucios.txt)')
    parser_convertir.set_defaults(func=handle_convertir)

    # --- COMANDO ENVIAR (NUEVO) ---
    parser_enviar = subparsers.add_parser('enviar', help='Convierte y envía logs en tiempo real a una Webhook URL (Zapier, etc.).')
    parser_enviar.add_argument('file_path', type=str, help='Ruta del archivo de logs de entrada.')
    parser_enviar.add_argument('webhook_url', type=str, help='URL del Webhook de destino (ej: Zapier).')
    parser_enviar.set_defaults(func=handle_enviar)

    # Procesar y llamar a la función adecuada
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()