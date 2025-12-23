import os
import subprocess
import json
import re
import time
import logging
import threading
import uuid
import asyncio
from collections import deque
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode, MessageMediaType

# ========== CONFIGURACIÓN DEL BOT ==========
# CREDENCIALES DIRECTAMENTE EN EL CÓDIGO (SIN .env)
API_ID = 20534584  # Sin comillas, es número
API_HASH = "6d5b13261d2c92a9a00afc1fd613b9df"
BOT_TOKEN = "8562042457:AAGA__pfWDMVfdslzqwnoFl4yLrAre-HJ5I"
ADMIN_USER_ID = "7363341763"

# Configuración de compresión
COMPRESSION_SETTINGS = {
    "target_size_mb": 50,
    "resolution": "1280x720",
    "crf": 23,
    "preset": "medium"
}

# Límites del sistema
MAX_QUEUE_SIZE = 10
MAX_CONCURRENT_PROCESSES = 2
MAX_FILE_SIZE = 4000 * 1024 * 1024  # 500MB

# Directorio de trabajo
WORK_DIR = "/tmp/video_bot"
os.makedirs(WORK_DIR, exist_ok=True)

# Tipos MIME de video aceptados
VIDEO_MIME_TYPES = [
    "video/mp4", "video/avi", "video/mkv", "video/mov", "video/wmv",
    "video/flv", "video/webm", "video/mpeg", "video/quicktime", "video/x-msvideo"
]

# ========== CONFIGURACIÓN DE LOGGING ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========== SISTEMA DE COLA ==========
video_queue = deque()
active_processes = {}
queue_lock = threading.Lock()
process_lock = threading.Lock()

# ========== SERVIDOR WEB PARA RENDER ==========
from flask import Flask, jsonify

app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Video Compression Bot",
        "message": "Bot funcionando en Render",
        "queue_size": len(video_queue),
        "active_processes": len(active_processes)
    })

@app_flask.route('/health')
def health():
    with queue_lock:
        queue_size = len(video_queue)
    with process_lock:
        active_count = len(active_processes)
    
    return jsonify({
        "status": "healthy",
        "queue_size": queue_size,
        "active_processes": active_count,
        "timestamp": time.time(),
        "uptime": time.time() - app_start_time if 'app_start_time' in globals() else 0
    })

@app_flask.route('/queue')
def queue_status():
    with queue_lock:
        queue_list = []
        for i, (task_id, chat_id, msg_id, path, name) in enumerate(list(video_queue)[:20], 1):
            file_exists = os.path.exists(path)
            size = os.path.getsize(path) if file_exists else 0
            queue_list.append({
                "position": i,
                "task_id": task_id,
                "user_id": chat_id,
                "filename": name,
                "size": size,
                "file_exists": file_exists
            })
    
    return jsonify({
        "total_in_queue": len(video_queue),
        "queue": queue_list,
        "active_processes": len(active_processes)
    })

def run_flask():
    """Ejecuta Flask en un hilo separado"""
    port = int(os.environ.get('PORT', 10000))
    app_flask.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ========== FUNCIONES DE PROGRESO ==========
def create_progress_bar(percentage, length=15):
    """Crea una barra de progreso visual"""
    percentage = max(0, min(100, percentage))
    filled = int(length * percentage / 100)
    bar = "█" * filled + "░" * (length - filled)
    return bar

def format_time(seconds):
    """Formatea segundos a tiempo legible"""
    if seconds < 60:
        return f"{int(seconds)} segundos"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes} min {secs} seg"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours} horas {minutes} min"

def format_size(bytes_size):
    """Formatea bytes a tamaño legible"""
    if bytes_size >= 1024 * 1024 * 1024:
        return f"{bytes_size/(1024*1024*1024):.1f} GB"
    elif bytes_size >= 1024 * 1024:
        return f"{bytes_size/(1024*1024):.1f} MB"
    elif bytes_size >= 1024:
        return f"{bytes_size/1024:.1f} KB"
    else:
        return f"{bytes_size} B"

# ========== FUNCIONES DE VIDEO ==========
def get_video_info(video_path):
    """Obtiene información del video usando ffprobe"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout al obtener info del video: {video_path}")
        return None
    except Exception as e:
        logger.error(f"Error obteniendo info del video: {e}")
        return None

def calculate_bitrate(target_size_mb, duration_seconds):
    """Calcula el bitrate necesario para alcanzar el tamaño objetivo"""
    if duration_seconds <= 0:
        return 1000  # bitrate por defecto
    
    # Convertir tamaño objetivo a kilobits (1 MB = 8000 kilobits)
    target_kbits = target_size_mb * 8000
    
    # Calcular bitrate (kbps)
    bitrate = int(target_kbits / duration_seconds)
    
    # Ajustar límites (entre 500kbps y 4000kbps)
    bitrate = max(500, min(bitrate, 4000))
    
    return bitrate

def parse_ffmpeg_time(time_str):
    """Parsea el tiempo de la salida de ffmpeg"""
    try:
        if 'time=' in time_str:
            time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.\d{2}', time_str)
            if time_match:
                hours = int(time_match.group(1))
                minutes = int(time_match.group(2))
                seconds = int(time_match.group(3))
                return hours * 3600 + minutes * 60 + seconds
        return None
    except Exception as e:
        logger.debug(f"Error parseando tiempo: {e}")
        return None

def is_video_document(message: Message):
    """Verifica si un documento es un video"""
    if not message.document:
        return False
    
    # Verificar por extensión de archivo
    if hasattr(message.document, 'file_name') and message.document.file_name:
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', 
                          '.flv', '.webm', '.m4v', '.3gp', '.ogg']
        file_ext = os.path.splitext(message.document.file_name.lower())[1]
        if file_ext in video_extensions:
            return True
    
    # Verificar por tipo MIME si está disponible
    if hasattr(message.document, 'mime_type') and message.document.mime_type:
        if any(video_type in message.document.mime_type.lower() for video_type in ['video', 'mp4', 'avi', 'mkv', 'mov']):
            return True
    
    # Verificar por tamaño (si es muy grande, probablemente no es un video pequeño)
    if hasattr(message.document, 'file_size'):
        if message.document.file_size > 10 * 1024 * 1024:  # Más de 10MB
            return True
    
    return False

# ========== PROCESADOR DE VIDEOS ==========
class VideoProcessor(threading.Thread):
    """Hilo para procesar videos de la cola"""
    
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.running = True
        self.current_task_id = None
        
    def run(self):
        """Procesa videos de la cola continuamente"""
        logger.info("🔄 Procesador de videos iniciado")
        
        while self.running:
            try:
                # Obtener siguiente tarea de la cola
                task = None
                with queue_lock:
                    if video_queue:
                        task = video_queue.popleft()
                        self.current_task_id = task[0]
                
                if task:
                    task_id, chat_id, message_id, file_path, original_name = task
                    logger.info(f"📥 Procesando video: {original_name} (ID: {task_id})")
                    self.process_video(task_id, chat_id, message_id, file_path, original_name)
                else:
                    # No hay tareas, esperar
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"❌ Error en procesador principal: {e}")
                time.sleep(5)
    
    def process_video(self, task_id, chat_id, message_id, file_path, original_name):
        """Procesa un video individual"""
        progress_msg_id = None
        
        try:
            # Verificar que el archivo existe
            if not os.path.exists(file_path):
                logger.error(f"Archivo no encontrado: {file_path}")
                asyncio.run_coroutine_threadsafe(
                    self.send_error_message(chat_id, original_name, "El archivo temporal no se encontró"),
                    asyncio.get_event_loop()
                ).result()
                return
            
            # Agregar a procesos activos
            with process_lock:
                active_processes[task_id] = {
                    'chat_id': chat_id,
                    'start_time': time.time(),
                    'status': 'procesando',
                    'filename': original_name,
                    'progress': 0
                }
            
            # Ruta de salida
            safe_name = re.sub(r'[^\w\-.]', '_', original_name)
            output_name = f"compressed_{task_id}_{safe_name}"
            output_path = os.path.join(WORK_DIR, output_name)
            
            # Enviar mensaje de inicio
            progress_msg = asyncio.run_coroutine_threadsafe(
                self.send_progress_message(chat_id, original_name, 0, 0, task_id),
                asyncio.get_event_loop()
            ).result()
            
            if progress_msg:
                progress_msg_id = progress_msg.id
                with process_lock:
                    if task_id in active_processes:
                        active_processes[task_id]['progress_msg_id'] = progress_msg_id
            
            # Obtener información del video
            logger.info(f"📊 Analizando video: {original_name}")
            video_info = get_video_info(file_path)
            if not video_info:
                raise Exception("No se pudo obtener información del video (ffprobe falló)")
            
            # Extraer duración y tamaño
            duration = 0
            if 'format' in video_info and 'duration' in video_info['format']:
                try:
                    duration = float(video_info['format']['duration'])
                except:
                    duration = 0
            
            original_size = os.path.getsize(file_path)
            
            # Calcular bitrate para compresión
            bitrate = calculate_bitrate(COMPRESSION_SETTINGS["target_size_mb"], duration)
            logger.info(f"🎯 Bitrate calculado: {bitrate}kbps para {duration:.1f}s de video")
            
            # Construir comando ffmpeg
            cmd = [
                'ffmpeg',
                '-i', file_path,
                '-vf', f'scale={COMPRESSION_SETTINGS["resolution"]}',
                '-c:v', 'libx264',
                '-preset', COMPRESSION_SETTINGS["preset"],
                '-crf', str(COMPRESSION_SETTINGS["crf"]),
                '-b:v', f'{bitrate}k',
                '-maxrate', f'{bitrate * 1.5}k',
                '-bufsize', f'{bitrate * 2}k',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-threads', '2',
                '-y',  # Sobrescribir si existe
                output_path
            ]
            
            # Ejecutar compresión
            logger.info(f"🎬 Iniciando compresión: {original_name}")
            start_time = time.time()
            process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                universal_newlines=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace'
            )
            
            # Monitorear progreso
            last_update = start_time
            last_percentage = 0
            
            while True:
                line = process.stderr.readline()
                if not line:
                    if process.poll() is not None:
                        break
                    time.sleep(0.1)
                    continue
                
                # Parsear tiempo actual
                current_time = parse_ffmpeg_time(line)
                if current_time and duration > 0:
                    percentage = min(99.9, (current_time / duration) * 100)
                    elapsed = time.time() - start_time
                    
                    # Actualizar cada 3 segundos o si el progreso cambió significativamente
                    if time.time() - last_update >= 3 or abs(percentage - last_percentage) >= 5:
                        with process_lock:
                            if task_id in active_processes:
                                active_processes[task_id]['progress'] = percentage
                                active_processes[task_id]['elapsed'] = elapsed
                        
                        asyncio.run_coroutine_threadsafe(
                            self.send_progress_message(chat_id, original_name, percentage, elapsed, task_id),
                            asyncio.get_event_loop()
                        ).result()
                        
                        last_update = time.time()
                        last_percentage = percentage
            
            # Esperar finalización
            process.wait()
            
            if process.returncode != 0:
                raise Exception(f"FFmpeg falló con código {process.returncode}")
            
            # Verificar archivo de salida
            if not os.path.exists(output_path):
                raise Exception("No se generó el archivo comprimido")
            
            # Obtener tamaño comprimido
            compressed_size = os.path.getsize(output_path)
            saved = original_size - compressed_size
            saved_percent = (saved / original_size * 100) if original_size > 0 else 0
            
            # Actualizar estado
            total_time = time.time() - start_time
            logger.info(f"✅ Compresión exitosa: {original_name} "
                       f"({format_size(original_size)} → {format_size(compressed_size)}, "
                       f"ahorro: {saved_percent:.1f}%, tiempo: {format_time(total_time)})")
            
            # Enviar video comprimido
            asyncio.run_coroutine_threadsafe(
                self.send_compressed_video(chat_id, output_path, original_name, 
                                         original_size, compressed_size, saved_percent, task_id),
                asyncio.get_event_loop()
            ).result()
            
        except Exception as e:
            logger.error(f"❌ Error procesando video {original_name}: {e}")
            try:
                asyncio.run_coroutine_threadsafe(
                    self.send_error_message(chat_id, original_name, str(e), task_id),
                    asyncio.get_event_loop()
                ).result()
            except Exception as err:
                logger.error(f"❌ Error enviando mensaje de error: {err}")
        finally:
            # Limpiar archivos temporales
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"🗑️ Eliminado archivo temporal: {file_path}")
            except Exception as e:
                logger.error(f"Error eliminando archivo temporal {file_path}: {e}")
            
            try:
                if 'output_path' in locals() and os.path.exists(output_path):
                    os.remove(output_path)
                    logger.debug(f"🗑️ Eliminado archivo de salida: {output_path}")
            except Exception as e:
                logger.error(f"Error eliminando archivo de salida: {e}")
            
            # Remover de procesos activos
            with process_lock:
                if task_id in active_processes:
                    del active_processes[task_id]
            
            self.current_task_id = None
            
            # Limpiar mensaje de progreso
            if progress_msg_id:
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.clean_progress_message(chat_id, progress_msg_id),
                        asyncio.get_event_loop()
                    ).result()
                except:
                    pass
    
    async def send_progress_message(self, chat_id, filename, percentage, elapsed, task_id=None):
        """Envía/actualiza mensaje de progreso"""
        try:
            bar = create_progress_bar(percentage)
            time_str = format_time(elapsed)
            
            # Calcular tiempo estimado restante
            remaining = ""
            if percentage > 5:
                total_estimated = elapsed / (percentage / 100)
                remaining_estimated = total_estimated - elapsed
                if remaining_estimated > 0:
                    remaining = f"\n⏳ Restante: {format_time(remaining_estimated)}"
            
            message = (
                f"🎬 **Comprimiendo video...**\n\n"
                f"📁 `{filename[:40]}{'...' if len(filename) > 40 else ''}`\n\n"
                f"{bar} **{percentage:.1f}%**\n\n"
                f"⏱️ Transcurrido: {time_str}"
                f"{remaining}"
            )
            
            # Buscar mensaje de progreso existente
            msg_id = None
            with process_lock:
                if task_id and task_id in active_processes and 'progress_msg_id' in active_processes[task_id]:
                    msg_id = active_processes[task_id]['progress_msg_id']
                else:
                    # Buscar en todos los procesos activos del usuario
                    for pid, info in active_processes.items():
                        if info['chat_id'] == chat_id and 'progress_msg_id' in info:
                            msg_id = info['progress_msg_id']
                            break
            
            if msg_id:
                # Actualizar mensaje existente
                try:
                    await self.app.edit_message_text(
                        chat_id=chat_id,
                        message_id=msg_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return None
                except Exception as e:
                    logger.debug(f"No se pudo editar mensaje {msg_id}: {e}")
                    # Si falla la edición, crear uno nuevo
            
            # Crear nuevo mensaje
            msg = await self.app.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Guardar ID del mensaje
            if msg and task_id:
                with process_lock:
                    if task_id in active_processes:
                        active_processes[task_id]['progress_msg_id'] = msg.id
            
            return msg
            
        except Exception as e:
            logger.error(f"❌ Error enviando progreso: {e}")
            return None
    
    async def send_compressed_video(self, chat_id, video_path, original_name, 
                                   original_size, compressed_size, saved_percent, task_id=None):
        """Envía el video comprimido al usuario"""
        try:
            # Calcular ratio
            ratio = original_size / compressed_size if compressed_size > 0 else 1
            
            # Preparar caption
            caption = (
                f"✅ **Video comprimido exitosamente!**\n\n"
                f"📁 `{original_name[:50]}{'...' if len(original_name) > 50 else ''}`\n\n"
                f"📊 **Resultados:**\n"
                f"• Tamaño original: {format_size(original_size)}\n"
                f"• Tamaño comprimido: {format_size(compressed_size)}\n"
                f"• Espacio ahorrado: {saved_percent:.1f}%\n"
                f"• Ratio de compresión: {ratio:.1f}x\n\n"
                f"⚡ **¡Listo para compartir!**"
            )
            
            # Enviar video
            logger.info(f"📤 Enviando video comprimido a {chat_id}: {original_name}")
            
            await self.app.send_chat_action(chat_id, "upload_video")
            
            # Intentar enviar el video
            try:
                await self.app.send_video(
                    chat_id=chat_id,
                    video=video_path,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    supports_streaming=True
                )
                logger.info(f"✅ Video enviado exitosamente: {original_name}")
            except Exception as send_error:
                # Si falla, enviar mensaje alternativo
                logger.error(f"Error enviando video, enviando enlace alternativo: {send_error}")
                await self.app.send_message(
                    chat_id=chat_id,
                    text=f"✅ **Video comprimido pero demasiado grande para Telegram**\n\n"
                         f"El video fue comprimido exitosamente pero supera el límite de Telegram.\n"
                         f"**Resultados:**\n"
                         f"- Tamaño original: {format_size(original_size)}\n"
                         f"- Tamaño comprimido: {format_size(compressed_size)}\n"
                         f"- Ahorro: {saved_percent:.1f}%\n\n"
                         f"💡 *Sugerencia:* Intenta con un video más corto.",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            # Limpiar mensaje de progreso
            await self.clean_progress_message_by_task(task_id, chat_id)
            
        except Exception as e:
            logger.error(f"❌ Error enviando video: {e}")
            await self.app.send_message(
                chat_id=chat_id,
                text=f"✅ Video comprimido, pero hubo un error al enviarlo: {str(e)[:200]}"
            )
    
    async def send_error_message(self, chat_id, filename, error, task_id=None):
        """Envía mensaje de error"""
        try:
            error_msg = (
                f"❌ **Error al procesar video**\n\n"
                f"📁 `{filename[:50]}{'...' if len(filename) > 50 else ''}`\n\n"
                f"**Error:** {str(error)[:200]}\n\n"
                f"Por favor, intenta con otro video o contacta al administrador."
            )
            
            await self.app.send_message(
                chat_id=chat_id,
                text=error_msg,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Limpiar mensaje de progreso
            await self.clean_progress_message_by_task(task_id, chat_id)
            
        except Exception as e:
            logger.error(f"❌ Error enviando mensaje de error: {e}")
    
    async def clean_progress_message_by_task(self, task_id, chat_id):
        """Limpia el mensaje de progreso usando el task_id"""
        try:
            if not task_id:
                return
                
            with process_lock:
                if task_id in active_processes and 'progress_msg_id' in active_processes[task_id]:
                    msg_id = active_processes[task_id]['progress_msg_id']
                    try:
                        await self.app.delete_messages(chat_id, msg_id)
                        logger.debug(f"🗑️ Mensaje de progreso eliminado: {msg_id}")
                    except Exception as e:
                        logger.debug(f"No se pudo eliminar mensaje {msg_id}: {e}")
        except Exception as e:
            logger.error(f"Error limpiando mensaje de progreso: {e}")
    
    async def clean_progress_message(self, chat_id, msg_id):
        """Limpia un mensaje de progreso específico"""
        try:
            await self.app.delete_messages(chat_id, msg_id)
        except:
            pass
    
    def stop(self):
        """Detiene el procesador"""
        self.running = False
        logger.info("⏹️ Procesador de videos detenido")

# ========== BOT DE TELEGRAM ==========
# Crear cliente de Pyrogram
app = Client(
    "video_compression_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Variables globales
processor = None
app_start_time = None

@app.on_message(filters.command(["start", "help"]))
async def start_command(client, message: Message):
    """Comando de inicio"""
    help_text = (
        "🎬 **Bot de Compresión de Videos**\n\n"
        "Envía cualquier video para comprimirlo automáticamente.\n\n"
        "⚡ **Características:**\n"
        "• Compresión automática con FFmpeg\n"
        "• Barra de progreso en tiempo real\n"
        "• Sistema de cola inteligente\n"
        "• Máximo tamaño por video: 500MB\n"
        "• Formatos soportados: MP4, AVI, MKV, MOV, etc.\n\n"
        "📊 **Estadísticas actuales:**\n"
        f"• 🕒 Uptime: {format_time(time.time() - app_start_time) if app_start_time else 'Iniciando'}\n"
        f"• 📋 En cola: {len(video_queue)}\n"
        f"• 🔄 Procesando: {len(active_processes)}\n"
        f"• 💾 Directorio: {WORK_DIR}\n\n"
        "⚠️ **Nota:** Los videos se procesan en orden de llegada.\n\n"
        "**Comandos disponibles:**\n"
        "/start - Muestra este mensaje\n"
        "/status - Estado del sistema\n"
        "/queue - Ver cola de espera\n"
        "/clean - Limpiar mis archivos en espera\n"
        "/info - Información técnica"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Estado del Sistema", callback_data="status")],
        [InlineKeyboardButton("❓ Cómo usar", callback_data="howto")],
        [InlineKeyboardButton("🛠️ Soporte", url="https://t.me/" + ADMIN_USER_ID)]
    ])
    
    await message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

@app.on_message(filters.command("status"))
async def status_command(client, message: Message):
    """Muestra el estado del sistema"""
    with queue_lock:
        queue_size = len(video_queue)
        queue_list = list(video_queue)[:5]
    
    with process_lock:
        active_count = len(active_processes)
        active_list = list(active_processes.items())[:5]
    
    # Calcular uso de disco
    try:
        total, used, free = shutil.disk_usage(WORK_DIR)
        disk_usage = f"💾 {used/total*100:.1f}% usado ({format_size(free)} libre)"
    except:
        disk_usage = "💾 N/A"
    
    status_text = (
        "📊 **Estado del Sistema de Compresión**\n\n"
        f"📋 **Videos en cola:** {queue_size}\n"
        f"🔄 **Procesando ahora:** {active_count}/{MAX_CONCURRENT_PROCESSES}\n"
        f"{disk_usage}\n"
        f"🕒 **Uptime:** {format_time(time.time() - app_start_time) if app_start_time else 'N/A'}\n\n"
    )
    
    if queue_size > 0:
        estimated_time = queue_size * 180  # 3 minutos por video estimado
        status_text += f"⏱️ **Tiempo estimado total:** {format_time(estimated_time)}\n\n"
        
        if queue_list:
            status_text += "**📥 Próximos en cola:**\n"
            for i, (_, _, _, _, name) in enumerate(queue_list, 1):
                short_name = name[:25] + "..." if len(name) > 25 else name
                status_text += f"{i}. `{short_name}`\n"
    
    if active_count > 0:
        status_text += "\n**🔄 Procesos activos:**\n"
        for task_id, info in active_list:
            elapsed = time.time() - info['start_time']
            short_name = info['filename'][:20] + "..." if len(info['filename']) > 20 else info['filename']
            progress = info.get('progress', 0)
            status_text += f"• `{short_name}` - {progress:.1f}% ({format_time(elapsed)})\n"
    
    # Información del sistema
    import psutil
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    status_text += f"\n**⚙️ Sistema:** CPU: {cpu_percent}% | RAM: {memory.percent}%"
    
    await message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("queue"))
async def queue_command(client, message: Message):
    """Muestra los videos en cola"""
    with queue_lock:
        if not video_queue:
            await message.reply_text(
                "📭 **La cola está vacía.**\n\n"
                "No hay videos esperando procesamiento. ¡Envía uno!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        queue_text = "📋 **Videos en cola de espera:**\n\n"
        total_size = 0
        user_in_queue = 0
        
        for i, (task_id, chat_id, msg_id, path, name) in enumerate(list(video_queue)[:8], 1):
            # Calcular tamaño si el archivo existe
            size_str = ""
            if os.path.exists(path):
                try:
                    size = os.path.getsize(path)
                    total_size += size
                    size_str = f" ({format_size(size)})"
                except:
                    size_str = " (error tamaño)"
            
            short_name = name[:35] + "..." if len(name) > 35 else name
            
            # Marcar los videos del usuario actual
            if chat_id == message.chat.id:
                queue_text += f"**{i}. `{short_name}`**{size_str} 👤\n"
                user_in_queue += 1
            else:
                queue_text += f"{i}. `{short_name}`{size_str}\n"
        
        if len(video_queue) > 8:
            queue_text += f"\n... y **{len(video_queue) - 8}** más.\n"
        
        queue_text += f"\n📦 **Tamaño total en cola:** {format_size(total_size)}"
        
        # Información del usuario
        if user_in_queue > 0:
            user_position = None
            for i, (_, chat_id, _, _, _) in enumerate(video_queue, 1):
                if chat_id == message.chat.id:
                    user_position = i
                    break
            
            if user_position:
                estimated_wait = max(0, user_position - len(active_processes)) * 180
                queue_text += f"\n\n👤 **Tus videos:** {user_in_queue} en cola"
                queue_text += f"\n🎯 **Tu posición:** {user_position}"
                queue_text += f"\n⏱️ **Espera estimada:** {format_time(estimated_wait)}"
        
        # Tiempo estimado total
        estimated_total = len(video_queue) * 180
        queue_text += f"\n⏱️ **Tiempo total estimado:** {format_time(estimated_total)}"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Actualizar", callback_data="refresh_queue"),
         InlineKeyboardButton("🧹 Limpiar mis videos", callback_data="clean_my")]
    ])
    
    await message.reply_text(queue_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

@app.on_message(filters.command("clean"))
async def clean_command(client, message: Message):
    """Limpia los videos del usuario de la cola"""
    user_id = message.chat.id
    removed_count = 0
    freed_space = 0
    
    with queue_lock:
        # Crear nueva cola sin los videos del usuario
        new_queue = deque()
        for task in video_queue:
            task_id, chat_id, msg_id, path, name = task
            if chat_id == user_id:
                # Eliminar archivo temporal
                try:
                    if os.path.exists(path):
                        size = os.path.getsize(path)
                        freed_space += size
                        os.remove(path)
                        logger.info(f"🗑️ Eliminado video de usuario {user_id}: {name}")
                except Exception as e:
                    logger.error(f"Error eliminando archivo {path}: {e}")
                removed_count += 1
            else:
                new_queue.append(task)
        
        video_queue.clear()
        video_queue.extend(new_queue)
    
    if removed_count > 0:
        response = (
            f"🧹 **Limpieza completada**\n\n"
            f"✅ Videos removidos: {removed_count}\n"
            f"💾 Espacio liberado: {format_size(freed_space)}\n"
            f"📋 Videos restantes en cola: {len(video_queue)}"
        )
    else:
        response = (
            "✅ **No tienes videos en la cola de espera.**\n\n"
            "Todos tus videos ya están siendo procesados o no hay videos pendientes."
        )
    
    await message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("info"))
async def info_command(client, message: Message):
    """Muestra información técnica del bot"""
    import platform
    import psutil
    
    # Información del sistema
    system_info = platform.system()
    python_version = platform.python_version()
    
    # Información de FFmpeg
    try:
        ffmpeg_result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        ffmpeg_version = ffmpeg_result.stdout.split('\n')[0] if ffmpeg_result.stdout else "No disponible"
    except:
        ffmpeg_version = "No instalado"
    
    # Uso de recursos
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    info_text = (
        "🛠️ **Información Técnica del Bot**\n\n"
        f"**📦 Sistema:** {system_info} | Python {python_version}\n"
        f"**🎬 FFmpeg:** {ffmpeg_version[:50]}...\n"
        f"**⚙️ Pyrogram:** {getattr(pyrogram, '__version__', 'N/A')}\n\n"
        
        f"**📊 Recursos del Sistema:**\n"
        f"• CPU: {cpu_percent}% utilizado\n"
        f"• RAM: {memory.percent}% ({format_size(memory.used)}/{format_size(memory.total)})\n"
        f"• Disco: {disk.percent}% ({format_size(disk.used)}/{format_size(disk.total)})\n\n"
        
        f"**⚡ Configuración del Bot:**\n"
        f"• Directorio de trabajo: {WORK_DIR}\n"
        f"• Máximo por video: {format_size(MAX_FILE_SIZE)}\n"
        f"• Máximo en cola: {MAX_QUEUE_SIZE}\n"
        f"• Procesos concurrentes: {MAX_CONCURRENT_PROCESSES}\n"
        f"• Resolución objetivo: {COMPRESSION_SETTINGS['resolution']}\n\n"
        
        f"**📈 Estadísticas:**\n"
        f"• Uptime: {format_time(time.time() - app_start_time) if app_start_time else 'N/A'}\n"
        f"• En cola: {len(video_queue)}\n"
        f"• Procesando: {len(active_processes)}\n"
        f"• Procesador activo: {'✅ Sí' if processor and processor.is_alive() else '❌ No'}"
    )
    
    await message.reply_text(info_text, parse_mode=ParseMode.MARKDOWN)

# MANEJADOR DE VIDEOS CORREGIDO - SIN filters.mime_type
@app.on_message(filters.video | filters.document)
async def handle_video(client, message: Message):
    """Maneja videos enviados al bot"""
    try:
        # Determinar si es un video válido
        is_video = False
        file_size = 0
        file_name = ""
        
        if message.video:
            # Es un video nativo de Telegram
            is_video = True
            file_size = message.video.file_size
            file_name = message.video.file_name or "video_telegram.mp4"
            mime_type = "video/mp4"
            
        elif message.document:
            # Verificar si es un documento de video usando nuestra función
            if is_video_document(message):
                is_video = True
                file_size = message.document.file_size
                file_name = message.document.file_name or "video_document.mp4"
                mime_type = message.document.mime_type or "video/mp4"
        
        if not is_video:
            # No es un video, ignorar
            return
        
        logger.info(f"📥 Video recibido: {file_name} ({format_size(file_size)}) de {message.chat.id}")
        
        # Verificar tamaño máximo
        if file_size > MAX_FILE_SIZE:
            await message.reply_text(
                f"❌ **Video demasiado grande**\n\n"
                f"Tamaño: {format_size(file_size)}\n"
                f"Límite máximo: {format_size(MAX_FILE_SIZE)}\n\n"
                "Por favor, envía un video más pequeño.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Verificar si la cola está llena
        with queue_lock:
            if len(video_queue) >= MAX_QUEUE_SIZE:
                await message.reply_text(
                    "❌ **Cola llena**\n\n"
                    "El sistema tiene demasiados videos en espera ({MAX_QUEUE_SIZE}).\n"
                    "Por favor, intenta de nuevo en unos minutos.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
        
        # Crear ID único para la tarea
        task_id = str(uuid.uuid4())[:8]
        
        # Notificar descarga
        download_msg = await message.reply_text(
            f"📥 **Descargando video...**\n\n"
            f"📁 `{file_name[:50]}{'...' if len(file_name) > 50 else ''}`\n"
            f"📦 {format_size(file_size)}\n"
            f"⏳ Por favor espera...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Crear nombre de archivo temporal
        timestamp = int(time.time())
        safe_name = re.sub(r'[^\w\-.]', '_', file_name)
        temp_name = f"temp_{timestamp}_{task_id}_{safe_name}"
        temp_path = os.path.join(WORK_DIR, temp_name)
        
        # Descargar el video
        try:
            await message.download(file_name=temp_path)
            
            # Verificar descarga
            if not os.path.exists(temp_path):
                await download_msg.edit_text("❌ Error al descargar el video (archivo no creado).")
                return
                
            downloaded_size = os.path.getsize(temp_path)
            if downloaded_size == 0:
                await download_msg.edit_text("❌ El archivo descargado está vacío.")
                try:
                    os.remove(temp_path)
                except:
                    pass
                return
                
            logger.info(f"✅ Video descargado: {file_name} -> {format_size(downloaded_size)}")
                
        except Exception as e:
            logger.error(f"❌ Error en descarga: {e}")
            await download_msg.edit_text(f"❌ Error al descargar el video: {str(e)[:100]}")
            return
        
        # Agregar a la cola
        with queue_lock:
            video_queue.append((task_id, message.chat.id, message.id, temp_path, file_name))
            position = len(video_queue)
        
        # Preparar respuesta
        response = (
            f"✅ **Video agregado a la cola**\n\n"
            f"📁 `{file_name[:50]}{'...' if len(file_name) > 50 else ''}`\n"
            f"📊 Tamaño: {format_size(file_size)}\n"
            f"🎯 Posición en cola: {position}\n"
            f"📋 Total en cola: {len(video_queue)}\n"
            f"🔄 Procesando ahora: {len(active_processes)}/{MAX_CONCURRENT_PROCESSES}\n\n"
        )
        
        if position == 1 and len(active_processes) < MAX_CONCURRENT_PROCESSES:
            response += "⚡ **Será procesado inmediatamente.**"
        else:
            wait_time = max(0, position - len(active_processes)) * 180  # 3 minutos por video
            response += f"⏱️ **Tiempo estimado de espera:** {format_time(wait_time)}"
        
        # Teclado con opciones
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📊 Estado", callback_data="status"),
                InlineKeyboardButton("📋 Ver Cola", callback_data="queue")
            ],
            [
                InlineKeyboardButton("🧹 Limpiar mis videos", callback_data="clean_my")
            ]
        ])
        
        await download_msg.edit_text(response, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"❌ Error manejando video: {e}")
        try:
            await message.reply_text(
                f"❌ **Error procesando tu video**\n\n"
                f"Detalle: {str(e)[:150]}\n\n"
                f"Por favor, intenta de nuevo o contacta al soporte.",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

@app.on_callback_query()
async def handle_callback(client, callback_query):
    """Maneja los botones inline"""
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    try:
        if data == "status":
            await status_command(client, callback_query.message)
        elif data == "queue":
            await queue_command(client, callback_query.message)
        elif data == "refresh_queue":
            await queue_command(client, callback_query.message)
            await callback_query.answer("✅ Cola actualizada")
        elif data == "clean_my":
            await clean_command(client, callback_query.message)
            await callback_query.answer("✅ Limpieza completada")
        elif data == "howto":
            await callback_query.message.reply_text(
                "❓ **Cómo usar el bot:**\n\n"
                "1. **Envía cualquier video** al bot\n"
                "2. **Espera a que se descargue** y se agregue a la cola\n"
                "3. **Mira el progreso** en tiempo real\n"
                "4. **Recibe tu video comprimido** automáticamente\n\n"
                "**💡 Consejos:**\n"
                "• Videos más cortos se procesan más rápido\n"
                "• Usa /queue para ver tu posición\n"
                "• Usa /clean para remover tus videos de la cola\n"
                "• El límite es 500MB por video\n\n"
                "**🔄 Proceso:** Descarga → Compresión → Envío",
                parse_mode=ParseMode.MARKDOWN
            )
            await callback_query.answer()
        else:
            await callback_query.answer("Acción no reconocida")
        
    except Exception as e:
        logger.error(f"❌ Error en callback: {e}")
        await callback_query.answer("❌ Error procesando la acción")

# ========== FUNCIÓN DE LIMPIEZA AUTOMÁTICA ==========
import shutil

def auto_cleanup():
    """Limpia archivos temporales antiguos automáticamente"""
    logger.info("🧹 Iniciando sistema de limpieza automática")
    
    while True:
        try:
            now = time.time()
            cleaned_files = 0
            cleaned_size = 0
            
            # Limpiar archivos con más de 3 horas
            for filename in os.listdir(WORK_DIR):
                filepath = os.path.join(WORK_DIR, filename)
                if os.path.isfile(filepath):
                    try:
                        file_age = now - os.path.getmtime(filepath)
                        if file_age > 10800:  # 3 horas
                            size = os.path.getsize(filepath)
                            os.remove(filepath)
                            cleaned_files += 1
                            cleaned_size += size
                            logger.debug(f"Auto-cleanup: {filename} ({format_size(size)})")
                    except Exception as e:
                        logger.error(f"Error eliminando {filename}: {e}")
            
            if cleaned_files > 0:
                logger.info(f"🧹 Auto-cleanup: {cleaned_files} archivos, {format_size(cleaned_size)}")
            
            # Esperar 30 minutos antes de la próxima limpieza
            time.sleep(1800)
            
        except Exception as e:
            logger.error(f"❌ Error en auto-cleanup: {e}")
            time.sleep(300)

# ========== INICIALIZACIÓN Y EJECUCIÓN ==========
async def main():
    """Función principal del bot"""
    global processor, app_start_time
    
    app_start_time = time.time()
    
    # Verificar que ffmpeg esté instalado
    logger.info("🔍 Verificando dependencias...")
    try:
        ffmpeg_check = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)
        if ffmpeg_check.returncode != 0:
            raise Exception("FFmpeg no responde correctamente")
        logger.info(f"✅ FFmpeg: {ffmpeg_check.stdout.split('version')[1].split()[0] if 'version' in ffmpeg_check.stdout else 'Disponible'}")
    except Exception as e:
        logger.error(f"❌ ERROR CRÍTICO: FFmpeg no está instalado o no funciona: {e}")
        print("\n" + "="*60)
        print("❌ ERROR: FFmpeg NO ESTÁ INSTALADO O NO FUNCIONA")
        print("="*60)
        print("Instala FFmpeg según tu sistema:")
        print("• Ubuntu/Debian: sudo apt install ffmpeg")
        print("• CentOS/RHEL: sudo yum install ffmpeg")
        print("• macOS: brew install ffmpeg")
        print("• Windows: Descarga desde ffmpeg.org")
        print("="*60)
        return
    
    # Iniciar Flask en hilo separado
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"🌐 Servidor Flask iniciado en puerto {os.environ.get('PORT', 10000)}")
    
    # Iniciar limpieza automática
    cleanup_thread = threading.Thread(target=auto_cleanup, daemon=True)
    cleanup_thread.start()
    logger.info("🧹 Sistema de limpieza automática iniciado")
    
    # Iniciar procesador de videos
    processor = VideoProcessor(app)
    processor.start()
    logger.info("🔄 Procesador de videos iniciado")
    
    # Iniciar bot de Telegram
    await app.start()
    
    # Obtener información del bot
    bot_info = await app.get_me()
    logger.info(f"✅ Bot de Telegram iniciado: @{bot_info.username} (ID: {bot_info.id})")
    
    # Mensaje de inicio completo
    print("\n" + "="*60)
    print("🎬 BOT DE COMPRESIÓN DE VIDEOS INICIADO")
    print("="*60)
    print(f"🤖 Bot: @{bot_info.username}")
    print(f"🆔 ID: {bot_info.id}")
    print(f"🌐 Web Server: http://0.0.0.0:{os.environ.get('PORT', 10000)}")
    print(f"📊 Health Check: /health")
    print(f"💾 Directorio: {WORK_DIR}")
    print(f"🚀 Procesos máx: {MAX_CONCURRENT_PROCESSES}")
    print(f"📋 Cola máx: {MAX_QUEUE_SIZE}")
    print(f"📦 Tamaño máx: {format_size(MAX_FILE_SIZE)}")
    print("="*60)
    print("✅ ¡Bot listo para recibir videos!")
    print("="*60 + "\n")
    
    # Enviar mensaje al admin si está configurado
    try:
        if ADMIN_USER_ID:
            await app.send_message(
                int(ADMIN_USER_ID),
                f"✅ **Bot iniciado exitosamente**\n\n"
                f"• 🤖 @{bot_info.username}\n"
                f"• 🌐 Web: puerto {os.environ.get('PORT', 10000)}\n"
                f"• 🕒 Hora: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"• 💾 Dir: {WORK_DIR}\n\n"
                f"¡Listo para comprimir videos!",
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logger.error(f"No se pudo notificar al admin: {e}")
    
    # Mantener el bot ejecutándose
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("Bot interrumpido")

if __name__ == "__main__":
    # Verificar e importar psutil si está disponible
    try:
        import psutil
        logger.info("✅ psutil disponible para monitoreo")
    except ImportError:
        logger.warning("⚠️ psutil no instalado, algunas funciones de monitoreo no estarán disponibles")
        # Crear un stub para psutil
        class psutil_stub:
            @staticmethod
            def cpu_percent():
                return 0
            class virtual_memory:
                percent = 0
                used = 0
                total = 0
            class disk_usage:
                def __init__(self, path):
                    self.percent = 0
                    self.used = 0
                    self.total = 0
        
        import sys
        sys.modules['psutil'] = psutil_stub()
        psutil = psutil_stub
    
    # Ejecutar el bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⏹️ Bot detenido por el usuario (Ctrl+C)")
        if processor:
            processor.stop()
            processor.join(timeout=5)
        print("\n👋 Bot detenido exitosamente")
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Limpieza final
        try:
            # Limpiar archivos temporales
            for filename in os.listdir(WORK_DIR):
                filepath = os.path.join(WORK_DIR, filename)
                if os.path.isfile(filepath):
                    try:
                        os.remove(filepath)
                    except:
                        pass
        except:
            pass
        
        print("\n🧹 Limpieza final completada")
