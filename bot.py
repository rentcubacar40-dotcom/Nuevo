import requests
import time
import os
import platform
import socket
import datetime
import logging
import threading
import psutil
import uuid
import subprocess

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}"

def keep_alive():
    """Mantener worker activo en Choreo"""
    while True:
        logger.info("❤️ Worker activo - Manteniendo servicio")
        time.sleep(1800)  # 30 minutos

def send_message(chat_id, text):
    """Enviar mensaje a Telegram"""
    try:
        response = requests.post(
            f"{API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error enviando mensaje: {e}")
        return False

def get_detailed_server_info():
    """Obtener información DETALLADA del servidor Choreo"""
    try:
        # Información básica del sistema
        hostname = socket.gethostname()
        system = platform.system()
        release = platform.release()
        architecture = platform.machine()
        processor = platform.processor()
        
        # Información de red
        try:
            ip_local = socket.gethostbyname(hostname)
        except:
            ip_local = "No disponible"
        
        # Información de Choreo desde variables de entorno
        choreo_env_vars = {k: v for k, v in os.environ.items() if 'CHOREO' in k.upper()}
        
        # Información de Python
        python_version = platform.python_version()
        python_implementation = platform.python_implementation()
        
        # Información de procesos y recursos
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.datetime.now() - boot_time
        
        # Información de red y conexiones
        network_io = psutil.net_io_counters()
        
        # Información del proceso actual
        process = psutil.Process()
        process_memory = process.memory_info()
        process_cpu = process.cpu_percent()
        
        # Información de tiempo y fecha
        current_time = datetime.datetime.now()
        timezone = current_time.astimezone().tzinfo
        
        # Construir mensaje detallado
        info = (
            "🖥️ *INFORMACIÓN DETALLADA DEL SERVIDOR CHOREO*\n\n"
            
            "🔧 *INFORMACIÓN BÁSICA:*\n"
            f"• Hostname: `{hostname}`\n"
            f"• Sistema: `{system} {release}`\n"
            f"• Arquitectura: `{architecture}`\n"
            f"• Procesador: `{processor}`\n"
            f"• IP Local: `{ip_local}`\n\n"
            
            "🐍 *INFORMACIÓN PYTHON:*\n"
            f"• Versión: `{python_version}`\n"
            f"• Implementación: `{python_implementation}`\n\n"
            
            "⚡ *RECURSOS DEL SISTEMA:*\n"
            f"• Uso CPU: `{cpu_percent}%`\n"
            f"• Núcleos: `{cpu_count}`\n"
            f"• Frecuencia CPU: `{cpu_freq.current if cpu_freq else 'N/A'} MHz`\n"
            f"• Memoria Usada: `{memory.percent}%` ({self._bytes_to_mb(memory.used)}/{self._bytes_to_mb(memory.total)} MB)\n"
            f"• Disco Usado: `{disk.percent}%` ({self._bytes_to_gb(disk.used)}/{self._bytes_to_gb(disk.total)} GB)\n"
            f"• Uptime: `{str(uptime).split('.')[0]}`\n\n"
            
            "🌐 *RED Y CONEXIONES:*\n"
            f"• Bytes Enviados: `{self._bytes_to_mb(network_io.bytes_sent)} MB`\n"
            f"• Bytes Recibidos: `{self._bytes_to_mb(network_io.bytes_recv)} MB`\n\n"
            
            "📊 *PROCESO ACTUAL:*\n"
            f"• Memoria Proceso: `{self._bytes_to_mb(process_memory.rss)} MB`\n"
            f"• CPU Proceso: `{process_cpu}%`\n"
            f"• Hora Servidor: `{current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}`\n\n"
            
            "🔍 *VARIABLES CHOREO:*\n"
            f"• Total Variables: `{len(choreo_env_vars)}`\n"
        )
        
        # Agregar variables específicas de Choreo (primeras 3)
        for i, (key, value) in enumerate(list(choreo_env_vars.items())[:3]):
            info += f"• {key}: `{value[:30]}...`\n"
        
        info += f"\n✅ *Bot activo desde*: `{boot_time.strftime('%H:%M:%S')}`"
        
        return info
        
    except Exception as e:
        return f"❌ Error obteniendo información del servidor: {str(e)}"

def _bytes_to_mb(self, bytes_value):
    """Convertir bytes a MB"""
    return round(bytes_value / (1024 * 1024), 2)

def _bytes_to_gb(self, bytes_value):
    """Convertir bytes a GB"""
    return round(bytes_value / (1024 * 1024 * 1024), 2)

def get_quick_server_info():
    """Información rápida del servidor"""
    try:
        hostname = socket.gethostname()
        cpu_percent = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        
        info = (
            "📊 *ESTADO RÁPIDO DEL SERVIDOR*\n"
            f"• Hostname: `{hostname}`\n"
            f"• CPU: `{cpu_percent}%`\n"
            f"• Memoria: `{memory.percent}%`\n"
            f"• Hora: `{datetime.datetime.now().strftime('%H:%M:%S')}`\n"
            "✅ *Sistema estable*"
        )
        return info
    except Exception as e:
        return f"❌ Error: {str(e)}"

def process_message(chat_id, text):
    """Procesar mensajes y comandos"""
    logger.info(f"Procesando mensaje: {text} de {chat_id}")
    
    if text == "/start":
        welcome_msg = (
            "🤖 *BOT CHOREO - INFORMACIÓN DEL SERVIDOR*\n\n"
            "📋 *Comandos disponibles:*\n"
            "• `/info` - Información detallada del servidor\n"
            "• `/status` - Estado rápido del sistema\n"
            "• `/resources` - Uso de recursos en tiempo real\n"
            "• `/help` - Mostrar esta ayuda\n\n"
            "🔧 *Servidor:* Choreo Workers\n"
            "🔄 *Modo:* Polling activo"
        )
        send_message(chat_id, welcome_msg)
        
    elif text == "/info":
        server_info = get_detailed_server_info()
        # Dividir mensaje largo si es necesario
        if len(server_info) > 4000:
            parts = [server_info[i:i+4000] for i in range(0, len(server_info), 4000)]
            for part in parts:
                send_message(chat_id, part)
                time.sleep(0.5)
        else:
            send_message(chat_id, server_info)
            
    elif text == "/status":
        quick_info = get_quick_server_info()
        send_message(chat_id, quick_info)
        
    elif text == "/resources":
        resources_msg = get_quick_server_info()
        send_message(chat_id, resources_msg)
        
    elif text == "/help":
        help_msg = (
            "🆘 *AYUDA - COMANDOS DISPONIBLES*\n\n"
            "• `/info` - Información COMPLETA del servidor\n"
            "• `/status` - Estado rápido del sistema\n" 
            "• `/resources` - Uso de recursos en tiempo real\n"
            "• `/help` - Mostrar esta ayuda\n\n"
            "💡 Usa `/info` para ver todos los detalles del servidor Choreo"
        )
        send_message(chat_id, help_msg)
        
    else:
        send_message(chat_id, 
            "❌ Comando no reconocido\n\n"
            "Usa `/help` para ver los comandos disponibles"
        )

def main():
    """Función principal"""
    logger.info("🚀 Iniciando Bot Detallado de Choreo")
    
    # Verificar token
    if not TOKEN:
        logger.error("❌ TELEGRAM_TOKEN no configurado")
        return
    
    # Iniciar keep-alive
    threading.Thread(target=keep_alive, daemon=True).start()
    logger.info("🫀 Keep-alive activado")
    
    # Bucle principal de polling
    offset = None
    while True:
        try:
            params = {"timeout": 25, "offset": offset}
            response = requests.get(f"{API_URL}/getUpdates", params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    updates = data.get("result", [])
                    
                    for update in updates:
                        if "message" in update:
                            chat_id = update["message"]["chat"]["id"]
                            text = update["message"].get("text", "").lower().strip()
                            process_message(chat_id, text)
                        
                        offset = update["update_id"] + 1
            
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error en polling: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
