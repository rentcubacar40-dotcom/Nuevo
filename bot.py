"""
🎬 Video Compression Bot Pro
Bot profesional de compresión de videos con soporte para archivos de hasta 4GB
Web Service integrado con Flask para Render
"""

import os
import sys
import asyncio
import logging
import json
import time
import uuid
import shutil
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor

# Importaciones principales
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode, MessageMediaType
from flask import Flask, jsonify, request
import aiofiles
import psutil
import ffmpeg
from bson import ObjectId

# ========== CONFIGURACIÓN ==========
# Configuración desde variables de entorno (con valores por defecto)
API_ID = int(os.environ.get("API_ID", "34862843"))
API_HASH = os.environ.get("API_HASH", "c61367316282c464faaa7f162d339a59")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8301377215:AAH3y8w8MmQnHdgtqCX7JuOfVNMfg1DEg_A")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7825439699"))
PORT = int(os.environ.get("PORT", 10000))

# Configuración del sistema
MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024  # 4GB
MAX_CONCURRENT = 2
MAX_QUEUE_SIZE = 20
COMPRESSION_PRESET = "medium"
TARGET_RESOLUTION = "1280x720"
WORK_DIR = Path("/tmp/video_bot_pro")
UPLOAD_DIR = WORK_DIR / "uploads"
OUTPUT_DIR = WORK_DIR / "output"

# Crear directorios
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ========== LOGGING PROFESIONAL ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ========== FLASK APP PARA RENDER ==========
flask_app = Flask(__name__)
start_time = datetime.now()

@flask_app.route('/')
def home():
    """Página principal del web service"""
    return jsonify({
        "status": "online",
        "service": "Video Compression Bot Pro",
        "version": "2.0.0",
        "uptime": str(datetime.now() - start_time),
        "endpoints": {
            "health": "/health",
            "stats": "/stats",
            "queue": "/queue",
            "system": "/system"
        }
    })

@flask_app.route('/health')
def health_check():
    """Health check para Render"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "bot_running": "bot" in globals()
    }), 200

@flask_app.route('/stats')
def stats():
    """Estadísticas del bot"""
    return jsonify({
        "queue_size": len(task_queue),
        "active_tasks": len(active_tasks),
        "total_processed": stats_data["total_processed"],
        "total_size_processed": stats_data["total_size_processed"],
        "avg_compression_ratio": stats_data["avg_ratio"],
        "uptime": str(datetime.now() - start_time)
    })

@flask_app.route('/system')
def system_info():
    """Información del sistema"""
    return jsonify({
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent,
        "python_version": sys.version,
        "platform": sys.platform
    })

@flask_app.route('/queue')
def queue_status():
    """Estado de la cola"""
    queue_info = []
    for i, task in enumerate(list(task_queue)[:10], 1):
        queue_info.append({
            "position": i,
            "task_id": task["id"],
            "user_id": task["user_id"],
            "filename": task["filename"],
            "size": task["size"],
            "status": "queued"
        })
    
    active_info = []
    for task_id, task in active_tasks.items():
        active_info.append({
            "task_id": task_id,
            "filename": task.get("filename", "Unknown"),
            "progress": task.get("progress", 0),
            "start_time": task.get("start_time"),
            "user_id": task.get("user_id")
        })
    
    return jsonify({
        "queued": queue_info,
        "active": active_info,
        "max_queue": MAX_QUEUE_SIZE,
        "max_concurrent": MAX_CONCURRENT
    })

# ========== SISTEMA DE GESTIÓN DE TAREAS ==========
task_queue = deque()
active_tasks = {}
task_lock = threading.Lock()
stats_data = {
    "total_processed": 0,
    "total_size_processed": 0,
    "avg_ratio": 0
}

class TaskManager:
    """Gestor profesional de tareas de compresión"""
    
    @staticmethod
    def add_task(user_id: int, file_path: Path, filename: str, size: int):
        """Agrega una nueva tarea a la cola"""
        with task_lock:
            if len(task_queue) >= MAX_QUEUE_SIZE:
                raise Exception("Queue is full")
            
            task_id = str(uuid.uuid4())[:8]
            task = {
                "id": task_id,
                "user_id": user_id,
                "file_path": str(file_path),
                "filename": filename,
                "size": size,
                "added_time": datetime.now(),
                "status": "queued"
            }
            
            task_queue.append(task)
            logger.info(f"📥 Task added: {task_id} - {filename} ({size:,} bytes)")
            return task_id
    
    @staticmethod
    def get_next_task():
        """Obtiene la siguiente tarea de la cola"""
        with task_lock:
            if task_queue:
                return task_queue.popleft()
        return None
    
    @staticmethod
    def start_task(task_id, task_data):
        """Marca una tarea como activa"""
        with task_lock:
            active_tasks[task_id] = {
                **task_data,
                "start_time": datetime.now(),
                "progress": 0,
                "status": "processing"
            }
    
    @staticmethod
    def update_progress(task_id, progress):
        """Actualiza el progreso de una tarea"""
        with task_lock:
            if task_id in active_tasks:
                active_tasks[task_id]["progress"] = progress
    
    @staticmethod
    def complete_task(task_id, result):
        """Completa una tarea"""
        with task_lock:
            if task_id in active_tasks:
                # Actualizar estadísticas
                stats_data["total_processed"] += 1
                if "original_size" in result and "compressed_size" in result:
                    original = result["original_size"]
                    compressed = result["compressed_size"]
                    stats_data["total_size_processed"] += original
                    
                    if compressed > 0:
                        ratio = original / compressed
                        # Actualizar promedio móvil
                        if stats_data["avg_ratio"] == 0:
                            stats_data["avg_ratio"] = ratio
                        else:
                            stats_data["avg_ratio"] = (stats_data["avg_ratio"] + ratio) / 2
                
                del active_tasks[task_id]
                logger.info(f"✅ Task completed: {task_id}")
    
    @staticmethod
    def fail_task(task_id, error):
        """Marca una tarea como fallida"""
        with task_lock:
            if task_id in active_tasks:
                active_tasks[task_id]["status"] = "failed"
                active_tasks[task_id]["error"] = str(error)
                logger.error(f"❌ Task failed: {task_id} - {error}")

# ========== PROCESADOR DE VIDEOS ==========
class VideoProcessor:
    """Procesador profesional de videos usando FFmpeg"""
    
    @staticmethod
    def get_video_info(file_path: str) -> dict:
        """Obtiene información detallada del video"""
        try:
            probe = ffmpeg.probe(file_path)
            video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
            audio_stream = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
            
            return {
                "duration": float(probe['format']['duration']),
                "size": int(probe['format']['size']),
                "format": probe['format']['format_name'],
                "video": {
                    "codec": video_stream['codec_name'] if video_stream else None,
                    "resolution": f"{video_stream['width']}x{video_stream['height']}" if video_stream else None,
                    "bitrate": int(video_stream.get('bit_rate', 0)) if video_stream else 0,
                    "fps": eval(video_stream['avg_frame_rate']) if video_stream and 'avg_frame_rate' in video_stream else 0
                } if video_stream else None,
                "audio": {
                    "codec": audio_stream['codec_name'] if audio_stream else None,
                    "channels": audio_stream.get('channels', 0) if audio_stream else 0,
                    "bitrate": int(audio_stream.get('bit_rate', 0)) if audio_stream else 0
                } if audio_stream else None
            }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    @staticmethod
    def calculate_optimal_settings(original_info: dict, target_size_mb: int = 50):
        """Calcula configuración óptima para compresión"""
        duration = original_info["duration"]
        
        if duration <= 0:
            return {
                "video_bitrate": "1000k",
                "audio_bitrate": "128k",
                "crf": 23,
                "preset": COMPRESSION_PRESET
            }
        
        # Calcular bitrate para tamaño objetivo
        target_bits = target_size_mb * 8 * 1024 * 1024  # Convertir a bits
        required_bitrate = int(target_bits / duration)  # bits por segundo
        
        # Ajustar límites
        video_bitrate = max(500, min(required_bitrate - 128000, 4000000))
        audio_bitrate = 128000
        
        return {
            "video_bitrate": f"{video_bitrate // 1000}k",
            "audio_bitrate": f"{audio_bitrate // 1000}k",
            "crf": 23 if video_bitrate > 1500000 else 26,
            "preset": COMPRESSION_PRESET,
            "resolution": TARGET_RESOLUTION
        }
    
    @staticmethod
    async def compress_video(input_path: str, output_path: str, settings: dict, 
                           progress_callback=None) -> dict:
        """Comprime un video con progreso en tiempo real"""
        try:
            # Construir comando FFmpeg
            input_stream = ffmpeg.input(input_path)
            
            # Aplicar filtros
            video = input_stream.video.filter('scale', settings["resolution"])
            
            # Configurar salida
            output = ffmpeg.output(
                video,
                input_stream.audio,
                output_path,
                **{
                    'c:v': 'libx264',
                    'preset': settings["preset"],
                    'crf': str(settings["crf"]),
                    'b:v': settings["video_bitrate"],
                    'maxrate': settings["video_bitrate"],
                    'bufsize': f"{int(settings['video_bitrate'][:-1]) * 2}k",
                    'c:a': 'aac',
                    'b:a': settings["audio_bitrate"],
                    'threads': '2',
                    'movflags': '+faststart'
                }
            )
            
            # Ejecutar con callback de progreso
            process = await asyncio.create_subprocess_shell(
                ffmpeg.compile(output, overwrite_output=True),
                stderr=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL
            )
            
            # Monitorear progreso
            duration = None
            while True:
                line = await process.stderr.readline()
                if not line:
                    if process.returncode is not None:
                        break
                    await asyncio.sleep(0.1)
                    continue
                
                line = line.decode('utf-8', errors='ignore')
                
                # Parsear duración
                if duration is None and "Duration:" in line:
                    try:
                        dur_str = line.split("Duration:")[1].split(",")[0].strip()
                        h, m, s = dur_str.split(":")
                        s, ms = s.split(".")
                        duration = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 100
                    except:
                        pass
                
                # Parsear tiempo actual y llamar al callback
                if duration and "time=" in line and progress_callback:
                    try:
                        time_str = line.split("time=")[1].split(" ")[0]
                        h, m, s = time_str.split(":")
                        current = int(h) * 3600 + int(m) * 60 + float(s)
                        progress = min(99, (current / duration) * 100)
                        await progress_callback(progress)
                    except:
                        pass
            
            await process.wait()
            
            if process.returncode != 0:
                raise Exception(f"FFmpeg failed with code {process.returncode}")
            
            # Verificar archivo de salida
            if not os.path.exists(output_path):
                raise Exception("Output file not created")
            
            # Obtener información del archivo comprimido
            compressed_info = VideoProcessor.get_video_info(output_path)
            
            return {
                "success": True,
                "output_path": output_path,
                "compressed_info": compressed_info,
                "original_size": os.path.getsize(input_path),
                "compressed_size": os.path.getsize(output_path)
            }
            
        except Exception as e:
            logger.error(f"Compression error: {e}")
            return {"success": False, "error": str(e)}

# ========== BOT DE TELEGRAM ==========
# Configurar Pyrogram con ajustes optimizados
bot = Client(
    "video_compression_bot_pro",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=100,
    sleep_threshold=60,
    max_concurrent_transmissions=5,
    in_memory=True
)

# ========== MANEJADORES DEL BOT ==========
@bot.on_message(filters.command(["start", "help"]))
async def start_handler(client: Client, message: Message):
    """Manejador del comando /start"""
    welcome_text = """
🎬 **Video Compression Bot Pro** 🚀

¡Hola! Soy un bot profesional de compresión de videos con soporte para archivos de hasta **4GB**.

**📦 Características:**
• Compresión inteligente con FFmpeg
• Soporte para archivos de hasta 4GB
• Sistema de cola profesional
• Progreso en tiempo real
• Web dashboard integrado

**📁 Formatos soportados:**
MP4, AVI, MKV, MOV, WMV, FLV, WebM, y más...

**⚡ Comandos disponibles:**
/start - Muestra este mensaje
/status - Estado del sistema
/queue - Ver cola de procesamiento
/stats - Estadísticas del bot
/clean - Limpiar mis archivos

**🚀 ¡Solo envía un video para comenzar!**
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Web Dashboard", url=f"http://localhost:{PORT}")],
        [InlineKeyboardButton("📊 Estado", callback_data="status"),
         InlineKeyboardButton("📋 Cola", callback_data="queue")]
    ])
    
    await message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

@bot.on_message(filters.command("status"))
async def status_handler(client: Client, message: Message):
    """Estado del sistema"""
    with task_lock:
        queue_size = len(task_queue)
        active_count = len(active_tasks)
    
    # Información del sistema
    cpu = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    status_text = f"""
📊 **Estado del Sistema**

**🚦 Procesamiento:**
• 📋 En cola: {queue_size}/{MAX_QUEUE_SIZE}
• 🔄 Procesando: {active_count}/{MAX_CONCURRENT}
• ✅ Procesados: {stats_data['total_processed']}

**⚙️ Sistema:**
• CPU: {cpu:.1f}%
• RAM: {memory.percent:.1f}%
• Disco: {disk.percent:.1f}%
• Uptime: {str(datetime.now() - start_time).split('.')[0]}

**💾 Estadísticas:**
• Total procesado: {stats_data['total_size_processed']:,} bytes
• Ratio promedio: {stats_data['avg_ratio']:.2f}x
"""
    
    await message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)

@bot.on_message(filters.video | (filters.document & filters.private))
async def video_handler(client: Client, message: Message):
    """Manejador de videos"""
    try:
        user_id = message.from_user.id
        
        # Determinar tipo de archivo
        if message.video:
            file_size = message.video.file_size
            file_name = message.video.file_name or f"video_{message.video.file_id[:8]}.mp4"
        elif message.document:
            file_size = message.document.file_size
            file_name = message.document.file_name or "video_document"
        else:
            return
        
        # Verificar tamaño máximo
        if file_size > MAX_FILE_SIZE:
            await message.reply_text(
                f"❌ **Archivo demasiado grande**\n\n"
                f"Tamaño: {file_size:,} bytes ({file_size / 1024 / 1024 / 1024:.2f} GB)\n"
                f"Límite: {MAX_FILE_SIZE:,} bytes (4 GB)\n\n"
                f"Por favor, envía un archivo más pequeño.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Notificar inicio de descarga
        status_msg = await message.reply_text(
            f"📥 **Descargando archivo...**\n\n"
            f"📁 `{file_name}`\n"
            f"📦 {file_size:,} bytes\n"
            f"⏳ Por favor espera...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Crear nombre único para el archivo
        unique_id = str(uuid.uuid4())[:12]
        safe_name = "".join(c for c in file_name if c.isalnum() or c in "._- ")
        input_path = UPLOAD_DIR / f"{unique_id}_{safe_name}"
        
        # Descargar archivo
        try:
            download_start = time.time()
            await message.download(file_name=str(input_path))
            download_time = time.time() - download_start
            
            # Verificar descarga
            if not input_path.exists():
                await status_msg.edit_text("❌ Error al descargar el archivo")
                return
                
            actual_size = input_path.stat().st_size
            logger.info(f"✅ Descargado: {file_name} ({actual_size:,} bytes) en {download_time:.1f}s")
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            await status_msg.edit_text(f"❌ Error en descarga: {str(e)[:100]}")
            return
        
        # Agregar a la cola
        try:
            task_id = TaskManager.add_task(user_id, input_path, file_name, actual_size)
            
            with task_lock:
                position = len(task_queue) + len(active_tasks)
            
            # Mensaje de confirmación
            queue_text = f"""
✅ **Archivo agregado a la cola**

📁 `{file_name[:50]}{'...' if len(file_name) > 50 else ''}`
📦 {actual_size:,} bytes
🎯 Posición: #{position}
📋 En cola: {len(task_queue)}
🔄 Procesando: {len(active_tasks)}

"""
            
            if position <= MAX_CONCURRENT:
                queue_text += "⚡ **Será procesado inmediatamente**"
            else:
                wait_time = (position - MAX_CONCURRENT) * 300  # 5 minutos estimados
                queue_text += f"⏱️ **Tiempo estimado:** ~{wait_time // 60} minutos"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Estado", callback_data="status"),
                 InlineKeyboardButton("📋 Ver Cola", callback_data="queue")]
            ])
            
            await status_msg.edit_text(queue_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
            
        except Exception as e:
            await status_msg.edit_text(f"❌ Error al agregar a la cola: {str(e)[:100]}")
            # Limpiar archivo descargado
            try:
                input_path.unlink()
            except:
                pass
    
    except Exception as e:
        logger.error(f"Video handler error: {e}")
        try:
            await message.reply_text(f"❌ Error procesando tu archivo: {str(e)[:150]}")
        except:
            pass

@bot.on_callback_query()
async def callback_handler(client: Client, callback_query):
    """Manejador de botones inline"""
    data = callback_query.data
    
    try:
        if data == "status":
            await status_handler(client, callback_query.message)
        elif data == "queue":
            await queue_handler(client, callback_query.message)
        elif data == "stats":
            await stats_handler(client, callback_query.message)
        
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await callback_query.answer("❌ Error procesando la acción", show_alert=True)

@bot.on_message(filters.command("queue"))
async def queue_handler(client: Client, message: Message):
    """Muestra la cola actual"""
    with task_lock:
        total_in_queue = len(task_queue)
        user_tasks = [t for t in list(task_queue) if t["user_id"] == message.from_user.id]
    
    if total_in_queue == 0:
        await message.reply_text(
            "📭 **La cola está vacía**\n\n"
            "No hay videos esperando procesamiento. ¡Envía uno! 🎬",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    queue_text = f"📋 **Cola de procesamiento**\n\n"
    queue_text += f"Total en cola: **{total_in_queue}** videos\n"
    
    if user_tasks:
        queue_text += f"Tus videos en cola: **{len(user_tasks)}**\n\n"
        
        for i, task in enumerate(user_tasks[:5], 1):
            filename = task["filename"][:30] + "..." if len(task["filename"]) > 30 else task["filename"]
            size_mb = task["size"] / 1024 / 1024
            queue_text += f"{i}. `{filename}` ({size_mb:.1f} MB)\n"
    
    # Información de tiempo estimado
    with task_lock:
        active_count = len(active_tasks)
    
    if total_in_queue > 0:
        estimated_minutes = (total_in_queue * 5) // 60
        estimated_seconds = (total_in_queue * 5) % 60
        queue_text += f"\n⏱️ **Tiempo estimado total:** {estimated_minutes}min {estimated_seconds}s"
    
    await message.reply_text(queue_text, parse_mode=ParseMode.MARKDOWN)

@bot.on_message(filters.command("stats"))
async def stats_handler(client: Client, message: Message):
    """Estadísticas del bot"""
    stats_text = f"""
📈 **Estadísticas del Bot**

**📊 Procesamiento:**
• Total procesado: {stats_data['total_processed']} videos
• Tamaño total: {stats_data['total_size_processed']:,} bytes
• Ratio promedio: {stats_data['avg_ratio']:.2f}x

**🎯 Rendimiento:**
• Uptime: {str(datetime.now() - start_time).split('.')[0]}
• Máximo concurrente: {MAX_CONCURRENT}
• Máximo en cola: {MAX_QUEUE_SIZE}
• Límite por archivo: {MAX_FILE_SIZE / 1024 / 1024 / 1024:.1f} GB

**🌐 Web Service:**
• Puerto: {PORT}
• Endpoints disponibles: /health, /stats, /queue
• Dashboard: http://localhost:{PORT}
"""
    
    await message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

@bot.on_message(filters.command("clean"))
async def clean_handler(client: Client, message: Message):
    """Limpia archivos del usuario"""
    user_id = message.from_user.id
    cleaned = 0
    
    with task_lock:
        # Remover de la cola
        new_queue = deque()
        for task in task_queue:
            if task["user_id"] == user_id:
                # Eliminar archivo
                try:
                    if os.path.exists(task["file_path"]):
                        os.remove(task["file_path"])
                        cleaned += 1
                except:
                    pass
            else:
                new_queue.append(task)
        
        task_queue.clear()
        task_queue.extend(new_queue)
    
    await message.reply_text(
        f"🧹 **Limpieza completada**\n\n"
        f"✅ Archivos removidos: {cleaned}\n"
        f"📋 Videos restantes en cola: {len(task_queue)}",
        parse_mode=ParseMode.MARKDOWN
    )

# ========== WORKER DE PROCESAMIENTO ==========
async def process_worker():
    """Worker que procesa tareas de la cola"""
    logger.info("🚀 Worker de procesamiento iniciado")
    
    while True:
        try:
            # Obtener siguiente tarea
            task = TaskManager.get_next_task()
            
            if not task:
                await asyncio.sleep(2)
                continue
            
            task_id = task["id"]
            user_id = task["user_id"]
            file_path = task["file_path"]
            filename = task["filename"]
            
            logger.info(f"🎬 Procesando tarea {task_id}: {filename}")
            
            # Marcar como activa
            TaskManager.start_task(task_id, task)
            
            # Enviar mensaje de inicio al usuario
            try:
                await bot.send_message(
                    user_id,
                    f"🎬 **Comenzando compresión**\n\n"
                    f"📁 `{filename[:50]}{'...' if len(filename) > 50 else ''}`\n"
                    f"⏳ Preparando...",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
            
            # Función de callback para progreso
            async def update_progress(percent):
                TaskManager.update_progress(task_id, percent)
                
                # Actualizar cada 10% o cada 30 segundos
                if int(percent) % 10 == 0 or percent >= 99:
                    try:
                        progress_bar = "█" * int(percent / 10) + "░" * (10 - int(percent / 10))
                        await bot.send_message(
                            user_id,
                            f"🔄 **Progreso:** {percent:.1f}%\n"
                            f"{progress_bar}\n"
                            f"📁 `{filename[:40]}...`",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except:
                        pass
            
            # Crear ruta de salida
            output_filename = f"compressed_{task_id}_{filename}"
            output_path = OUTPUT_DIR / output_filename
            
            try:
                # Obtener información del video
                video_info = VideoProcessor.get_video_info(file_path)
                
                if not video_info:
                    raise Exception("No se pudo obtener información del video")
                
                # Calcular configuración óptima
                target_size_mb = min(100, task["size"] / 1024 / 1024 / 10)  # 10% del original, max 100MB
                settings = VideoProcessor.calculate_optimal_settings(video_info, target_size_mb)
                
                # Comprimir video
                result = await VideoProcessor.compress_video(
                    file_path,
                    str(output_path),
                    settings,
                    update_progress
                )
                
                if result["success"]:
                    # Calcular estadísticas
                    original_size = result["original_size"]
                    compressed_size = result["compressed_size"]
                    saved = original_size - compressed_size
                    saved_percent = (saved / original_size) * 100 if original_size > 0 else 0
                    ratio = original_size / compressed_size if compressed_size > 0 else 1
                    
                    # Enviar video comprimido
                    try:
                        await bot.send_video(
                            user_id,
                            video=str(output_path),
                            caption=(
                                f"✅ **Video comprimido exitosamente!**\n\n"
                                f"📁 `{filename}`\n\n"
                                f"📊 **Resultados:**\n"
                                f"• Original: {original_size:,} bytes\n"
                                f"• Comprimido: {compressed_size:,} bytes\n"
                                f"• Ahorro: {saved_percent:.1f}%\n"
                                f"• Ratio: {ratio:.1f}x\n"
                                f"• Resolución: {settings['resolution']}"
                            ),
                            parse_mode=ParseMode.MARKDOWN,
                            supports_streaming=True
                        )
                        
                        # Marcar como completada
                        TaskManager.complete_task(task_id, {
                            "original_size": original_size,
                            "compressed_size": compressed_size,
                            "ratio": ratio
                        })
                        
                    except Exception as send_error:
                        logger.error(f"Error sending video: {send_error}")
                        await bot.send_message(
                            user_id,
                            f"✅ Video comprimido pero no pude enviarlo.\n"
                            f"Tamaño: {compressed_size:,} bytes\n"
                            f"Ratio: {ratio:.1f}x\n\n"
                            f"Error: {str(send_error)[:100]}"
                        )
                else:
                    raise Exception(result.get("error", "Unknown compression error"))
                
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                TaskManager.fail_task(task_id, e)
                
                # Notificar al usuario
                try:
                    await bot.send_message(
                        user_id,
                        f"❌ **Error en compresión**\n\n"
                        f"📁 `{filename}`\n"
                        f"🔧 Error: {str(e)[:150]}\n\n"
                        f"Por favor, intenta con otro video.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
            
            finally:
                # Limpiar archivos temporales
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    if 'output_path' in locals() and os.path.exists(output_path):
                        os.remove(output_path)
                except:
                    pass
        
        except Exception as e:
            logger.error(f"Worker error: {e}")
            await asyncio.sleep(5)

# ========== INICIALIZACIÓN ==========
async def main():
    """Función principal"""
    logger.info("🚀 Iniciando Video Compression Bot Pro...")
    
    # Iniciar Flask en hilo separado
    def run_flask():
        flask_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"🌐 Flask iniciado en puerto {PORT}")
    
    # Iniciar worker de procesamiento
    worker_task = asyncio.create_task(process_worker())
    
    # Iniciar bot de Telegram
    await bot.start()
    
    bot_info = await bot.get_me()
    logger.info(f"🤖 Bot iniciado: @{bot_info.username}")
    
    # Limpiador automático de archivos temporales
    async def cleanup_worker():
        while True:
            try:
                now = time.time()
                for dir_path in [UPLOAD_DIR, OUTPUT_DIR]:
                    for file in dir_path.iterdir():
                        if file.is_file():
                            file_age = now - file.stat().st_mtime
                            if file_age > 3600:  # 1 hora
                                try:
                                    file.unlink()
                                    logger.debug(f"🗑️ Auto-cleanup: {file.name}")
                                except:
                                    pass
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
            await asyncio.sleep(1800)  # 30 minutos
    
    cleanup_task = asyncio.create_task(cleanup_worker())
    
    # Mensaje de inicio
    print("\n" + "="*60)
    print("🎬 VIDEO COMPRESSION BOT PRO - VERSION 2.0.0")
    print("="*60)
    print(f"🤖 Bot: @{bot_info.username}")
    print(f"🌐 Web Dashboard: http://0.0.0.0:{PORT}")
    print(f"📊 Health Check: /health")
    print(f"💾 Work Directory: {WORK_DIR}")
    print(f"🚀 Max File Size: {MAX_FILE_SIZE / 1024 / 1024 / 1024:.1f} GB")
    print(f"⚡ Max Concurrent: {MAX_CONCURRENT}")
    print(f"📋 Max Queue: {MAX_QUEUE_SIZE}")
    print("="*60)
    print("✅ ¡Bot listo para procesar videos de hasta 4GB!")
    print("="*60)
    
    # Notificar al admin
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🚀 **Bot iniciado exitosamente**\n\n"
            f"• 🤖 @{bot_info.username}\n"
            f"• 🌐 Web: puerto {PORT}\n"
            f"• 🕒 Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"• 💾 Dir: {WORK_DIR}\n"
            f"• 📊 Stats: http://0.0.0.0:{PORT}/stats\n\n"
            f"¡Listo para comprimir videos de hasta 4GB!",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass
    
    # Mantener ejecución
    try:
        await idle()
    finally:
        await bot.stop()
        worker_task.cancel()
        cleanup_task.cancel()

if __name__ == "__main__":
    # Verificar dependencias críticas
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except:
        pass
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⏹️ Bot detenido por el usuario")
        print("\n👋 Bot detenido exitosamente")
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
