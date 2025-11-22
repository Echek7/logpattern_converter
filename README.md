## LogPattern Converter CLI

### 🛠️ Herramienta Profesional de Refactorización de Logs

LogPattern Converter es una herramienta de línea de comandos (CLI) esencial para ingenieros de DevOps, SREs y administradores de sistemas que enfrentan la tarea crítica de **refactorizar, convertir y estandarizar patrones de logs complejos** de entornos heredados (legacy) a formatos modernos como JSON.

**Nuestro compromiso:** Eliminar las horas de trabajo manual en la migración de logs. El programa está diseñado para ser **robusto, veloz y a prueba de logs malformados**, asegurando una salida de JSON limpia y compatible con cualquier plataforma de observabilidad moderna (Datadog, Splunk, Elastic, etc.).

---

### 🚀 Instalación

Una vez que adquieras tu licencia de por vida, la instalación es simple y sigue el estándar profesional de Python:

```bash
pip install logpattern_converter
```
🔑 Licencia Requerida (Máquina Cazadora CRC)

Esta herramienta está protegida por nuestra Máquina Cazadora (Code Revenue Closure - CRC). Para acceder a la función principal de conversión, se requiere la activación de una licencia.

💰 Obtén tu clave de licencia AHORA por $9.99 USD.
El pago único incluye la clave de activación para uso ilimitado y acceso a todas las futuras actualizaciones de patrones.

➡️ Vendedor M2M (Sitio Web Oficial):
https://echek7.github.io/logpattern_converter 

---

1️⃣ Activación de la Licencia

Utiliza el sub-comando ```activar``` con la clave que recibiste por correo electrónico. Esto registra la licencia de forma persistente en tu máquina (en un archivo oculto ```.crc_license.json```).
```bash
logconv activar [SU_CLAVE_DE_LICENCIA_AQUÍ]
```
Verificación Exitosa:

```✅ LICENCIA ACTIVADA: Clave '...' guardada con éxito```.

Mensaje de la Máquina Cazadora: Si intentas saltar este paso y usar ```convertir```, el sistema mostrará un mensaje que te redirige a la URL de pago.

2️⃣ Conversión de Logs a Archivo Local

Una vez activado, puedes usar el comando ```convertir``` para procesar cualquier archivo de logs.
Los resultados se imprimen a la salida estándar (```stdout```), permitiendo la redirección simple a un archivo JSON.

```bash
# Sintaxis: logconv convertir [ARCHIVO_DE_ENTRADA] > [ARCHIVO_JSON_DE_SALIDA]
logconv convertir logs_sucios.txt > reporte_estandarizado.json
```

---

Contacto y Soporte Técnico
Para garantizar la autonomía y una respuesta rápida, todo el soporte, consultas de licenciamiento y reporte de problemas se centraliza en el sistema de GitHub Issues.

Abrir un Issue: Visita el Issue Tracker del repositorio oficial.
