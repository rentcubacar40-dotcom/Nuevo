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
import hashlib
from urllib.parse import urlparse

# ⚡ CONFIGURACIÓN DE LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%m/%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 🔥 CONFIGURACIÓN
BOT_VERSION = "BOT_LEGAL_v1_" + datetime.datetime.now().strftime("%m%d%H%M")
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}"

# 📊 CONTADORES
activity_counter = 0
start_time = datetime.datetime.now()

# 🔧 VERIFICAR MÓDULOS
YOUTUBE_AVAILABLE = False
try:
    import yt_dlp
    YOUTUBE_AVAILABLE = True
    logger.info("✅ Módulo YouTube disponible")
except ImportError as e:
    logger.warning(f"⚠️ YouTube no disponible: {e}")

class YouTubeDownloader:
    def __init__(self):
        if not YOUTUBE_AVAILABLE:
            logger.error("❌ YouTube Downloader no disponible")
            return
            
        self.downloaded_videos = set()
        self.load_downloaded_list()
        self.setup_directories()
        
        # Configuración básica de yt-dlp
        self.ydl_opts = {
            'outtmpl': '/tmp/youtube_downloads/%(title).100s.%(ext)s',
            'restrictfilenames': True,
            'nooverwrites': True,
            'writethumbnail': False,
        }
    
    def setup_directories(self):
        """Crear directorios necesarios"""
        try:
            os.makedirs('/tmp/youtube_downloads', exist_ok=True)
            logger.info("✅ Directorios de descarga creados")
        except Exception as e:
            logger.warning(f"⚠️ Error creando directorios: {e}")
    
    def load_downloaded_list(self):
        """Cargar lista de videos descargados"""
        try:
            if os.path.exists('/tmp/downloaded_videos.json'):
                with open('/tmp/downloaded_videos.json', 'r') as f:
                    data = json.load(f)
                    self.downloaded_videos = set(data.get('videos', []))
                logger.info(f"✅ Lista cargada: {len(self.downloaded_videos)} videos")
        except Exception as e:
            logger.warning(f"❌ Error cargando lista: {e}")
    
    def save_downloaded_list(self):
        """Guardar lista de videos descargados"""
        try:
            with open('/tmp/downloaded_videos.json', 'w') as f:
                json.dump({'videos': list(self.downloaded_videos)}, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Error guardando lista: {e}")
    
    def get_video_id(self, url: str) -> str:
        """Generar ID único para el video"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def is_valid_youtube_url(self, url: str) -> bool:
        """Validar si es URL de YouTube válida"""
        try:
            parsed = urlparse(url)
            return any(domain in parsed.netloc for domain in ['youtube.com', 'youtu.be'])
        except:
            return False
    
    def get_video_info(self, url: str) -> dict:
        """Obtener información del video"""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                return {
                    'success': True,
                    'title': info.get('title', ''),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', ''),
                    'view_count': info.get('view_count', 0),
                    'timestamp': datetime.datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo info: {e}")
            return {'success': False, 'error': str(e)}
    
    def download_video(self, url: str, format_type: str = 'mp4') -> dict:
        """Descargar video de YouTube"""
        try:
            if not self.is_valid_youtube_url(url):
                return {'success': False, 'error': 'URL de YouTube no válida'}
            
            video_id = self.get_video_id(url)
            if video_id in self.downloaded_videos:
                return {'success': True, 'skipped': True, 'reason': 'Ya descargado'}
            
            # Obtener información primero
            info = self.get_video_info(url)
            if not info['success']:
                return info
            
            # Configurar opciones de descarga
            download_opts = self.ydl_opts.copy()
            
            if format_type == 'mp3':
                download_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            else:
                download_opts.update({
                    'format': f'best[ext={format_type}]/best'
                })
            
            # Descargar
            logger.info(f"📥 Descargando: {info['title']}")
            with yt_dlp.YoutubeDL(download_opts) as ydl:
                ydl.download([url])
            
            # Buscar archivo descargado
            downloaded_file = None
            for filename in os.listdir('/tmp/youtube_downloads'):
                filepath = os.path.join('/tmp/youtube_downloads', filename)
                if os.path.isfile(filepath):
                    downloaded_file = {
                        'filename': filename,
                        'size_mb': round(os.path.getsize(filepath) / (1024 * 1024), 2),
                        'path': filepath
                    }
                    break
            
            # Marcar como descargado
            self.downloaded_videos.add(video_id)
            self.save_downloaded_list()
            
            return {
                'success': True,
                'downloaded': True,
                'video_info': info,
                'downloaded_file': downloaded_file,
                'format': format_type
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Error descargando: {e}")
            
            if "Sign in" in error_msg or "bot" in error_msg.lower():
                return {'success': False, 'error': 'YouTube ha bloqueado la descarga. Prueba con otro video.'}
            else:
                return {'success': False, 'error': f'Error de descarga: {error_msg}'}
    
    def get_download_stats(self) -> dict:
        """Obtener estadísticas de descargas"""
        try:
            download_dir = '/tmp/youtube_downloads'
            if not os.path.exists(download_dir):
                return {
                    'total_downloads': 0,
                    'total_size_mb': 0,
                    'downloaded_videos_count': len(self.downloaded_videos)
                }
                
            files = os.listdir(download_dir)
            total_size = sum(
                os.path.getsize(os.path.join(download_dir, f)) 
                for f in files if os.path.isfile(os.path.join(download_dir, f))
            ) / (1024 * 1024)  # MB
            
            return {
                'total_downloads': len(files),
                'total_size_mb': round(total_size, 2),
                'downloaded_videos_count': len(self.downloaded_videos)
            }
        except Exception as e:
            logger.error(f"❌ Error obteniendo stats: {e}")
            return {'error': str(e)}

# 🔥 INICIALIZAR DESCARGADOR
youtube_downloader = YouTubeDownloader()

def bytes_to_mb(bytes_value):
    """Convertir bytes a MB"""
    return round(bytes_value / (1024 * 1024), 2)

def bytes_to_gb(bytes_value):
    """Convertir bytes a GB"""
    return round(bytes_value / (1024 * 1024 * 1024), 2)

def aggressive_keep_alive():
    """Mantener el bot activo"""
    global activity_counter
    
    while True:
        try:
            # Actividad de red
            requests.get("https://httpbin.org/json", timeout=10)
            logger.info("🌐 Keep-alive: HTTP Request")
            
            # Actividad de disco
            with open("/tmp/bot_heartbeat.txt", "w") as f:
                f.write(f"Heartbeat: {datetime.datetime.now()} | Counter: {activity_counter}")
            
            # Actividad de CPU
            numbers = [random.randint(1, 1000) for _ in range(5000)]
            sorted_numbers = sorted(numbers)
            
            # Monitoreo del sistema
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_usage = psutil.virtual_memory().percent
            
            # Contador y log
            activity_counter += 1
            uptime = datetime.datetime.now() - start_time
            
            logger.info(f"🔴 KEEP-ALIVE #{activity_counter} | CPU: {cpu_usage}% | RAM: {memory_usage}% | Uptime: {str(uptime).split('.')[0]}")
            
        except Exception as e:
            logger.error(f"❌ Keep-alive error: {e}")
        
        # Esperar 5 minutos
        time.sleep(300)

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
        success = response.status_code == 200
        if success:
            logger.info(f"📤 Mensaje enviado a {chat_id}")
        return success
    except Exception as e:
        logger.error(f"❌ Error enviando mensaje: {e}")
        return False

def get_comprehensive_system_info():
    """Obtener información completa del sistema"""
    try:
        # Información básica
        hostname = socket.gethostname()
        system_info = platform.system()
        release_info = platform.release()
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_cores = psutil.cpu_count()
        
        # Memoria
        memory = psutil.virtual_memory()
        
        # Disco
        disk = psutil.disk_usage('/')
        
        # Red
        net_io = psutil.net_io_counters()
        
        # Proceso
        current_process = psutil.Process()
        process_memory = current_process.memory_info()
        
        # Descargas YouTube
        download_stats = youtube_downloader.get_download_stats()
        
        # Tiempo
        current_time = datetime.datetime.now()
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        system_uptime = current_time - boot_time
        bot_uptime = current_time - start_time
        
        # Construir mensaje
        info_message = (
            f"🖥️ *INFORMACIÓN DEL SISTEMA*\n"
            f"*Versión:* `{BOT_VERSION}`\n\n"
            
            "🔧 *SISTEMA:*\n"
            f"• Hostname: `{hostname}`\n"
            f"• Sistema: `{system_info} {release_info}`\n\n"
            
            "⚡ *CPU:*\n"
            f"• Uso: `{cpu_percent}%`\n"
            f"• Núcleos: `{cpu_cores}`\n\n"
            
            "💾 *MEMORIA:*\n"
            f"• Uso: `{memory.percent}%`\n"
            f"• Total: `{bytes_to_gb(memory.total)} GB`\n\n"
            
            "💽 *DISCO:*\n"
            f"• Uso: `{disk.percent}%`\n"
            f"• Total: `{bytes_to_gb(disk.total)} GB`\n\n"
            
            "📥 *YOUTUBE:*\n"
            f"• Estado: `{'✅' if YOUTUBE_AVAILABLE else '❌'}`\n"
            f"• Descargas: `{download_stats.get('total_downloads', 0)}`\n"
            f"• Espacio: `{download_stats.get('total_size_mb', 0)} MB`\n\n"
            
            "🌐 *RED:*\n"
            f"• Enviados: `{bytes_to_mb(net_io.bytes_sent)} MB`\n"
            f"• Recibidos: `{bytes_to_mb(net_io.bytes_recv)} MB`\n\n"
            
            "📊 *BOT:*\n"
            f"• Memoria: `{bytes_to_mb(process_memory.rss)} MB`\n"
            f"• Keep-alives: `{activity_counter}`\n"
            f"• Uptime: `{str(bot_uptime).split('.')[0]}`\n"
            f"• Hora: `{current_time.strftime('%H:%M:%S')}`\n\n"
            
            "✅ *SISTEMA ESTABLE*"
        )
        
        return info_message
        
    except Exception as e:
        return f"❌ Error: {str(e)}"

def get_quick_status():
    """Estado rápido del sistema"""
    try:
        cpu_usage = psutil.cpu_percent(interval=0.5)
        memory_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/').percent
        
        download_stats = youtube_downloader.get_download_stats()
        
        status_message = (
            f"⚡ *ESTADO RÁPIDO - {BOT_VERSION}*\n\n"
            f"• CPU: `{cpu_usage}%`\n"
            f"• Memoria: `{memory_usage}%`\n"
            f"• Disco: `{disk_usage}%`\n"
            f"• YouTube: `{'✅' if YOUTUBE_AVAILABLE else '❌'}`\n"
            f"• Descargas: `{download_stats.get('total_downloads', 0)}`\n"
            f"• Keep-alives: `{activity_counter}`\n"
            f"• Hora: `{datetime.datetime.now().strftime('%H:%M:%S')}`\n\n"
            "✅ *Sistema funcionando*"
        )
        
        return status_message
    except Exception as e:
        return f"❌ Error: {str(e)}"

def handle_youtube_download(chat_id, url, format_type='mp4'):
    """Manejar descarga de YouTube"""
    try:
        if not YOUTUBE_AVAILABLE:
            send_telegram_message(chat_id, "❌ *YouTube no disponible*")
            return
        
        send_telegram_message(chat_id, "🔄 *Procesando descarga...*")
        
        result = youtube_downloader.download_video(url, format_type)
        
        if result['success']:
            if result.get('skipped'):
                message = (
                    f"⏭️ *Video Ya Descargado*\n\n"
                    f"📹 *Título:* {result['video_info']['title']}\n"
                    f"👤 *Canal:* {result['video_info']['uploader']}\n"
                    f"⏱️ *Duración:* {result['video_info']['duration']}s\n\n"
                    f"✅ *Ya estaba descargado*"
                )
            else:
                downloaded_file = result['downloaded_file']
                message = (
                    f"✅ *Descarga Exitosa*\n\n"
                    f"📹 *Título:* {result['video_info']['title']}\n"
                    f"👤 *Canal:* {result['video_info']['uploader']}\n"
                    f"📦 *Archivo:* `{downloaded_file['filename']}`\n"
                    f"💾 *Tamaño:* {downloaded_file['size_mb']} MB\n"
                    f"🎬 *Formato:* {result['format'].upper()}\n"
                    f"⏱️ *Duración:* {result['video_info']['duration']}s\n\n"
                    f"💾 *Guardado en:* `/tmp/youtube_downloads/`"
                )
        else:
            message = f"❌ *Error:* {result['error']}"
        
        send_telegram_message(chat_id, message)
        
    except Exception as e:
        error_msg = f"❌ *Error procesando:* {str(e)}"
        send_telegram_message(chat_id, error_msg)

def handle_telegram_message(chat_id, message_text):
    """Procesar mensajes de Telegram"""
    global activity_counter
    
    logger.info(f"📩 Mensaje: '{message_text}' de {chat_id}")
    
    # Incrementar contador
    activity_counter += 1
    
    if message_text == "/start":
        welcome_message = (
            f"🤖 *Bot YouTube Telegram*\n"
            f"*Versión:* `{BOT_VERSION}`\n\n"
            
            "📋 *COMANDOS:*\n"
            "• `/info` - Información completa\n"
            "• `/status` - Estado rápido\n"
            "• `/stats` - Estadísticas\n"
            "• `/yt_download URL` - Descargar video\n"
            "• `/yt_mp3 URL` - Descargar audio\n"
            "• `/yt_stats` - Stats descargas\n"
            "• `/alive` - Test conexión\n\n"
            
            "⚠️ *USO EDUCATIVO Y PERSONAL*"
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
        download_stats = youtube_downloader.get_download_stats()
        
        stats_message = (
            f"📊 *ESTADÍSTICAS - {BOT_VERSION}*\n\n"
            f"• Keep-alives: `{activity_counter}`\n"
            f"• Tiempo activo: `{str(uptime).split('.')[0]}`\n"
            f"• Descargas: `{download_stats.get('total_downloads', 0)}`\n"
            f"• Espacio: `{download_stats.get('total_size_mb', 0)} MB`\n"
            f"• Iniciado: `{start_time.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"• Última actividad: `{datetime.datetime.now().strftime('%H:%M:%S')}`\n\n"
            "🔴 *Keep-alive activo*"
        )
        send_telegram_message(chat_id, stats_message)
    
    elif message_text.startswith('/yt_download '):
        url = message_text.replace('/yt_download ', '').strip()
        if url:
            handle_youtube_download(chat_id, url, 'mp4')
        else:
            send_telegram_message(chat_id, "❌ *Uso:* `/yt_download URL`")
    
    elif message_text.startswith('/yt_mp3 '):
        url = message_text.replace('/yt_mp3 ', '').strip()
        if url:
            handle_youtube_download(chat_id, url, 'mp3')
        else:
            send_telegram_message(chat_id, "❌ *Uso:* `/yt_mp3 URL`")
    
    elif message_text == "/yt_stats":
        download_stats = youtube_downloader.get_download_stats()
        stats_message = (
            f"📊 *ESTADÍSTICAS YOUTUBE*\n\n"
            f"• Total descargas: `{download_stats.get('total_downloads', 0)}`\n"
            f"• Videos únicos: `{download_stats.get('downloaded_videos_count', 0)}`\n"
            f"• Espacio usado: `{download_stats.get('total_size_mb', 0)} MB`\n\n"
            "💡 *Comandos:*\n"
            "• `/yt_download URL` - Video MP4\n"
            "• `/yt_mp3 URL` - Audio MP3"
        )
        send_telegram_message(chat_id, stats_message)
        
    elif message_text == "/alive":
        send_telegram_message(chat_id, "💓 ¡BOT ACTIVO Y RESPONDIENDO! ✅")
        
    else:
        help_message = (
            "❌ Comando no reconocido\n\n"
            "✅ *Comandos:*\n"
            "• `/info` - Info sistema\n"
            "• `/status` - Estado rápido\n"
            "• `/stats` - Estadísticas\n"
            "• `/yt_download URL` - Descargar video\n"
            "• `/yt_mp3 URL` - Descargar audio\n"
            "• `/yt_stats` - Stats descargas\n"
            "• `/alive` - Test conexión\n\n"
            f"*Versión:* `{BOT_VERSION}`"
        )
        send_telegram_message(chat_id, help_message)

def telegram_polling_loop():
    """Bucle principal de Telegram"""
    logger.info("🚀 Iniciando polling de Telegram...")
    
    offset = None
    error_count = 0
    
    while True:
        try:
            # Obtener mensajes
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
                    
                    if updates:
                        logger.info(f"📥 {len(updates)} mensaje(s) nuevo(s)")
                        
                        for update in updates:
                            if "message" in update:
                                chat_id = update["message"]["chat"]["id"]
                                text = update["message"].get("text", "").strip()
                                handle_telegram_message(chat_id, text)
                            
                            # Actualizar offset
                            offset = update["update_id"] + 1
                    
                    # Resetear contador de errores
                    error_count = 0
                    
                else:
                    logger.error(f"❌ Error API Telegram: {data}")
                    error_count += 1
            else:
                logger.error(f"❌ Error HTTP {response.status_code}")
                error_count += 1
            
            # Manejo de errores consecutivos
            if error_count >= 3:
                logger.warning("⚠️ Muchos errores, esperando 30s...")
                time.sleep(30)
            else:
                time.sleep(2)
                
        except requests.exceptions.Timeout:
            logger.warning("⏰ Timeout en polling")
            continue
            
        except requests.exceptions.ConnectionError:
            logger.error("🔌 Error de conexión, reintentando en 15s...")
            time.sleep(15)
            
        except Exception as e:
            logger.error(f"💥 Error inesperado: {e}")
            time.sleep(10)

def main():
    """Función principal"""
    try:
        logger.info(f"🚀 INICIANDO BOT - {BOT_VERSION}")
        logger.info(f"📅 Inicio: {datetime.datetime.now()}")
        
        # Verificar token
        if not TOKEN:
            logger.error("❌ ERROR: TELEGRAM_TOKEN no configurado")
            logger.error("💡 Configura la variable en Choreo")
            return
        
        logger.info("✅ Token configurado")
        
        # Verificar dependencias
        try:
            import yt_dlp
            import psutil
            logger.info("✅ Dependencias cargadas")
        except ImportError as e:
            logger.error(f"❌ Dependencias faltantes: {e}")
            return
        
        logger.info("✅ Bot inicializado")
        
        # Iniciar keep-alive
        keep_alive_thread = threading.Thread(target=aggressive_keep_alive, daemon=True)
        keep_alive_thread.start()
        logger.info("🔴 Keep-alive activado")
        
        # Iniciar polling
        telegram_polling_loop()
        
    except Exception as e:
        logger.error(f"💥 ERROR CRÍTICO: {e}")
        time.sleep(60)

if __name__ == "__main__":
    main()
