import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import subprocess
from concurrent.futures import ThreadPoolExecutor

from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, RPCError
from moviepy.editor import VideoFileClip
from PIL import Image
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración
API_ID = 20534584
API_HASH = "6d5b13261d2c92a9a00afc1fd613b9df"
BOT_TOKEN = "8562042457:AAGA__pfWDMVfdslzqwnoFl4yLrAre-HJ5I"

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Directorios
TEMP_DIR = "temp_videos"
COMPRESSED_DIR = "compressed_videos"
THUMBNAILS_DIR = "thumbnails"
MAX_SIZE_GB = 4
MAX_SIZE_BYTES = MAX_SIZE_GB * 1024 * 1024 * 1024

# Crear directorios
for directory in [TEMP_DIR, COMPRESSED_DIR, THUMBNAILS_DIR]:
    os.makedirs(directory, exist_ok=True)

# Inicializar cliente Pyrogram
app = Client(
    "video_compressor_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=4,
    max_concurrent_transmissions=2
)

# Pool de threads para procesamiento pesado
executor = ThreadPoolExecutor(max_workers=2)

class VideoProcessor:
    """Clase para procesamiento de videos"""
    
    @staticmethod
    def get_video_info(video_path: str) -> dict:
        """Obtiene información del video usando ffprobe"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,duration,bit_rate,codec_name,r_frame_rate',
                '-of', 'csv=p=0',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = result.stdout.strip().split(',')
                if len(data) >= 6:
                    width, height = int(data[0]), int(data[1])
                    duration = float(data[2]) if data[2] else 0
                    bitrate = int(data[3]) if data[3] and data[3].isdigit() else 0
                    codec = data[4] if data[4] else 'unknown'
                    fps = eval(data[5]) if data[5] else 30
                    
                    # Calcular tamaño aproximado si no hay bitrate
                    if not bitrate and duration > 0:
                        bitrate = int((os.path.getsize(video_path) * 8) / duration)
                    
                    return {
                        'width': width,
                        'height': height,
                        'duration': duration,
                        'bitrate': bitrate,
                        'codec': codec,
                        'fps': fps,
                        'size_mb': os.path.getsize(video_path) / (1024 * 1024)
                    }
        except Exception as e:
            logger.error(f"Error obteniendo info del video: {e}")
        
        return None
    
    @staticmethod
    def create_thumbnail(video_path: str, output_path: str, time_sec: float = 5) -> bool:
        """Crea un thumbnail del video"""
        try:
            # Usar ffmpeg para extraer frame
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-ss', str(time_sec),
                '-vframes', '1',
                '-vf', 'scale=320:-1',
                '-q:v', '2',
                output_path,
                '-y'
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error creando thumbnail: {e}")
            return False
    
    @staticmethod
    def compress_video(input_path: str, output_path: str, quality: str = "medium") -> Tuple[bool, str]:
        """
        Comprime video usando ffmpeg con configuración optimizada
        quality: "low", "medium", "high", "very_high"
        """
        try:
            # Obtener información del video original
            info = VideoProcessor.get_video_info(input_path)
            if not info:
                return False, "No se pudo obtener información del video"
            
            # Configuración de compresión por calidad
            quality_settings = {
                "low": {
                    "crf": 28,
                    "preset": "ultrafast",
                    "bitrate": "500k",
                    "audio_bitrate": "64k"
                },
                "medium": {
                    "crf": 23,
                    "preset": "medium",
                    "bitrate": "1000k",
                    "audio_bitrate": "128k"
                },
                "high": {
                    "crf": 20,
                    "preset": "slow",
                    "bitrate": "2000k",
                    "audio_bitrate": "192k"
                },
                "very_high": {
                    "crf": 18,
                    "preset": "veryslow",
                    "bitrate": "3000k",
                    "audio_bitrate": "256k"
                }
            }
            
            settings = quality_settings.get(quality, quality_settings["medium"])
            
            # Calcular dimensiones escaladas (manteniendo aspect ratio)
            max_width = 1280 if quality in ["low", "medium"] else 1920
            scale_filter = f"scale='if(gt(iw,ih),min({max_width},iw),-1)':'if(gt(iw,ih),-1,min({max_width},ih))'"
            
            # Comando ffmpeg optimizado
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:v', 'libx264',
                '-crf', str(settings["crf"]),
                '-preset', settings["preset"],
                '-vf', scale_filter,
                '-c:a', 'aac',
                '-b:a', settings["audio_bitrate"],
                '-movflags', '+faststart',
                '-threads', '0',  # Usar todos los cores disponibles
                output_path,
                '-y'
            ]
            
            logger.info(f"Comprimiendo video con calidad {quality}: {' '.join(cmd)}")
            
            # Ejecutar compresión
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hora máximo
            )
            
            if process.returncode != 0:
                logger.error(f"Error en ffmpeg: {process.stderr}")
                return False, f"Error en compresión: {process.stderr[:200]}"
            
            # Verificar tamaño resultante
            original_size = os.path.getsize(input_path)
            compressed_size = os.path.getsize(output_path)
            compression_ratio = (1 - (compressed_size / original_size)) * 100
            
            logger.info(f"Compresión completada: {original_size/1024/1024:.2f}MB -> {compressed_size/1024/1024:.2f}MB ({compression_ratio:.1f}%)")
            
            return True, f"✅ Compresión exitosa\n📊 Reducción: {compression_ratio:.1f}%\n📦 Tamaño final: {compressed_size/1024/1024:.2f}MB"
            
        except subprocess.TimeoutExpired:
            return False, "⏱️ Tiempo de compresión excedido"
        except Exception as e:
            logger.error(f"Error en compresión: {e}")
            return False, f"❌ Error: {str(e)}"

# Estado del usuario
user_state = {}

# Handlers
@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    """Maneja el comando /start"""
    welcome_text = """
🎬 *BOT COMPRESOR DE VIDEOS* 🎬

¡Hola! Soy un bot especializado en comprimir videos manteniendo calidad.

✅ *Características:*
• 📦 Soporta videos de hasta 4GB
• ⚡ Compresión rápida y eficiente
• 🎚️ 4 niveles de calidad ajustables
• 🖼️ Thumbnails automáticos
• 📊 Información detallada del video

📤 *Para comenzar:*
1. Envíame un video
2. Elige la calidad de compresión
3. Espera el procesamiento
4. ¡Descarga tu video optimizado!

⚙️ *Comandos disponibles:*
/start - Mostrar este mensaje
/help - Ayuda detallada
/info - Información del bot
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Comprimir Video", callback_data="compress_guide")],
        [InlineKeyboardButton("⚙️ Configurar Calidad", callback_data="config_quality")],
        [InlineKeyboardButton("📊 Estadísticas", callback_data="stats")]
    ])
    
    await message.reply_text(
        welcome_text,
        parse_mode=enums.ParseMode.MARKDOWN,
        reply_markup=keyboard
    )

@app.on_message(filters.command("help"))
async def help_handler(client: Client, message: Message):
    """Maneja el comando /help"""
    help_text = """
🆘 *GUÍA DE USO* 🆘

1. 📤 *ENVÍO DE VIDEO:*
   • Envía el video directamente al chat
   • Puede ser video de Telegram o archivo
   • Máximo 4GB por archivo

2. ⚙️ *SELECCIÓN DE CALIDAD:*
   • 🟢 Baja: Máxima compresión (para WhatsApp)
   • 🟡 Media: Balance calidad/tamaño (recomendado)
   • 🟠 Alta: Buena calidad, compresión moderada
   • 🔴 Muy Alta: Calidad casi original

3. ⏳ *PROCESAMIENTO:*
   • El tiempo depende del tamaño y calidad
   • Videos grandes pueden tardar varios minutos
   • Recibirás notificación cuando esté listo

4. 📥 *DESCARGA:*
   • Video comprimido + thumbnail
   • Información de compresión
   • Botón para volver a comprimir

⚠️ *NOTAS IMPORTANTES:*
• Solo procesa videos (mp4, mkv, mov, avi)
• Mantén conexión estable durante procesamiento
• Los archivos temporales se eliminan automáticamente
"""
    
    await message.reply_text(help_text, parse_mode=enums.ParseMode.MARKDOWN)

@app.on_message(filters.video | filters.document)
async def video_handler(client: Client, message: Message):
    """Maneja la recepción de videos"""
    user_id = message.from_user.id
    
    # Verificar tamaño del archivo
    if message.video:
        file_size = message.video.file_size
        mime_type = "video"
    elif message.document:
        file_size = message.document.file_size
        mime_type = message.document.mime_type or ""
    
    # Verificar si es video
    if not (message.video or (message.document and "video" in mime_type)):
        await message.reply_text("❌ Por favor envía un archivo de video válido.")
        return
    
    # Verificar tamaño máximo
    if file_size > MAX_SIZE_BYTES:
        await message.reply_text(f"❌ El archivo excede el límite de {MAX_SIZE_GB}GB.\nTamaño actual: {file_size/1024/1024/1024:.2f}GB")
        return
    
    # Guardar estado del usuario
    user_state[user_id] = {
        "message_id": message.id,
        "chat_id": message.chat.id,
        "file_size": file_size,
        "processing": False
    }
    
    # Preguntar por calidad
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 Baja", callback_data="quality_low"),
            InlineKeyboardButton("🟡 Media", callback_data="quality_medium")
        ],
        [
            InlineKeyboardButton("🟠 Alta", callback_data="quality_high"),
            InlineKeyboardButton("🔴 Muy Alta", callback_data="quality_very_high")
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel_process")]
    ])
    
    await message.reply_text(
        f"🎬 *Video recibido:* {file_size/1024/1024:.2f}MB\n\n"
        "⚙️ *Selecciona la calidad de compresión:*\n\n"
        "🟢 **Baja:** Máxima compresión (para compartir)\n"
        "🟡 **Media:** Balance calidad/tamaño (recomendado)\n"
        "🟠 **Alta:** Buena calidad, menos compresión\n"
        "🔴 **Muy Alta:** Calidad casi original",
        parse_mode=enums.ParseMode.MARKDOWN,
        reply_markup=keyboard
    )

@app.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    """Maneja todos los callbacks"""
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    # Procesar según el callback
    if data == "compress_guide":
        await callback_query.answer()
        await callback_query.message.reply_text(
            "📤 Simplemente envía un video al chat para comenzar la compresión.",
            parse_mode=enums.ParseMode.MARKDOWN
        )
    
    elif data == "config_quality":
        await callback_query.answer()
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🟢 Baja", callback_data="set_low"),
                InlineKeyboardButton("🟡 Media", callback_data="set_medium")
            ],
            [
                InlineKeyboardButton("🟠 Alta", callback_data="set_high"),
                InlineKeyboardButton("🔴 Muy Alta", callback_data="set_very_high")
            ]
        ])
        await callback_query.message.edit_text(
            "⚙️ *Selecciona calidad predeterminada:*",
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    
    elif data.startswith("quality_"):
        await handle_quality_selection(client, callback_query)
    
    elif data == "cancel_process":
        await callback_query.answer("Proceso cancelado")
        if user_id in user_state:
            del user_state[user_id]
        await callback_query.message.delete()
    
    elif data.startswith("set_"):
        quality = data.split("_")[1]
        await callback_query.answer(f"Calidad {quality} establecida")
        await callback_query.message.edit_text(f"✅ Calidad predeterminada establecida: {quality.upper()}")

async def handle_quality_selection(client: Client, callback_query: CallbackQuery):
    """Maneja la selección de calidad"""
    user_id = callback_query.from_user.id
    quality = callback_query.data.split("_")[1]
    
    if user_id not in user_state:
        await callback_query.answer("Sesión expirada. Envía el video nuevamente.")
        return
    
    if user_state[user_id].get("processing"):
        await callback_query.answer("Ya hay un video en procesamiento.")
        return
    
    # Marcar como en procesamiento
    user_state[user_id]["processing"] = True
    user_state[user_id]["quality"] = quality
    
    await callback_query.answer(f"Procesando con calidad {quality}...")
    
    # Editar mensaje para mostrar estado
    status_msg = await callback_query.message.edit_text(
        f"⏳ *Descargando video...*\n"
        f"⚙️ Calidad: {quality.upper()}\n"
        f"🔄 Por favor espera...",
        parse_mode=enums.ParseMode.MARKDOWN
    )
    
    try:
        # Descargar el video
        message = await client.get_messages(
            user_state[user_id]["chat_id"],
            user_state[user_id]["message_id"]
        )
        
        # Crear nombres de archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_path = Path(TEMP_DIR) / f"original_{user_id}_{timestamp}.mp4"
        compressed_path = Path(COMPRESSED_DIR) / f"compressed_{user_id}_{timestamp}.mp4"
        thumbnail_path = Path(THUMBNAILS_DIR) / f"thumb_{user_id}_{timestamp}.jpg"
        
        # Actualizar estado
        await status_msg.edit_text(
            f"⏳ *Descargando video...*\n"
            f"📥 Progreso: 0%\n"
            f"⚙️ Calidad: {quality.upper()}",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
        # Función para mostrar progreso
        def progress(current, total):
            percent = (current / total) * 100
            asyncio.run_coroutine_threadsafe(
                status_msg.edit_text(
                    f"⏳ *Descargando video...*\n"
                    f"📥 Progreso: {percent:.1f}%\n"
                    f"⚙️ Calidad: {quality.upper()}",
                    parse_mode=enums.ParseMode.MARKDOWN
                ),
                client.loop
            )
        
        # Descargar el archivo
        await callback_query.message.reply_chat_action(enums.ChatAction.UPLOAD_VIDEO)
        
        download_path = await message.download(
            file_name=str(original_path),
            progress=progress
        )
        
        # Actualizar para compresión
        await status_msg.edit_text(
            f"✅ *Video descargado*\n"
            f"⚙️ *Comprimiendo con calidad {quality.upper()}...*\n"
            f"⏳ Esto puede tardar varios minutos...",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
        # Comprimir en thread separado
        loop = asyncio.get_event_loop()
        success, result = await loop.run_in_executor(
            executor,
            VideoProcessor.compress_video,
            str(download_path),
            str(compressed_path),
            quality
        )
        
        if not success:
            await status_msg.edit_text(f"❌ {result}")
            # Limpiar archivos
            for path in [download_path, compressed_path]:
                if path and os.path.exists(path):
                    os.remove(path)
            return
        
        # Crear thumbnail
        thumbnail_created = VideoProcessor.create_thumbnail(
            str(compressed_path),
            str(thumbnail_path)
        )
        
        # Enviar video comprimido
        await callback_query.message.reply_chat_action(enums.ChatAction.UPLOAD_VIDEO)
        
        # Obtener información del video comprimido
        compressed_info = VideoProcessor.get_video_info(str(compressed_path))
        compressed_size = os.path.getsize(compressed_path)
        
        # Preparar caption
        caption = (
            f"✅ *VIDEO COMPRIMIDO*\n\n"
            f"📊 *Información:*\n"
            f"• 📦 Tamaño original: {user_state[user_id]['file_size']/1024/1024:.2f}MB\n"
            f"• 📥 Tamaño final: {compressed_size/1024/1024:.2f}MB\n"
            f"• 🎚️ Calidad: {quality.upper()}\n"
            f"• ⏱️ Duración: {compressed_info['duration']:.1f}s\n"
            f"• 🖼️ Resolución: {compressed_info['width']}x{compressed_info['height']}\n\n"
            f"{result}"
        )
        
        # Enviar video con thumbnail si está disponible
        if thumbnail_created and os.path.exists(thumbnail_path):
            await client.send_video(
                chat_id=user_id,
                video=str(compressed_path),
                caption=caption,
                parse_mode=enums.ParseMode.MARKDOWN,
                thumb=str(thumbnail_path),
                duration=int(compressed_info['duration']),
                width=compressed_info['width'],
                height=compressed_info['height'],
                supports_streaming=True
            )
        else:
            await client.send_video(
                chat_id=user_id,
                video=str(compressed_path),
                caption=caption,
                parse_mode=enums.ParseMode.MARKDOWN,
                supports_streaming=True
            )
        
        # Mensaje final
        await status_msg.edit_text(
            f"✅ *Proceso completado*\n\n"
            f"🎬 Video comprimido enviado\n"
            f"📊 Reducción aplicada\n"
            f"📤 Listo para descargar\n\n"
            f"🔄 Envía otro video para continuar",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
        # Limpiar archivos temporales después de 5 minutos
        async def cleanup_files():
            await asyncio.sleep(300)  # 5 minutos
            for path in [download_path, str(compressed_path), str(thumbnail_path)]:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass
        
        asyncio.create_task(cleanup_files())
        
    except FloodWait as e:
        await status_msg.edit_text(f"⏳ Por favor espera {e.value} segundos antes de intentar nuevamente.")
    except RPCError as e:
        await status_msg.edit_text(f"❌ Error de Telegram: {e}")
    except Exception as e:
        logger.error(f"Error en procesamiento: {e}")
        await status_msg.edit_text(f"❌ Error inesperado: {str(e)}")
    finally:
        # Limpiar estado
        if user_id in user_state:
            del user_state[user_id]

@app.on_message(filters.command("info"))
async def info_handler(client: Client, message: Message):
    """Información del bot y estadísticas"""
    info_text = """
🤖 *INFORMACIÓN DEL BOT*

*Desarrollador:* @TuUsuario
*Versión:* 2.0.0
*Soporte:* Hasta 4GB por archivo

*Tecnologías utilizadas:*
• Pyrogram para la API de Telegram
• FFmpeg para procesamiento de video
• Compresión H.264 optimizada

*Estadísticas:*
• Máximo tamaño: 4GB
• Formatos soportados: MP4, MKV, MOV, AVI, etc.
• Calidades disponibles: 4 niveles

📝 *Código fuente:* [GitHub](https://github.com)
🆘 *Soporte:* @TuUsuario
"""
    await message.reply_text(info_text, parse_mode=enums.ParseMode.MARKDOWN, disable_web_page_preview=True)

# Manejo de errores
@app.on_message()
async def unknown_handler(client: Client, message: Message):
    """Maneja mensajes desconocidos"""
    await message.reply_text(
        "🤔 No entendí ese comando.\n\n"
        "📤 Envía un video o usa /start para ver las opciones disponibles.",
        parse_mode=enums.ParseMode.MARKDOWN
    )

# Función principal
async def main():
    """Función principal"""
    logger.info("Iniciando bot compresor de videos...")
    await app.start()
    logger.info("Bot iniciado correctamente")
    
    # Mantener el bot corriendo
    await asyncio.Event().wait()

if __name__ == "__main__":
    # Archivo .env necesario con:
    # API_ID=tu_api_id
    # API_HASH=tu_api_hash
    # BOT_TOKEN=tu_bot_token
    
    print("""
    ====================================
        BOT COMPRESOR DE VIDEOS
    ====================================
    Características:
    • Soporta videos de hasta 4GB
    • 4 niveles de compresión
    • Procesamiento asíncrono
    • Thumbnails automáticos
    ====================================
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot detenido por el usuario")
    except Exception as e:
        logger.error(f"Error fatal: {e}")
