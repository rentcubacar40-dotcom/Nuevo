import requests
import time
import os
import platform
import socket
import datetime
import logging
import threading
import psutil
import random

# ⚡ CONFIGURACIÓN AVANZADA DE LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%m/%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 🔥 VERSIÓN Y CONFIGURACIÓN
BOT_VERSION = "ULTRA_ACTIVE_" + datetime.datetime.now().strftime("%m%d%H%M")
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}"

# 📊 CONTADORES DE ACTIVIDAD
activity_counter = 0
start_time = datetime.datetime.now()

def bytes_to_mb(bytes_value):
    """Convertir bytes a MB"""
    return round(bytes_value / (1024 * 1024), 2)

def bytes_to_gb(bytes_value):
    """Convertir bytes a GB"""
    return round(bytes_value / (1024 * 1024 * 1024), 2)

def aggressive_keep_alive():
    """🔥 KEEP-ALIVE SUPER AGRESIVO CADA 5 MINUTOS"""
    global activity_counter
    
    while True:
        try:
            # 🌐 ACTIVIDAD DE RED 1 - HTTP Request
            requests.get("https://httpbin.org/json", timeout=10)
            logger.info("🌐 Keep-alive: HTTP Request completada")
            
            # 💾 ACTIVIDAD DE DISCO - Escribir archivo
            with open("/tmp/bot_heartbeat.txt", "w") as f:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"Heartbeat: {timestamp} | Counter: {activity_counter}")
            
            # ⚡ ACTIVIDAD DE CPU - Cálculos intensivos
            numbers = [random.randint(1, 1000) for _ in range(10000)]
            sorted_numbers = sorted(numbers)
            sum_total = sum(sorted_numbers)
            
            # 📊 ACTIVIDAD DE SISTEMA - Monitoreo
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_usage = psutil.virtual_memory().percent
            
            # 🔄 CONTADOR Y LOG
            activity_counter += 1
            uptime = datetime.datetime.now() - start_time
            
            logger.info(f"🔴 KEEP-ALIVE #{activity_counter} | CPU: {cpu_usage}% | RAM: {memory_usage}% | Uptime: {str(uptime).split('.')[0]}")
            
        except Exception as e:
            logger.error(f"❌ Keep-alive error: {e}")
        
        # ⏰ ESPERA 5 MINUTOS EXACTOS
        time.sleep(300)

def send_telegram_message(chat_id, text):
    """Enviar mensaje a Telegram con manejo de errores"""
    try:
        response = requests.post(
            f"{API_URL}/sendMessage",
            json={
                "chat_id": chat_id, 
                "text": text, 
                "parse_mode": "Markdown"
            },
            timeout=10
        )
        success = response.status_code == 200
        if success:
            logger.info(f"📤 Mensaje enviado a {chat_id}")
        return success
    except Exception as e:
        logger.error(f"❌ Error enviando mensaje: {e}")
        return False

def get_comprehensive_system_info():
    """📊 INFORMACIÓN COMPLETA DEL SISTEMA"""
    try:
        # 🔧 INFORMACIÓN BÁSICA
        hostname = socket.gethostname()
        system_info = platform.system()
        release_info = platform.release()
        architecture = platform.machine()
        
        # ⚡ INFORMACIÓN DE CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_cores = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        
        # 💾 INFORMACIÓN DE MEMORIA
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # 💽 INFORMACIÓN DE DISCO
        disk = psutil.disk_usage('/')
        
        # 🌐 INFORMACIÓN DE RED
        try:
            ip_address = socket.gethostbyname(hostname)
        except:
            ip_address = "No disponible"
        
        net_io = psutil.net_io_counters()
        
        # 📊 INFORMACIÓN DEL PROCESO
        current_process = psutil.Process()
        process_memory = current_process.memory_info()
        process_cpu = current_process.cpu_percent()
        
        # ⏰ INFORMACIÓN DE TIEMPO
        current_time = datetime.datetime.now()
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        system_uptime = current_time - boot_time
        bot_uptime = current_time - start_time
        
        # 🎯 CONSTRUIR MENSAJE
        info_message = (
            f"🖥️ *INFORMACIÓN COMPLETA DEL SERVIDOR*\n"
            f"*Versión Bot:* `{BOT_VERSION}`\n\n"
            
            "🔧 *INFORMACIÓN DEL SISTEMA:*\n"
            f"• Hostname: `{hostname}`\n"
            f"• Sistema: `{system_info} {release_info}`\n"
            f"• Arquitectura: `{architecture}`\n"
            f"• IP Local: `{ip_address}`\n\n"
            
            "⚡ *RENDIMIENTO CPU:*\n"
            f"• Uso Actual: `{cpu_percent}%`\n"
            f"• Núcleos: `{cpu_cores}`\n"
            f"• Frecuencia: `{cpu_freq.current if cpu_freq else 'N/A'} MHz`\n\n"
            
            "💾 *MEMORIA RAM:*\n"
            f"• Uso: `{memory.percent}%`\n"
            f"• Total: `{bytes_to_gb(memory.total)} GB`\n"
            f"• Disponible: `{bytes_to_gb(memory.available)} GB`\n"
            f"• Swap: `{bytes_to_gb(swap.used)}/{bytes_to_gb(swap.total)} GB`\n\n"
            
            "💽 *ALMACENAMIENTO:*\n"
            f"• Disco Usado: `{disk.percent}%`\n"
            f"• Total: `{bytes_to_gb(disk.total)} GB`\n"
            f"• Libre: `{bytes_to_gb(disk.free)} GB`\n\n"
            
            "🌐 *RED Y CONEXIONES:*\n"
            f"• Bytes Enviados: `{bytes_to_mb(net_io.bytes_sent)} MB`\n"
            f"• Bytes Recibidos: `{bytes_to_mb(net_io.bytes_recv)} MB`\n\n"
            
            "📊 *ESTADO DEL BOT:*\n"
            f"• Memoria Usada: `{bytes_to_mb(process_memory.rss)} MB`\n"
            f"• CPU Bot: `{process_cpu}%`\n"
            f"• Keep-alives: `{activity_counter}`\n"
            f"• Uptime Sistema: `{str(system_uptime).split('.')[0]}`\n"
            f"• Uptime Bot: `{str(bot_uptime).split('.')[0]}`\n"
            f"• Hora Servidor: `{current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}`\n\n"
            
            "✅ *SISTEMA ESTABLE Y MONITOREADO*"
        )
        
        return info_message
        
    except Exception as e:
        return f"❌ Error obteniendo información del sistema: {str(e)}"

def get_quick_status():
    """⚡ ESTADO RÁPIDO DEL SISTEMA"""
    try:
        cpu_usage = psutil.cpu_percent(interval=0.5)
        memory_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/').percent
        
        status_message = (
            f"⚡ *ESTADO RÁPIDO - {BOT_VERSION}*\n\n"
            f"• CPU: `{cpu_usage}%`\n"
            f"• Memoria: `{memory_usage}%`\n"
            f"• Disco: `{disk_usage}%`\n"
            f"• Keep-alives: `{activity_counter}`\n"
            f"• Hora: `{datetime.datetime.now().strftime('%H:%M:%S')}`\n\n"
            "✅ *Sistema funcionando correctamente*"
        )
        
        return status_message
    except Exception as e:
        return f"❌ Error: {str(e)}"

def handle_telegram_message(chat_id, message_text):
    """📨 PROCESAR MENSAJES DE TELEGRAM"""
    global activity_counter
    
    logger.info(f"📩 Mensaje recibido: '{message_text}' de {chat_id}")
    
    # 🔄 INCREMENTAR CONTADOR DE ACTIVIDAD
    activity_counter += 1
    
    if message_text == "/start":
        welcome_message = (
            f"🤖 *BOT CHOREO - VERSIÓN AVANZADA*\n"
            f"*Versión:* `{BOT_VERSION}`\n\n"
            
            "📋 *COMANDOS DISPONIBLES:*\n"
            "• `/info` - Información COMPLETA del servidor\n"
            "• `/status` - Estado rápido del sistema\n"
            "• `/stats` - Estadísticas del bot\n"
            "• `/alive` - Test de respuestaaa\n\n"
            
            "🔧 *CARACTERÍSTICAS:*\n"
            "• Keep-alive agresivo cada 5min\n"
            "• Monitoreo completo del sistema\n"
            "• Logs de actividad en tiempo real\n\n"
            
            "✅ *Bot optimizado para Choreo*"
        )
        send_telegram_message(chat_id, welcome_message)
        
    elif message_text == "/info":
        system_info = get_comprehensive_system_info()
        send_telegram_message(chat_id, system_info)
        
    elif message_text == "/status":
        quick_status = get_quick_status()
        send_telegram_message(chat_id, quick_status)
        
    elif message_text == "/stats":
        uptime = datetime.datetime.now() - start_time
        stats_message = (
            f"📊 *ESTADÍSTICAS DEL BOT - {BOT_VERSION}*\n\n"
            f"• Keep-alives ejecutados: `{activity_counter}`\n"
            f"• Tiempo activo: `{str(uptime).split('.')[0]}`\n"
            f"• Iniciado: `{start_time.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"• Última actividad: `{datetime.datetime.now().strftime('%H:%M:%S')}`\n"
            f"• Hostname: `{socket.gethostname()}`\n\n"
            "🔴 *Keep-alive activo cada 5 minutos*"
        )
        send_telegram_message(chat_id, stats_message)
        
    elif message_text == "/alive":
        send_telegram_message(chat_id, "💓 ¡BOT VIVO Y RESPONDIENDO! ✅")
        
    else:
        help_message = (
            "❌ Comando no reconocido\n\n"
            "✅ *Comandos disponibles:*\n"
            "• `/info` - Info completa del servidor\n"
            "• `/status` - Estado rápido\n"
            "• `/stats` - Estadísticas del bot\n"
            "• `/alive` - Test de respuesta\n\n"
            f"*Versión:* `{BOT_VERSION}`"
        )
        send_telegram_message(chat_id, help_message)

def telegram_polling_loop():
    """🔄 BUCLE PRINCIPAL DE POLLING"""
    logger.info("🚀 INICIANDO BUCLE DE POLLING DE TELEGRAM")
    
    offset = None
    error_count = 0
    
    while True:
        try:
            # 📡 OBTENER MENSAJES DE TELEGRAM
            polling_params = {
                "timeout": 50,  # ⏰ Timeout largo
                "offset": offset,
                "limit": 100
            }
            
            response = requests.get(
                f"{API_URL}/getUpdates", 
                params=polling_params, 
                timeout=55
            )
            
            if response.status_code == 200:
                telegram_data = response.json()
                
                if telegram_data.get("ok"):
                    updates = telegram_data.get("result", [])
                    
                    if updates:
                        logger.info(f"📥 {len(updates)} mensaje(s) nuevo(s) recibido(s)")
                        
                        for update in updates:
                            if "message" in update:
                                chat_id = update["message"]["chat"]["id"]
                                text_content = update["message"].get("text", "").strip().lower()
                                handle_telegram_message(chat_id, text_content)
                            
                            # ACTUALIZAR OFFSET
                            offset = update["update_id"] + 1
                    
                    # 🔄 RESETEAR CONTADOR DE ERRORES
                    error_count = 0
                    
                else:
                    logger.error(f"❌ Error en API de Telegram: {telegram_data}")
                    error_count += 1
            else:
                logger.error(f"❌ Error HTTP {response.status_code}")
                error_count += 1
            
            # 🛑 MANEJO DE ERRORES CONSECUTIVOS
            if error_count >= 3:
                logger.warning(f"⚠️ Muchos errores consecutivos, esperando 30 segundos...")
                time.sleep(30)
            else:
                time.sleep(2)  # ⏱️ Espera normal entre ciclos
                
        except requests.exceptions.Timeout:
            logger.warning("⏰ Timeout en polling, continuando...")
            continue
            
        except requests.exceptions.ConnectionError:
            logger.error("🔌 Error de conexión, reintentando en 15 segundos...")
            time.sleep(15)
            
        except Exception as e:
            logger.error(f"💥 Error inesperado en polling: {e}")
            time.sleep(10)

def main():
    """🎯 FUNCIÓN PRINCIPAL"""
    logger.info(f"🚀 INICIANDO BOT TELEGRAM - {BOT_VERSION}")
    logger.info(f"📅 Hora de inicio: {datetime.datetime.now()}")
    
    # 🚫 VERIFICAR TOKEN
    if not TOKEN:
        logger.error("❌ ERROR: TELEGRAM_TOKEN no configurado")
        logger.error("💡 Configura la variable de entorno en Choreo")
        return
    
    logger.info("✅ Token de Telegram configurado correctamente")
    
    # 🔥 INICIAR KEEP-ALIVE SUPREMO (CADA 5 MINUTOS)
    keep_alive_thread = threading.Thread(target=aggressive_keep_alive, daemon=True)
    keep_alive_thread.start()
    logger.info("🔴 KEEP-ALIVE AGRESIVO ACTIVADO - Cada 5 minutos")
    
    # 🔄 INICIAR POLLING DE TELEGRAM
    telegram_polling_loop()

if __name__ == "__main__":
    main()
