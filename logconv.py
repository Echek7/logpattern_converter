import sys
import json
import re
import argparse
import os
import requests 
from uuid import getnode as get_mac

# =================================================================
# CONFIGURACIÓN DE PRODUCCIÓN: BASE DE DATOS DE LICENCIAS
# =================================================================

# URL de la API de Verificación de Licencias (Cloud Function licenseVerifier)
# ESTA ES LA URL DE PRODUCCIÓN VERIFICADA
LICENSE_API_URL = os.environ.get(
    'LOGCONV_LICENSE_API_URL', 
    'https://licenseverifier-fc7us6k7sa-uc.a.run.app' # URL DE PRODUCCIÓN RESTAURADA
)

# Archivo de almacenamiento persistente de la licencia (Máquina Cazadora CRC)
LICENSE_FILE = '.crc_license.json'
# Clave de prueba para inicializar la DB localmente (opcional)
TEST_LICENSE_KEY = "ABC-123-XYZ"

# -----------------------------------------------------------------
# IDENTIFICADOR DE MÁQUINA (CRC)
# Usamos la dirección MAC para un identificador único y persistente.
# -----------------------------------------------------------------
def get_machine_id():
    """Genera un ID de máquina simple basado en la dirección MAC."""
    # Usar el MAC address como un identificador único de la máquina (CRC)
    return hex(get_mac()) 

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
    if not os.path.exists(LICENSE_FILE):
        sys.stderr.write("\n🚨 MÁQUINA CAZADORA CRC ACTIVADA: LICENCIA REQUERIDA.\n")
        sys.stderr.write("   Ejecute: 'logconv activar [SU_CLAVE_AQUÍ]' para continuar.\n")
        sys.stderr.write("   Obtenga su clave en: https://echek7.github.io/logpattern_converter/\n\n")
        sys.exit(2)

# =================================================================
# LÓGICA DE CONVERSIÓN DE LOGS
# =================================================================

def convertir_log_a_json(linea_log):
    # Lógica de conversión... (sin cambios)
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
            return output_data 
        except Exception:
            return {"status": "ERROR_PARSING", "raw_log": linea_log.strip()}
    return {"status": "NOT_PARSED", "raw_log": linea_log.strip()} 

# =================================================================
# MANEJADORES DE SUB-COMANDOS
# =================================================================

def handle_activar(args):
    """Lógica para el comando 'logconv activar [CLAVE]'. Ahora usa la API remota."""
    key = args.license_key
    
    # 1. Obtener ID de la máquina (CRC)
    machine_id = get_machine_id()
    
    # 2. Preparar el payload: CORRECCIÓN: Usar 'license_key' para coincidir con el servidor (snake_case)
    payload = {
        'license_key': key, # <-- CORRECCIÓN AQUI: CLAVE EN SNAKE_CASE
        'machineId': machine_id
    }
    
    sys.stdout.write(f"\n⚙️ Verificando clave '{key}' (CRC: {machine_id}) contra el Servidor de Licencias en: {LICENSE_API_URL}...\n")
    
    try:
        # 3. Enviar la clave y el machineId a la Cloud Function
        response = requests.post(
            LICENSE_API_URL, 
            json=payload,
            timeout=10 # Tiempo de espera de 10 segundos
        )
        response.raise_for_status() # Lanza excepción para códigos 4xx/5xx

        # 4. Procesar la respuesta
        full_result = response.json()
        
        # Usamos full_result directamente ya que esperamos una respuesta HTTP estándar
        result = full_result
        
        # Adaptar la verificación para usar 'valid' o 'success' del servidor
        if result.get('success') is True or result.get('valid') is True:
            guardar_licencia(key)
        else:
            # Preferir 'message' si existe en la respuesta del servidor
            message = result.get('message', 'Clave no válida o no activada.')
            sys.stderr.write(f"\n❌ ERROR DE LICENCIA: {message}\n")
            sys.stderr.write("   Por favor, visite nuestro Vendedor M2M para obtener una licencia.\n\n")
            sys.exit(2)

    except requests.exceptions.Timeout:
        sys.stderr.write(f"\n❌ ERROR DE CONEXIÓN: La solicitud tardó más de 10 segundos en responder (Timeout).\n")
        sys.stderr.write("   Esto puede indicar que la Cloud Function está inactiva o tardando demasiado en ejecutarse.\n\n")
        sys.exit(2)
    except requests.exceptions.RequestException as e:
        sys.stderr.write(f"\n❌ ERROR DE CONEXIÓN: No se pudo contactar al servidor de licencias en {LICENSE_API_URL}.\n")
        sys.stderr.write(f"   Asegúrese de que su Cloud Function esté funcionando correctamente y que la URL sea pública.\n")
        if hasattr(e, 'response') and e.response is not None and hasattr(e.response, 'text'):
             sys.stderr.write(f"   Respuesta del Servidor (DEBUG): {e.response.text}\n")
        sys.stderr.write(f"   Detalle: {e}\n\n")
        sys.exit(2)
    except Exception as e:
        sys.stderr.write(f"\n❌ ERROR INESPERADO durante la verificación de la licencia: {e}\n\n")
        sys.exit(2)


def handle_convertir(args):
    """Lógica para el comando 'logconv convertir [ARCHIVO]'"""
    verificar_licencia_y_fallar() 
    file_path = args.file_path
    line_count = 0 
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line_count += 1
                line = line.strip()
                if line:
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
    verificar_licencia_y_fallar() 
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
                    try:
                        response = requests.post(webhook_url, json=data_dict, timeout=10)
                        response.raise_for_status() 
                        sys.stdout.write(f".") 
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
    subparsers = parser.add_subparsers(dest='command', required=True, help='Comandos disponibles')
    
    # --- COMANDO ACTIVAR ---
    parser_activar = subparsers.add_parser('activar', help='Activa la licencia para uso de por vida.')
    parser_activar.add_argument('license_key', type=str, help='Clave de licencia.')
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

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()