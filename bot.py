import requests
import time
import os
import platform
import psutil
import datetime
import socket
import logging

# Configurar logging para ver qué pasa
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}"

class TelegramBot:
    def __init__(self):
        self.offset = None
        logger.info("🚀 Bot de Telegram iniciado (Modo Polling)")
    
    def get_updates(self):
        """Obtener mensajes nuevos de Telegram"""
        try:
            url = f"{API_URL}/getUpdates"
            params = {"timeout": 30, "offset": self.offset}
            response = requests.get(url, params=params, timeout=35)
            response.raise_for_status()
            return response.json().get("result", [])
        except Exception as e:
            logger.error(f"❌ Error obteniendo updates: {e}")
            return []
    
    def send_message(self, chat_id, text):
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
            if response.status_code == 200:
                logger.info(f"✅ Mensaje enviado a {chat_id}")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Error enviando mensaje: {e}")
            return False
    
    def get_server_status(self):
        """Obtener información del servidor (tu código original)"""
        try:
            uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time())
            cpu_percent = psutil.cpu_percent(interval=0.5)
            cpu_count = psutil.cpu_count()
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            
            try:
                ip_addr = socket.gethostbyname(socket.gethostname())
            except:
                ip_addr = "No disponible"

            info = (
                "🖥️ *Estado del servidor Choreo*\n"
                f"🏠 Hostname: `{socket.gethostname()}`\n"
                f"💻 Plataforma: `{platform.system()} {platform.release()}`\n"
                f"⏱️ Uptime: `{str(uptime).split('.')[0]}`\n"
                f"🌐 IP contenedor: `{ip_addr}`\n"
                f"⚙️ CPU: `{cpu_percent}%` ({cpu_count} núcleos)\n"
                f"💾 Memoria: `{mem.percent}%` usada\n"
                f"🗄️ Disco: `{disk.percent}%` usado\n"
                f"🔧 Modo: `Polling (getUpdates)`\n"
                "✅ **Bot funcionando correctamente**"
            )
            return info
        except Exception as e:
            return f"❌ Error obteniendo info del servidor: {str(e)}"
    
    def convert_bytes(self, size):
        """Convertir bytes a formato legible"""
        for unit in ['B','KB','MB','GB','TB']:
            if size < 1024.0:
                return f"{size:.2f}{unit}"
            size /= 1024.0
        return f"{size:.2f}PB"
    
    def process_message(self, message):
        """Procesar mensaje recibido"""
        chat_id = message["chat"]["id"]
        text = message.get("text", "").lower()
        
        logger.info(f"📩 Mensaje recibido: {text} de {chat_id}")
        
        if text == "/start":
            self.send_message(chat_id, 
                "👋 ¡Hola! Soy tu bot en Choreo 🚀\n"
                "Usa /status para ver información del servidor.\n"
                "🔧 *Modo:* Polling (getUpdates)"
            )
        elif text == "/status":
            server_info = self.get_server_status()
            self.send_message(chat_id, server_info)
        elif text == "/ping":
            self.send_message(chat_id, "🏓 ¡Pong! Bot activo en Choreo")
        else:
            self.send_message(chat_id, 
                "🤖 No entendí tu mensaje, pero estoy activo en Choreo 😎\n"
                "Usa /status para ver info del servidor"
            )
    
    def run(self):
        """Bucle principal de polling"""
        logger.info("🔄 Iniciando bucle de polling...")
        
        while True:
            try:
                updates = self.get_updates()
                
                if updates:
                    logger.info(f"📥 {len(updates)} mensajes nuevos")
                
                for update in updates:
                    # Actualizar offset para no procesar dos veces el mismo mensaje
                    self.offset = update["update_id"] + 1
                    
                    if "message" in update:
                        self.process_message(update["message"])
                    else:
                        logger.info(f"📨 Update sin message: {update}")
                
                # Pequeña pausa entre ciclos de polling
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("🛑 Bot detenido por el usuario")
                break
            except Exception as e:
                logger.error(f"💥 Error en bucle principal: {e}")
                time.sleep(5)  # Esperar más en caso de error

if __name__ == "__main__":
    logger.info("🎯 Iniciando Bot de Telegram...")
    
    if not TOKEN:
        logger.error("❌ TELEGRAM_TOKEN no configurado")
        exit(1)
    
    bot = TelegramBot()
    bot.run()
