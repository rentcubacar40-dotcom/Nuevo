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

# ⚡ CONFIGURACIÓN AVANZADA DE LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%m/%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 🔥 VERSIÓN Y CONFIGURACIÓN
BOT_VERSION = "ULTRA_ANTI_BLOCK_" + datetime.datetime.now().strftime("%m%d%H%M")
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}"

# 📊 CONTADORES DE ACTIVIDAD
activity_counter = 0
start_time = datetime.datetime.now()

# 🔧 VERIFICAR YOUTUBE DISPONIBLE
YOUTUBE_AVAILABLE = False
try:
    import yt_dlp
    YOUTUBE_AVAILABLE = True
    logger.info("✅ YouTube Downloader disponible")
except ImportError as e:
    logger.warning(f"⚠️ YouTube Downloader NO disponible: {e}")

class YouTubeDownloader:
    def __init__(self):
        if not YOUTUBE_AVAILABLE:
            logger.error("❌ YouTube Downloader no disponible - yt-dlp no instalado")
            return
            
        self.downloaded_videos = set()
        self.load_downloaded_list()
        self.setup_directories()
        
        # 🛡️ CONFIGURACIÓN AVANZADA ANTI-DETECCIÓN
        self.ydl_opts = {
            'outtmpl': '/tmp/youtube_downloads/%(title).100s.%(ext)s',
            'restrictfilenames': True,
            'nooverwrites': True,
            'writethumbnail': False,
            
            # ⚡ CONFIGURACIÓN DE DESEMPEÑO
            'extract_flat': False,
            'socket_timeout': 45,
            'retries': 15,
            'fragment_retries': 15,
            'skip_unavailable_fragments': True,
            'ignoreerrors': False,
            'no_warnings': False,
            'quiet': True,
            'no_check_certificate': True,
            'prefer_ffmpeg': True,
            
            # 🌍 CONFIGURACIÓN GEOGRÁFICA
            'geo_bypass': True,
            'geo_bypass_country': random.choice(['US', 'GB', 'CA', 'AU', 'DE', 'FR']),
            'geo_bypass_ip_block': None,
            
            # 📊 CONFIGURACIÓN DE RED AVANZADA
            'http_chunk_size': 10485760,
            'continuedl': True,
            'noprogress': True,
            'consoletitle': False,
            'throttledratelimit': 10485760,
            
            # 🔒 CONFIGURACIÓN DE SEGURIDAD
            'allow_unplayable_formats': False,
            'ignore_no_formats_error': False,
            'wait_for_video': (10, 120),
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['configs', 'webpage'],
                }
            },
            
            # 🕵️ CONFIGURACIÓN DE USER-AGENT (se rotará dinámicamente)
            'http_headers': self._get_rotated_headers()
        }
        
        logger.info("✅ YouTube Downloader inicializado con configuración ANTI-BLOQUEO")
    
    def _get_rotated_headers(self):
        """🔀 Obtener headers rotados aleatoriamente"""
        user_agents = [
            # Chrome Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            
            # Chrome Mac
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            
            # Firefox
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
            
            # Safari
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            
            # Edge
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        ]
        
        selected_ua = random.choice(user_agents)
        
        return {
            'User-Agent': selected_ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': random.choice(['en-US,en;q=0.9', 'es-ES,es;q=0.8', 'fr-FR,fr;q=0.7', 'de-DE,de;q=0.8']),
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
            'DNT': random.choice(['1', '0']),
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
        }
    
    def _rotate_download_strategy(self, strategy_index):
        """🔄 Rotar estrategia de descarga"""
        strategies = [
            # Estrategia 1: Calidad media + codec específico
            {
                'video': 'best[height<=720][vcodec^=avc1]/best[height<=480]/best[ext=mp4]/best',
                'audio': 'bestaudio/best',
                'description': '🎯 720p/480p con codec AVC'
            },
            # Estrategia 2: Enfoque mobile
            {
                'video': 'best[height<=360][vcodec^=avc1]/best[height<=240]/worst',
                'audio': 'bestaudio/best',
                'description': '📱 360p/240p (compatible mobile)'
            },
            # Estrategia 3: Enfoque universal
            {
                'video': 'best[ext=mp4]/best[ext=webm]/best',
                'audio': 'bestaudio/best',
                'description': '🌐 Formato universal MP4/WEBM'
            },
            # Estrategia 4: Enfoque conservador
            {
                'video': 'worst[ext=mp4]/worst',
                'audio': 'worstaudio/best',
                'description': '⚡ Calidad mínima (máxima compatibilidad)'
            },
            # Estrategia 5: Enfoque específico YouTube
            {
                'video': 'best[height<=480]/best[height<=360]/best[height<=240]',
                'audio': 'bestaudio/best',
                'description': '🎬 Específico YouTube (480p/360p)'
            }
        ]
        
        return strategies[strategy_index % len(strategies)]
    
    def setup_directories(self):
        """Crear directorios necesarios"""
        try:
            os.makedirs('/tmp/youtube_downloads', exist_ok=True)
            logger.info("✅ Directorios de descarga creados")
        except Exception as e:
            logger.warning(f"⚠️ Error creando directorios: {e}")
    
    def load_downloaded_list(self):
        """Cargar lista de videos ya descargados"""
        try:
            if os.path.exists('/tmp/downloaded_videos.json'):
                with open('/tmp/downloaded_videos.json', 'r') as f:
                    data = json.load(f)
                    self.downloaded_videos = set(data.get('videos', []))
                logger.info(f"✅ Lista de descargas cargada: {len(self.downloaded_videos)} videos")
        except Exception as e:
            logger.warning(f"❌ Error cargando lista de descargas: {e}")
    
    def save_downloaded_list(self):
        """Guardar lista de videos descargados"""
        try:
            with open('/tmp/downloaded_videos.json', 'w') as f:
                json.dump({'videos': list(self.downloaded_videos)}, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Error guardando lista de descargas: {e}")
    
    def get_video_id(self, url: str) -> str:
        """Generar ID único para el video"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def is_valid_youtube_url(self, url: str) -> bool:
        """Validar si es una URL de YouTube válida"""
        try:
            parsed = urlparse(url)
            return any(domain in parsed.netloc for domain in ['youtube.com', 'youtu.be'])
        except:
            return False
    
    def get_video_info(self, url: str) -> dict:
        """Obtener información del video con rotación de estrategias"""
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                # Rotar configuración para cada intento
                info_opts = {
                    'quiet': True,
                    'no_warnings': False,
                    'ignoreerrors': False,
                    'extract_flat': False,
                    'socket_timeout': 30,
                    'retries': 5,
                    'http_headers': self._get_rotated_headers(),
                }
                
                with yt_dlp.YoutubeDL(info_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    return {
                        'success': True,
                        'title': info.get('title', ''),
                        'duration': info.get('duration', 0),
                        'uploader': info.get('uploader', ''),
                        'view_count': info.get('view_count', 0),
                        'thumbnail': info.get('thumbnail', ''),
                        'webpage_url': info.get('webpage_url', ''),
                        'timestamp': datetime.datetime.now().isoformat(),
                        'attempt': attempt + 1
                    }
                    
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"⚠️ Intento {attempt + 1} de info falló: {error_msg}")
                
                if attempt < max_attempts - 1:
                    # Espera exponencial con jitter
                    wait_time = (2 ** attempt) + random.uniform(0.5, 1.5)
                    logger.info(f"⏳ Reintentando info en {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    # Último intento falló
                    if "Sign in" in error_msg or "bot" in error_msg.lower():
                        return {'success': False, 'error': 'YouTube ha bloqueado el acceso. Intenta con otro video.'}
                    elif "Private video" in error_msg:
                        return {'success': False, 'error': 'Video privado - No se puede acceder'}
                    elif "Video unavailable" in error_msg:
                        return {'success': False, 'error': 'Video no disponible'}
                    else:
                        return {'success': False, 'error': f'Error obteniendo información: {error_msg}'}
        
        return {'success': False, 'error': 'No se pudo obtener información después de múltiples intentos'}
    
    def download_video(self, url: str, format_type: str = 'mp4') -> dict:
        """🎯 DESCARGA AVANZADA CON MÚLTIPLES ESTRATEGIAS"""
        try:
            if not YOUTUBE_AVAILABLE:
                return {'success': False, 'error': 'YouTube Downloader no disponible'}
                
            if not self.is_valid_youtube_url(url):
                return {'success': False, 'error': 'URL de YouTube no válida'}
            
            video_id = self.get_video_id(url)
            if video_id in self.downloaded_videos:
                return {'success': True, 'skipped': True, 'reason': 'Ya descargado anteriormente'}
            
            # Obtener información primero
            logger.info(f"🔍 Obteniendo información del video...")
            info = self.get_video_info(url)
            if not info['success']:
                return info
            
            # 🎯 ESTRATEGIA DE DESCARGA CON MÚLTIPLES CAPAS
            max_strategies = 5
            downloaded_file = None
            
            for strategy_index in range(max_strategies):
                try:
                    strategy = self._rotate_download_strategy(strategy_index)
                    logger.info(f"🎯 Estrategia {strategy_index + 1}: {strategy['description']}")
                    
                    # Configurar opciones de descarga para esta estrategia
                    download_opts = self.ydl_opts.copy()
                    download_opts['http_headers'] = self._get_rotated_headers()
                    
                    # Aplicar delays aleatorios entre estrategias
                    if strategy_index > 0:
                        delay = random.uniform(3, 8)
                        logger.info(f"⏳ Esperando {delay:.1f}s antes de siguiente estrategia...")
                        time.sleep(delay)
                    
                    if format_type == 'mp3':
                        download_opts.update({
                            'format': strategy['audio'],
                            'postprocessors': [{
                                'key': 'FFmpegExtractAudio',
                                'preferredcodec': 'mp3',
                                'preferredquality': '192',
                            }],
                            'extractaudio': True,
                            'audioformat': 'mp3',
                        })
                    else:
                        download_opts.update({
                            'format': strategy['video'],
                            'merge_output_format': 'mp4',
                        })
                    
                    # 🔧 CONFIGURACIÓN DE REINTENTOS INTELIGENTES
                    download_opts.update({
                        'retry_sleep_functions': {
                            'http': lambda n: random.uniform(2, 5) + (n * random.uniform(1, 3)),
                            'fragment': lambda n: random.uniform(1, 3) + (n * random.uniform(0.5, 2)),
                        },
                        'sleep_interval': random.randint(1, 4),
                    })
                    
                    # EJECUTAR DESCARGA
                    with yt_dlp.YoutubeDL(download_opts) as ydl:
                        ydl.download([url])
                    
                    # 🔍 BUSCAR ARCHIVO DESCARGADO
                    download_dir = '/tmp/youtube_downloads'
                    if os.path.exists(download_dir):
                        for filename in os.listdir(download_dir):
                            filepath = os.path.join(download_dir, filename)
                            if os.path.isfile(filepath):
                                file_size = os.path.getsize(filepath)
                                if file_size > 1024:  # Al menos 1KB
                                    downloaded_file = {
                                        'filename': filename,
                                        'size_mb': round(file_size / (1024 * 1024), 2),
                                        'path': filepath,
                                        'strategy_used': strategy['description']
                                    }
                                    break
                    
                    if downloaded_file:
                        logger.info(f"✅ Estrategia {strategy_index + 1} exitosa!")
                        break
                    else:
                        logger.warning(f"⚠️ Estrategia {strategy_index + 1} no produjo archivo")
                        
                except yt_dlp.DownloadError as e:
                    error_msg = str(e)
                    logger.warning(f"⚠️ Estrategia {strategy_index + 1} falló: {error_msg}")
                    
                    if strategy_index == max_strategies - 1:
                        # Última estrategia falló
                        if "Sign in" in error_msg or "bot" in error_msg.lower():
                            return {'success': False, 'error': 'YouTube ha bloqueado todas las estrategias. Video muy protegido.'}
                        else:
                            return {'success': False, 'error': f'Todas las estrategias fallaron: {error_msg}'}
                
                except Exception as e:
                    logger.warning(f"⚠️ Error en estrategia {strategy_index + 1}: {str(e)}")
                    if strategy_index == max_strategies - 1:
                        return {'success': False, 'error': f'Error crítico en descarga: {str(e)}'}
            
            if not downloaded_file:
                return {'success': False, 'error': 'No se pudo descargar el archivo después de todas las estrategias'}
            
            # ✅ MARCAR COMO DESCARGADO
            self.downloaded_videos.add(video_id)
            self.save_downloaded_list()
            
            logger.info(f"✅ Descarga completada con estrategia: {downloaded_file['strategy_used']}")
            
            return {
                'success': True,
                'downloaded': True,
                'video_info': info,
                'downloaded_file': downloaded_file,
                'format': format_type,
                'strategy_used': downloaded_file['strategy_used'],
                'timestamp': datetime.datetime.now().isoformat()
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"💥 Error crítico en download_video: {error_msg}")
            
            if "Sign in" in error_msg or "bot" in error_msg.lower():
                return {'success': False, 'error': '🔒 YouTube ha detectado actividad automática. Video muy protegido.'}
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
                    'downloaded_videos_count': len(self.downloaded_videos),
                    'download_path': download_dir,
                    'youtube_available': YOUTUBE_AVAILABLE
                }
                
            files = [f for f in os.listdir(download_dir) if os.path.isfile(os.path.join(download_dir, f))]
            total_size = sum(
                os.path.getsize(os.path.join(download_dir, f)) 
                for f in files
            ) / (1024 * 1024)  # MB
            
            return {
                'total_downloads': len(files),
                'total_size_mb': round(total_size, 2),
                'downloaded_videos_count': len(self.downloaded_videos),
                'download_path': download_dir,
                'youtube_available': YOUTUBE_AVAILABLE
            }
        except Exception as e:
            logger.error(f"❌ Error obteniendo stats de descargas: {e}")
            return {'error': str(e)}

# 🔥 INICIALIZAR DESCARGADOR DE YOUTUBE
youtube_downloader = YouTubeDownloader()

# ... (el resto de las funciones se mantienen igual que en el código anterior)
# [Mantener todas las otras funciones: bytes_to_mb, bytes_to_gb, aggressive_keep_alive, 
# send_telegram_message, get_comprehensive_system_info, get_quick_status, etc.]

def handle_youtube_download(chat_id, url, format_type='mp4'):
    """📥 MANEJAR DESCARGA CON ESTRATEGIAS AVANZADAS"""
    try:
        if not YOUTUBE_AVAILABLE:
            send_telegram_message(
                chat_id, 
                "❌ *YouTube Downloader NO disponible*\n\n"
                "El módulo yt-dlp no está instalado correctamente."
            )
            return
        
        # Mensaje de inicio mejorado
        start_message = (
            "🛡️ *INICIANDO MODO ANTI-BLOQUEO*\n\n"
            "🎯 *Estrategias activadas:*\n"
            "• 🔄 Rotación de User-Agents\n"
            "• 🌍 Geolocalización variable\n" 
            "• 📊 Múltiples calidades\n"
            "• ⏳ Delays inteligentes\n"
            "• 🎯 5 estrategias diferentes\n\n"
            "⏳ _Procesando... Esto puede tomar 1-2 minutos_"
        )
        send_telegram_message(chat_id, start_message)
        
        # Descargar video
        result = youtube_downloader.download_video(url, format_type)
        
        if result['success']:
            if result.get('skipped'):
                message = (
                    f"⏭️ *Video Ya Descargado*\n\n"
                    f"📹 *Título:* {result['video_info']['title']}\n"
                    f"👤 *Canal:* {result['video_info']['uploader']}\n"
                    f"⏱️ *Duración:* {result['video_info']['duration']} segundos\n\n"
                    f"✅ *Este video ya fue descargado anteriormente*"
                )
            else:
                downloaded_file = result['downloaded_file']
                message = (
                    f"🎉 *¡DESCARGA EXITOSA!*\n\n"
                    f"📹 *Título:* {result['video_info']['title']}\n"
                    f"👤 *Canal:* {result['video_info']['uploader']}\n"
                    f"📦 *Archivo:* `{downloaded_file['filename']}`\n"
                    f"💾 *Tamaño:* {downloaded_file['size_mb']} MB\n"
                    f"🎬 *Formato:* {result['format'].upper()}\n"
                    f"🛡️ *Estrategia:* {result['strategy_used']}\n"
                    f"⏱️ *Duración:* {result['video_info']['duration']} segundos\n\n"
                    f"✅ *Sistema anti-bloqueo funcionó correctamente*"
                )
        else:
            error_msg = result['error']
            if any(keyword in error_msg.lower() for keyword in ['bloqueado', 'sign in', 'bot', 'detectado', 'protegido']):
                message = (
                    f"🛡️ *SISTEMA ANTI-BLOQUEO SUPERADO*\n\n"
                    f"*Situación:* YouTube ha bloqueado todas las estrategias\n\n"
                    f"📊 *Estrategias probadas:*\n"
                    f"• 🔄 5 diferentes User-Agents\n"
                    f"• 🌍 6 ubicaciones geográficas\n" 
                    f"• 📊 Múltiples calidades de video\n"
                    f"• ⏳ Delays y tiempos variables\n\n"
                    f"💡 *Recomendaciones avanzadas:*\n"
                    f"• 🕐 Intenta en 1-2 horas\n"
                    f"• 🌐 Usa una VPN diferente\n"
                    f"• 📹 Prueba videos menos populares\n"
                    f"• 🔄 Contacta al administrador\n\n"
                    f"⚠️ *Este video tiene protección avanzada*"
                )
            else:
                message = f"❌ *Error en la descarga:* {error_msg}"
        
        send_telegram_message(chat_id, message)
        
    except Exception as e:
        error_msg = f"❌ *Error procesando descarga:* {str(e)}"
        logger.error(f"💥 Error en handle_youtube_download: {e}")
        send_telegram_message(chat_id, error_msg)

# ... (mantener el resto del código igual)

def handle_telegram_message(chat_id, message_text):
    """📨 PROCESAR MENSAJES DE TELEGRAM"""
    global activity_counter
    
    logger.info(f"📩 Mensaje recibido: '{message_text}' de {chat_id}")
    
    # 🔄 INCREMENTAR CONTADOR DE ACTIVIDAD
    activity_counter += 1
    
    if message_text == "/start":
        youtube_status = "✅ MODO ANTI-BLOQUEO" if YOUTUBE_AVAILABLE else "❌ NO DISPONIBLE"
        
        welcome_message = (
            f"🤖 *BOT CHOREO - MODO ANTI-BLOQUEO*\n"
            f"*Versión:* `{BOT_VERSION}`\n"
            f"*YouTube:* `{youtube_status}`\n\n"
            
            "🛡️ *SISTEMA ANTI-DETECCIÓN ACTIVO:*\n"
            "• 🔄 Rotación de User-Agents\n"
            "• 🌍 Geolocalización variable\n"
            "• 📊 5 estrategias de descarga\n"
            "• ⏳ Delays inteligentes\n"
            "• 🎯 Múltiples calidades\n\n"
            
            "📋 *COMANDOS DISPONIBLES:*\n"
            "• `/info` - Información del servidor\n"
            "• `/status` - Estado rápido\n"
            "• `/stats` - Estadísticas del bot\n"
            "• `/yt_download URL` - Descargar video MP4\n"
            "• `/yt_mp3 URL` - Descargar audio MP3\n"
            "• `/yt_stats` - Estadísticas de descargas\n"
            "• `/alive` - Test de respuesta\n\n"
            
            "⚠️ *NOTA:* Sistema optimizado para videos con protección media"
        )
        send_telegram_message(chat_id, welcome_message)
    
    # ... (mantener el resto de comandos igual)

# ... (mantener main() y el resto del código igual)

def main():
    """🎯 FUNCIÓN PRINCIPAL"""
    try:
        logger.info(f"🚀 INICIANDO BOT ANTI-BLOQUEO - {BOT_VERSION}")
        logger.info(f"📅 Hora de inicio: {datetime.datetime.now()}")
        
        # 🚫 VERIFICAR TOKEN
        if not TOKEN:
            logger.error("❌ ERROR: TELEGRAM_TOKEN no configurado")
            logger.error("💡 Configura la variable de entorno en Choreo")
            return
        
        logger.info("✅ Token de Telegram configurado correctamente")
        
        # ✅ VERIFICAR DEPENDENCIAS
        try:
            import yt_dlp
            import psutil
            logger.info("✅ Todas las dependencias cargadas correctamente")
        except ImportError as e:
            logger.error(f"❌ Error importando dependencias: {e}")
            logger.error("💡 Verifica que requirements.txt esté correcto")
        
        logger.info("✅ Bot ANTI-BLOQUEO inicializado correctamente")
        
        # 🔥 INICIAR KEEP-ALIVE
        keep_alive_thread = threading.Thread(target=aggressive_keep_alive, daemon=True)
        keep_alive_thread.start()
        logger.info("🔴 KEEP-ALIVE ACTIVADO - Cada 5 minutos")
        
        # 🔄 INICIAR POLLING DE TELEGRAM
        telegram_polling_loop()
        
    except Exception as e:
        logger.error(f"💥 ERROR CRÍTICO: {e}")
        time.sleep(60)

if __name__ == "__main__":
    main()
