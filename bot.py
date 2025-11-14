"""
YouTube Telegram Bot
Copyright (C) 2024 Tu Nombre

Licencia AGPLv3: https://www.gnu.org/licenses/agpl-3.0.html
Uso educativo y personal. Usuario responsable del cumplimiento legal.
"""

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
import json
from urllib.parse import urlparse

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%m/%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuración
BOT_VERSION = "BOT_SIMPLE_v1_" + datetime.datetime.now().strftime("%m%d%H%M")
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}"

# Contadores
activity_counter = 0
start_time = datetime.datetime.now()

def send_telegram_message(chat_id, text):
    """Enviar mensaje a Telegram"""
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
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error enviando mensaje: {e}")
        return False

def get_system_info():
    """Obtener información del sistema"""
    try:
        hostname = socket.gethostname()
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/').percent
        
        uptime = datetime.datetime.now() - start_time
        
        info_message = (
            f"🖥️ *INFORMACIÓN DEL SISTEMA*\n"
            f"*Versión:* `{BOT_VERSION}`\n\n"
            f"• Hostname: `{hostname}`\n"
            f"• CPU: `{cpu_usage}%`\n"
            f"• Memoria: `{memory_usage}%`\n"
            f"• Disco: `{disk_usage}%`\n"
            f"• Solicitudes: `{activity_counter}`\n"
            f"• Tiempo activo: `{str(uptime).split('.')[0]}`\n\n"
            f"✅ *Sistema estable*"
        )
        return info_message
    except Exception as e:
        return f"❌ Error: {str(e)}"

def aggressive_keep_alive():
    """Mantener el bot activo"""
    global activity_counter
    while True:
        try:
            activity_counter += 1
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_usage = psutil.virtual_memory().percent
            
            logger.info(f"🔄 Keep-alive #{activity_counter} | CPU: {cpu_usage}% | RAM: {memory_usage}%")
            time.sleep(300)  # 5 minutos
            
        except Exception as e:
            logger.error(f"Error en keep-alive: {e}")
            time.sleep(60)

def handle_youtube_info(chat_id, url):
    """Proporcionar información sobre descargas de YouTube"""
    info_message = (
        "📹 *INFORMACIÓN SOBRE DESCARGAS DE YOUTUBE*\n\n"
        
        "🔒 *Situación Actual:*\n"
        "YouTube ha implementado protecciones avanzadas que "
        "bloquean descargas desde entornos cloud como Choreo.\n\n"
        
        "💡 *Soluciones Disponibles:*\n"
        "• Usar una **VPN personal**\n" 
        "• **Servidor local** con IP residencial\n"
        "• **Aplicaciones de escritorio** como yt-dlp\n"
        "• **Extensiones de navegador** permitidas\n\n"
        
        "⚠️ *Limitaciones Técnicas:*\n"
        "• IPs de cloud están en listas negras\n"
        "• Detección de automatización\n"
        "• Protección anti-bots activa\n\n"
        
        "🎯 *Recomendación:*\n"
        "Para descargas confiables, usa yt-dlp en tu computadora personal."
    )
    
    send_telegram_message(chat_id, info_message)

def handle_telegram_message(chat_id, message_text):
    """Procesar mensajes de Telegram"""
    global activity_counter
    activity_counter += 1
    
    if message_text == "/start":
        welcome_message = (
            f"🤖 *Bot de Información YouTube*\n"
            f"*Versión:* `{BOT_VERSION}`\n\n"
            
            "📋 *Comandos Disponibles:*\n"
            "• `/info` - Información del sistema\n"
            "• `/status` - Estado del bot\n" 
            "• `/youtube_info` - Info sobre descargas\n"
            "• `/alive` - Test de conexión\n\n"
            
            "🔍 *Funcionalidad:*\n"
            "Este bot proporciona información técnica sobre "
            "descargas de YouTube y estado del sistema.\n\n"
            
            "⚠️ *Uso educativo y informativo*"
        )
        send_telegram_message(chat_id, welcome_message)
        
    elif message_text == "/info":
        system_info = get_system_info()
        send_telegram_message(chat_id, system_info)
        
    elif message_text == "/status":
        uptime = datetime.datetime.now() - start_time
        status_message = (
            f"⚡ *Estado del Bot - {BOT_VERSION}*\n\n"
            f"• Activo: `{str(uptime).split('.')[0]}`\n"
            f"• Solicitudes: `{activity_counter}`\n" 
            f"• CPU: `{psutil.cpu_percent()}%`\n"
            f"• Memoria: `{psutil.virtual_memory().percent}%`\n"
            f"• Hora: `{datetime.datetime.now().strftime('%H:%M:%S')}`\n\n"
            "✅ *Bot operativo*"
        )
        send_telegram_message(chat_id, status_message)
        
    elif message_text == "/youtube_info":
        handle_youtube_info(chat_id, "")
        
    elif message_text == "/alive":
        send_telegram_message(chat_id, "💓 ¡Bot activo y respondiendo!")
        
    elif "youtube" in message_text.lower() or "descarg" in message_text.lower():
        handle_youtube_info(chat_id, "")
        
    else:
        help_message = (
            "❌ Comando no reconocido\n\n"
            "✅ *Comandos disponibles:*\n" 
            "• `/info` - Información del sistema\n"
            "• `/status` - Estado del bot\n"
            "• `/youtube_info` - Info sobre descargas YouTube\n"
            "• `/alive` - Test de conexión\n\n"
            f"*Versión:* `{BOT_VERSION}`"
        )
        send_telegram_message(chat_id, help_message)

def telegram_polling_loop():
    """Bucle principal de Telegram"""
    logger.info("🚀 Iniciando bot de Telegram...")
    offset = None
    
    while True:
        try:
            response = requests.get(
                f"{API_URL}/getUpdates", 
                params={
                    "timeout": 50,
                    "offset": offset,
                    "limit": 100
                }, 
                timeout=55
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    updates = data.get("result", [])
                    for update in updates:
                        if "message" in update:
                            chat_id = update["message"]["chat"]["id"]
                            text = update["message"].get("text", "").strip()
                            handle_telegram_message(chat_id, text)
                        offset = update["update_id"] + 1
            time.sleep(2)
            
        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            logger.error(f"Error en polling: {e}")
            time.sleep(10)

def main():
    """Función principal"""
    logger.info(f"🎯 Iniciando Bot v{BOT_VERSION}")
    
    if not TOKEN:
        logger.error("❌ TELEGRAM_TOKEN no configurado")
        return
    
    # Iniciar keep-alive
    keep_alive_thread = threading.Thread(target=aggressive_keep_alive, daemon=True)
    keep_alive_thread.start()
    logger.info("🔴 Keep-alive activado")
    
    # Iniciar polling de Telegram
    telegram_polling_loop()

if __name__ == "__main__":
    main()
