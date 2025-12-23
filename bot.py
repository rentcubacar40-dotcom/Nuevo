#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import asyncio
import logging
from typing import Optional, Tuple
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== CONFIGURACIÓN ====================
# Variables de configuración (cámbialas por tus valores)
API_ID = 20534584  # Tu API ID de my.telegram.org
API_HASH = "6d5b13261d2c92a9a00afc1fd613b9df"  # Tu API Hash
BOT_TOKEN = "8562042457:AAGA__pfWDMVfdslzqwnoFl4yLrAre-HJ5I"  # Token del bot de @BotFather
MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024  # 4GB en bytes
ADMIN_USER_ID = 7363341763  # Tu ID de usuario de Telegram

# Configuración de compresión
SUPPORTED_FORMATS = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v', '.3gp']
COMPRESSION_PRESETS = {
    'alta': '-crf 28 -preset fast',
    'media': '-crf 23 -preset medium',
    'baja': '-crf 18 -preset slow'
}
# ========================================================

# Inicializar cliente Pyrogram
app = Client(
    "video_compressor_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=4,
    sleep_threshold=60,
    max_concurrent_transmissions=2
)

# Directorios de trabajo
WORK_DIR = "workdir"
COMPRESSED_DIR = "compressed"
os.makedirs(WORK_DIR, exist_ok=True)
os.makedirs(COMPRESSED_DIR, exist_ok=True)

class VideoCompressor:
    def __init__(self):
        self.processing = {}
    
    async def get_video_info(self, input_path: str) -> Optional[dict]:
        """Obtiene información del video usando ffprobe"""
        try:
            import subprocess
            import json
            
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                input_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return None
            
            info = json.loads(result.stdout)
            video_info = {}
            
            # Buscar stream de video
            for stream in info.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_info['duration'] = float(stream.get('duration', 0))
                    video_info['width'] = stream.get('width', 0)
                    video_info['height'] = stream.get('height', 0)
                    video_info['codec'] = stream.get('codec_name', 'unknown')
                    video_info['bitrate'] = stream.get('bit_rate', '0')
                    break
            
            video_info['size'] = os.path.getsize(input_path)
            video_info['format'] = info.get('format', {}).get('format_name', 'unknown')
            
            return video_info
        except Exception as e:
            logger.error(f"Error al obtener info del video: {e}")
            return None
    
    async def compress_video(self, input_path: str, output_path: str, 
                           quality: str = 'media') -> Tuple[bool, str]:
        """Comprime el video usando FFmpeg"""
        try:
            import subprocess
            
            if quality not in COMPRESSION_PRESETS:
                quality = 'media'
            
            preset = COMPRESSION_PRESETS[quality]
            
            # Comando de compresión optimizado
            cmd = [
                'ffmpeg', '-i', input_path,
                '-c:v', 'libx264',
                *preset.split(),
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y',  # Sobrescribir archivo si existe
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                original_size = os.path.getsize(input_path)
                compressed_size = os.path.getsize(output_path)
                compression_ratio = ((original_size - compressed_size) / original_size) * 100
                
                return True, f"✅ Compresión exitosa\n\n" \
                           f"📊 **Resultados:**\n" \
                           f"• Tamaño original: {self.format_size(original_size)}\n" \
                           f"• Tamaño comprimido: {self.format_size(compressed_size)}\n" \
                           f"• Reducción: {compression_ratio:.1f}%"
            else:
                return False, f"❌ Error en la compresión:\n{stderr.decode()}"
                
        except Exception as e:
            logger.error(f"Error en compresión: {e}")
            return False, f"❌ Error: {str(e)}"
    
    def format_size(self, size_bytes: int) -> str:
        """Formatea el tamaño en bytes a formato legible"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
    
    def cleanup_files(self, *file_paths):
        """Limpia archivos temporales"""
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Error limpiando archivo {file_path}: {e}")

compressor = VideoCompressor()

# ==================== HANDLERS ====================

@app.on_message(filters.command(["start", "help"]))
async def start_command(client: Client, message: Message):
    """Mensaje de bienvenida"""
    welcome_text = """
🤖 **Video Compressor Bot** 🎬

¡Hola! Soy un bot especializado en comprimir videos manteniendo buena calidad.

**📋 Características:**
• Comprime videos hasta **4GB**
• Soporta múltiples formatos
• 3 niveles de compresión
• Mantiene calidad de audio

**⚡ Comandos disponibles:**
/start - Mostrar este mensaje
/help - Mostrar ayuda
/compress - Comprimir un video
/stats - Ver estadísticas del bot

**📤 Cómo usar:**
1. Envíame un video (hasta 4GB)
2. Elige el nivel de compresión
3. Espera el procesamiento
4. Recibe tu video comprimido

**📝 Formato soportados:** MP4, AVI, MOV, MKV, FLV, WMV, WEBM, M4V, 3GP
"""
    
    await message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Comprimir Video", callback_data="compress_info")]
        ])
    )

@app.on_message(filters.command("compress"))
async def compress_command(client: Client, message: Message):
    """Instrucciones para comprimir"""
    await message.reply_text(
        "📤 **Para comprimir un video:**\n\n"
        "1. Envíame el video que deseas comprimir\n"
        "2. Elige el nivel de compresión cuando te lo pida\n"
        "3. Espera mientras proceso el video\n"
        "4. Recibirás el video comprimido\n\n"
        "📊 **Niveles de compresión:**\n"
        "• **Alta** - Máxima compresión\n"
        "• **Media** - Balance calidad/tamaño\n"
        "• **Baja** - Máxima calidad",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.command("stats"))
async def stats_command(client: Client, message: Message):
    """Estadísticas del bot"""
    if message.from_user.id != ADMIN_USER_ID:
        await message.reply_text("❌ Solo el administrador puede ver las estadísticas.")
        return
    
    import psutil
    import shutil
    
    disk_usage = shutil.disk_usage("/")
    memory = psutil.virtual_memory()
    
    stats_text = f"""
📊 **Estadísticas del Bot**

**💾 Uso de disco:**
• Total: {compressor.format_size(disk_usage.total)}
• Usado: {compressor.format_size(disk_usage.used)}
• Libre: {compressor.format_size(disk_usage.free)}

**🧠 Memoria:**
• Total: {compressor.format_size(memory.total)}
• Usado: {compressor.format_size(memory.used)}
• Libre: {compressor.format_size(memory.available)}

**📈 Archivos temporales:**
• Directorio de trabajo: {len(os.listdir(WORK_DIR))} archivos
"""
    
    await message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.video | filters.document)
async def handle_video(client: Client, message: Message):
    """Maneja videos enviados al bot"""
    try:
        user_id = message.from_user.id
        
        # Verificar si el usuario ya está procesando un video
        if user_id in compressor.processing:
            await message.reply_text("⏳ Ya tienes un video en proceso. Espera a que termine.")
            return
        
        # Obtener información del archivo
        if message.video:
            file = message.video
            file_name = file.file_name or f"video_{message.id}.mp4"
        else:
            file = message.document
            file_name = file.file_name
            
            # Verificar formato soportado
            file_ext = os.path.splitext(file_name.lower())[1]
            if file_ext not in SUPPORTED_FORMATS:
                await message.reply_text(
                    f"❌ Formato no soportado. Formatos aceptados:\n" +
                    ", ".join(SUPPORTED_FORMATS)
                )
                return
        
        # Verificar tamaño del archivo
        if file.file_size > MAX_FILE_SIZE:
            await message.reply_text(
                f"❌ El archivo es demasiado grande. "
                f"Máximo permitido: {compressor.format_size(MAX_FILE_SIZE)}"
            )
            return
        
        # Marcar usuario como procesando
        compressor.processing[user_id] = True
        
        # Informar al usuario
        status_msg = await message.reply_text(
            "📥 **Descargando video...**\n"
            f"📝 Nombre: `{file_name}`\n"
            f"📦 Tamaño: {compressor.format_size(file.file_size)}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Descargar el video
        input_path = os.path.join(WORK_DIR, f"input_{user_id}_{message.id}")
        
        await client.download_media(
            message,
            file_name=input_path,
            progress=self.progress_callback,
            progress_args=(status_msg, "descargando")
        )
        
        # Obtener información del video
        await status_msg.edit_text("📊 **Analizando video...**")
        video_info = await compressor.get_video_info(input_path)
        
        if not video_info:
            await status_msg.edit_text("❌ No se pudo analizar el video.")
            del compressor.processing[user_id]
            compressor.cleanup_files(input_path)
            return
        
        # Mostrar información y opciones de compresión
        info_text = f"""
🎬 **Video Analizado**

📝 **Información:**
• Duración: {int(video_info['duration'] // 60)}:{(video_info['duration'] % 60):02.0f}
• Resolución: {video_info['width']}x{video_info['height']}
• Codec: {video_info['codec']}
• Tamaño: {compressor.format_size(video_info['size'])}

🔧 **Selecciona nivel de compresión:**
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🟢 Alta", callback_data=f"compress_{user_id}_alta"),
                InlineKeyboardButton("🟡 Media", callback_data=f"compress_{user_id}_media"),
                InlineKeyboardButton("🔴 Baja", callback_data=f"compress_{user_id}_baja")
            ],
            [InlineKeyboardButton("❌ Cancelar", callback_data=f"cancel_{user_id}")]
        ])
        
        await status_msg.edit_text(
            info_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error manejando video: {e}")
        if user_id in compressor.processing:
            del compressor.processing[user_id]
        await message.reply_text(f"❌ Error: {str(e)}")

@app.on_callback_query()
async def handle_callback(client: Client, callback_query):
    """Maneja callbacks de los botones"""
    try:
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        if data.startswith("compress_"):
            _, callback_user_id, quality = data.split("_")
            callback_user_id = int(callback_user_id)
            
            if user_id != callback_user_id:
                await callback_query.answer("❌ Este menú no es para ti.", show_alert=True)
                return
            
            await callback_query.message.edit_text(f"⚙️ **Comprimiendo con calidad {quality}...**")
            
            # Encontrar el archivo de entrada
            input_pattern = f"input_{user_id}_*"
            import glob
            input_files = glob.glob(os.path.join(WORK_DIR, input_pattern))
            
            if not input_files:
                await callback_query.message.edit_text("❌ No se encontró el archivo original.")
                del compressor.processing[user_id]
                return
            
            input_path = input_files[0]
            output_path = os.path.join(COMPRESSED_DIR, f"compressed_{user_id}_{quality}.mp4")
            
            # Comprimir video
            success, result_text = await compressor.compress_video(input_path, output_path, quality)
            
            if success:
                # Enviar video comprimido
                await callback_query.message.edit_text("📤 **Enviando video comprimido...**")
                
                await client.send_video(
                    chat_id=user_id,
                    video=output_path,
                    caption=result_text,
                    parse_mode=ParseMode.MARKDOWN,
                    progress=self.progress_callback,
                    progress_args=(callback_query.message, "enviando")
                )
                
                await callback_query.message.delete()
            else:
                await callback_query.message.edit_text(result_text)
            
            # Limpiar archivos
            compressor.cleanup_files(input_path, output_path)
            del compressor.processing[user_id]
            
        elif data.startswith("cancel_"):
            _, callback_user_id = data.split("_")
            callback_user_id = int(callback_user_id)
            
            if user_id != callback_user_id:
                await callback_query.answer("❌ Este menú no es para ti.", show_alert=True)
                return
            
            # Limpiar archivos
            input_pattern = f"input_{user_id}_*"
            import glob
            input_files = glob.glob(os.path.join(WORK_DIR, input_pattern))
            
            for file_path in input_files:
                compressor.cleanup_files(file_path)
            
            if user_id in compressor.processing:
                del compressor.processing[user_id]
            
            await callback_query.message.edit_text("❌ **Compresión cancelada.**")
            await callback_query.answer("Compresión cancelada")
            
        elif data == "compress_info":
            await callback_query.answer()
            await callback_query.message.reply_text(
                "📤 **Para comprimir un video:**\n\n"
                "Simplemente envía el video que deseas comprimir y "
                "selecciona el nivel de compresión que prefieras.",
                parse_mode=ParseMode.MARKDOWN
            )
            
    except Exception as e:
        logger.error(f"Error en callback: {e}")
        await callback_query.message.edit_text(f"❌ Error: {str(e)}")
        if user_id in compressor.processing:
            del compressor.processing[user_id]

    async def progress_callback(self, current: int, total: int, message: Message, action: str):
        """Callback para mostrar progreso de descarga/subida"""
        try:
            percentage = (current / total) * 100
            
            # Actualizar cada 5% o cada 5MB
            if current % max(5 * 1024 * 1024, total // 20) == 0 or current == total:
                progress_bar = self.create_progress_bar(percentage)
                
                await message.edit_text(
                    f"⏳ **{action.capitalize()}...**\n"
                    f"{progress_bar} {percentage:.1f}%\n"
                    f"📦 {self.format_size(current)} / {self.format_size(total)}",
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            logger.error(f"Error en progress_callback: {e}")

    def create_progress_bar(self, percentage: float) -> str:
        """Crea una barra de progreso visual"""
        bar_length = 10
        filled_length = int(bar_length * percentage // 100)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        return f"[{bar}]"

# ==================== MAIN ====================

async def main():
    """Función principal"""
    logger.info("🚀 Iniciando Video Compressor Bot...")
    
    # Verificar dependencias
    try:
        import subprocess
        # Verificar si FFmpeg está instalado
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        logger.info("✅ FFmpeg encontrado")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("❌ FFmpeg no encontrado. Instálalo con: apt-get install ffmpeg")
        return
    
    # Iniciar el bot
    await app.start()
    logger.info("🤖 Bot iniciado correctamente")
    
    # Obtener información del bot
    me = await app.get_me()
    logger.info(f"✅ Conectado como: @{me.username}")
    logger.info(f"🆔 ID del bot: {me.id}")
    
    # Mantener el bot corriendo
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot detenido por el usuario")
    except Exception as e:
        logger.error(f"❌ Error crítico: {e}")
    finally:
        # Limpiar archivos temporales al salir
        logger.info("🧹 Limpiando archivos temporales...")
        import shutil
        if os.path.exists(WORK_DIR):
            shutil.rmtree(WORK_DIR)
        if os.path.exists(COMPRESSED_DIR):
            shutil.rmtree(COMPRESSED_DIR)
        logger.info("✅ Limpieza completada")
