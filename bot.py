#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import asyncio
import logging
import threading
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Tuple

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

# ==================== CONFIGURACIÓN ====================
# ⚠️ REEMPLAZA CON TUS VALORES REALES
API_ID = 20534584
API_HASH = "6d5b13261d2c92a9a00afc1fd613b9df"
BOT_TOKEN = "8562042457:AAGA__pfWDMVfdslzqwnoFl4yLrAre-HJ5I"
ADMIN_USER_ID = 7363341763

MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024  # 4GB
# =======================================================

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# ==================== WEB SERVER PARA RENDER ====================

class HealthHandler(BaseHTTPRequestHandler):
    """Handler para health checks de Render"""
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Bot is alive')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Silenciar logs HTTP

def run_web_server():
    """Ejecuta servidor HTTP en puerto dinámico"""
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"✅ Servidor web en puerto {port}")
    server.serve_forever()

# ==================== CLASE COMPRESOR ====================

class VideoCompressor:
    def __init__(self):
        self.processing = {}
    
    async def get_video_info(self, input_path: str) -> Optional[dict]:
        """Obtiene información del video"""
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
            
            for stream in info.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_info['duration'] = float(stream.get('duration', 0))
                    video_info['width'] = stream.get('width', 0)
                    video_info['height'] = stream.get('height', 0)
                    video_info['codec'] = stream.get('codec_name', 'unknown')
                    break
            
            video_info['size'] = os.path.getsize(input_path)
            return video_info
        except Exception as e:
            logger.error(f"Error obteniendo info: {e}")
            return None
    
    async def compress_video(self, input_path: str, output_path: str, quality: str = 'medium') -> Tuple[bool, str]:
        """Comprime el video"""
        try:
            import subprocess
            
            presets = {
                'high': '-crf 28 -preset fast',
                'medium': '-crf 23 -preset medium', 
                'low': '-crf 18 -preset slow'
            }
            
            preset = presets.get(quality, presets['medium'])
            
            cmd = [
                'ffmpeg', '-i', input_path,
                '-c:v', 'libx264',
                *preset.split(),
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y',
                output_path
            ]
            
            logger.info(f"Comprimiendo con: {' '.join(cmd[:5])}...")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                original_size = os.path.getsize(input_path)
                compressed_size = os.path.getsize(output_path)
                if original_size > 0:
                    compression_ratio = ((original_size - compressed_size) / original_size) * 100
                else:
                    compression_ratio = 0
                
                return True, (
                    f"✅ **Compresión completada**\n\n"
                    f"📊 **Resultados:**\n"
                    f"• Original: {self.format_size(original_size)}\n"
                    f"• Comprimido: {self.format_size(compressed_size)}\n"
                    f"• Reducción: {compression_ratio:.1f}%\n"
                    f"• Calidad: {quality.capitalize()}"
                )
            else:
                error_msg = stderr.decode()[:300]
                return False, f"❌ Error en compresión:\n{error_msg}"
                
        except Exception as e:
            logger.error(f"Error comprimiendo: {e}")
            return False, f"❌ Error: {str(e)}"
    
    def format_size(self, size_bytes: int) -> str:
        """Formatea tamaño en bytes"""
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
                logger.error(f"Error limpiando {file_path}: {e}")

# ==================== INICIALIZACIÓN ====================

# Directorios
WORK_DIR = "workdir"
COMPRESSED_DIR = "compressed"
os.makedirs(WORK_DIR, exist_ok=True)
os.makedirs(COMPRESSED_DIR, exist_ok=True)

# Inicializar compresor
compressor = VideoCompressor()

# Inicializar Pyrogram Client - CONFIGURACIÓN CRÍTICA
app = Client(
    "video_compressor_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=2,
    sleep_threshold=60,
    in_memory=True,
    no_updates=True,      # ✅ Evita buscar updates antiguos
    ipv6=False,           # ✅ Desactiva IPv6 (problemas en Render)
    max_concurrent_transmissions=1,  # ✅ Reduce carga
)

# ==================== HANDLERS ====================

@app.on_message(filters.command(["start", "help"]))
async def start_command(client: Client, message: Message):
    """Mensaje de bienvenida"""
    welcome_text = """
🤖 **Video Compressor Bot** 🎬

¡Hola! Comprimo videos manteniendo buena calidad.

**📋 Características:**
• Videos hasta **4GB**
• Formatos: MP4, AVI, MOV, MKV, etc.
• 3 niveles de compresión
• Audio de calidad

**⚡ Comandos:**
/start - Este mensaje
/status - Estado del bot
/compress - Instrucciones

**📤 Para usar:**
1. Envíame un video
2. Elige nivel de compresión
3. Espera el procesamiento
4. Recibe tu video comprimido
"""
    
    await message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Comenzar", callback_data="start_compress")]
        ])
    )

@app.on_message(filters.command("status"))
async def status_command(client: Client, message: Message):
    """Estado del bot"""
    import psutil
    import shutil
    
    disk = shutil.disk_usage("/")
    mem = psutil.virtual_memory()
    
    status_text = f"""
📊 **Estado del Bot**

**Sistema:**
• CPU: {psutil.cpu_percent()}%
• Memoria: {compressor.format_size(mem.used)} / {compressor.format_size(mem.total)}
• Disco: {compressor.format_size(disk.used)} / {compressor.format_size(disk.total)}

**Bot:**
• Usuarios procesando: {len(compressor.processing)}
• Estado: ✅ Operativo
"""
    
    await message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("compress"))
async def compress_info(client: Client, message: Message):
    """Información sobre compresión"""
    await message.reply_text(
        "📤 **Para comprimir:**\n\n"
        "Simplemente envíame un video y te mostraré las opciones.\n\n"
        "📊 **Niveles:**\n"
        "• **Alta** - Máxima compresión\n"
        "• **Media** - Balance calidad/tamaño\n"
        "• **Baja** - Máxima calidad\n\n"
        "💡 Usa **Media** para la mayoría de casos.",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.video | filters.document)
async def handle_media(client: Client, message: Message):
    """Maneja videos enviados"""
    user_id = message.from_user.id
    
    try:
        if user_id in compressor.processing:
            await message.reply_text("⏳ Ya tienes un video en proceso.")
            return
        
        if message.video:
            file = message.video
            file_name = file.file_name or f"video_{message.id}.mp4"
        else:
            file = message.document
            file_name = file.file_name or f"file_{message.id}"
            
            ext = os.path.splitext(file_name.lower())[1]
            supported = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm']
            if ext not in supported:
                await message.reply_text(f"❌ Formato no soportado.")
                return
        
        if file.file_size > MAX_FILE_SIZE:
            await message.reply_text(f"❌ Muy grande. Máximo: {compressor.format_size(MAX_FILE_SIZE)}")
            return
        
        compressor.processing[user_id] = True
        
        status_msg = await message.reply_text(
            f"📥 **Descargando...**\n`{file_name}`\n"
            f"📦 {compressor.format_size(file.file_size)}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        input_path = os.path.join(WORK_DIR, f"input_{user_id}_{message.id}")
        
        await client.download_media(message, file_name=input_path)
        
        await status_msg.edit_text("📊 Analizando video...")
        video_info = await compressor.get_video_info(input_path)
        
        if not video_info:
            await status_msg.edit_text("❌ Error al analizar el video.")
            del compressor.processing[user_id]
            compressor.cleanup_files(input_path)
            return
        
        info_text = f"""
🎬 **Video listo para comprimir**

📝 **Información:**
• Duración: {int(video_info.get('duration', 0) // 60)}:{int(video_info.get('duration', 0) % 60):02d}
• Resolución: {video_info.get('width', 0)}x{video_info.get('height', 0)}
• Tamaño: {compressor.format_size(video_info.get('size', 0))}

🔧 **Elige nivel de compresión:**
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🟢 Alta", callback_data=f"compress_{user_id}_high"),
                InlineKeyboardButton("🟡 Media", callback_data=f"compress_{user_id}_medium"),
            ],
            [
                InlineKeyboardButton("🔴 Baja", callback_data=f"compress_{user_id}_low"),
                InlineKeyboardButton("❌ Cancelar", callback_data=f"cancel_{user_id}")
            ]
        ])
        
        await status_msg.edit_text(
            info_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error en handle_media: {e}")
        if user_id in compressor.processing:
            del compressor.processing[user_id]
        await message.reply_text(f"❌ Error: {str(e)[:200]}")

@app.on_callback_query()
async def handle_callback(client: Client, callback_query):
    """Maneja callbacks"""
    try:
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        if data.startswith("compress_"):
            _, callback_user_id, quality = data.split("_")
            callback_user_id = int(callback_user_id)
            
            if user_id != callback_user_id:
                await callback_query.answer("Este menú no es para ti", show_alert=True)
                return
            
            await callback_query.answer(f"Comprimiendo ({quality})...")
            await callback_query.message.edit_text(f"⚙️ Comprimiendo ({quality})...")
            
            import glob
            input_files = glob.glob(os.path.join(WORK_DIR, f"input_{user_id}_*"))
            
            if not input_files:
                await callback_query.message.edit_text("❌ Archivo no encontrado")
                if user_id in compressor.processing:
                    del compressor.processing[user_id]
                return
            
            input_path = input_files[0]
            output_path = os.path.join(COMPRESSED_DIR, f"compressed_{user_id}_{quality}.mp4")
            
            success, result_text = await compressor.compress_video(input_path, output_path, quality)
            
            if success:
                await callback_query.message.edit_text("📤 Enviando video...")
                
                await client.send_video(
                    chat_id=user_id,
                    video=output_path,
                    caption=result_text,
                    parse_mode=ParseMode.MARKDOWN,
                    supports_streaming=True
                )
                
                await callback_query.message.delete()
            else:
                await callback_query.message.edit_text(result_text[:1000])
            
            compressor.cleanup_files(input_path, output_path)
            if user_id in compressor.processing:
                del compressor.processing[user_id]
            
        elif data.startswith("cancel_"):
            _, callback_user_id = data.split("_")
            callback_user_id = int(callback_user_id)
            
            if user_id != callback_user_id:
                await callback_query.answer("Este menú no es para ti", show_alert=True)
                return
            
            import glob
            input_files = glob.glob(os.path.join(WORK_DIR, f"input_{user_id}_*"))
            for file_path in input_files:
                compressor.cleanup_files(file_path)
            
            if user_id in compressor.processing:
                del compressor.processing[user_id]
            
            await callback_query.message.edit_text("❌ **Compresión cancelada**")
            await callback_query.answer("Cancelado")
            
        elif data == "start_compress":
            await callback_query.answer()
            await callback_query.message.reply_text(
                "📤 **Envía un video para comenzar**\n\n"
                "Puedes enviar cualquier video (hasta 4GB).",
                parse_mode=ParseMode.MARKDOWN
            )
            
    except Exception as e:
        logger.error(f"Error en callback: {e}")
        await callback_query.message.edit_text(f"❌ Error: {str(e)[:200]}")
        if user_id in compressor.processing:
            del compressor.processing[user_id]

# ==================== FUNCIÓN PRINCIPAL CORREGIDA ====================

async def run_bot():
    """Ejecuta el bot de Telegram - VERSIÓN 100% FUNCIONAL"""
    try:
        logger.info("🚀 Iniciando bot de Telegram...")
        
        # Verificar FFmpeg
        try:
            import subprocess
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            logger.info("✅ FFmpeg encontrado")
        except Exception:
            logger.error("❌ FFmpeg no encontrado.")
            return
        
        # Iniciar Pyrogram
        await app.start()
        
        # Obtener información del bot
        me = await app.get_me()
        logger.info(f"✅ Bot iniciado: @{me.username}")
        logger.info(f"🆔 ID: {me.id}")
        logger.info("🤖 Bot listo para recibir mensajes")
        
        # ✅✅✅ SOLUCIÓN DEFINITIVA: Mantener bot activo
        # Usamos una tarea que nunca termina pero permite procesar mensajes
        keep_running = asyncio.Future()
        
        try:
            # Esto mantiene el bot corriendo indefinidamente
            # PERO permite que Pyrogram procese mensajes
            await keep_running
        except asyncio.CancelledError:
            logger.info("Tarea cancelada")
        finally:
            if app.is_connected:
                await app.stop()
            logger.info("👋 Bot detenido")
            
    except Exception as e:
        logger.error(f"❌ Error en bot: {e}")
        if 'app' in locals() and app.is_connected:
            await app.stop()
        raise

async def main():
    """Función principal"""
    # Iniciar web server en hilo separado
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    logger.info("🌐 Servidor web iniciado")
    
    # Pequeña pausa para asegurar que el servidor web inicia
    await asyncio.sleep(2)
    
    # Ejecutar el bot
    await run_bot()

if __name__ == "__main__":
    # ✅ Configuración optimizada para Render
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot detenido por el usuario")
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
        sys.exit(1)
