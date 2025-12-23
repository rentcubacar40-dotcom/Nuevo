# =========================
# ARCHIVO: bot.py
# =========================

import os
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import *
from utils import progress, get_video_info

app = Client(
    "premium_video_compressor",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

PRESETS = {
    "tg": ("Telegram 720p", "1280x720", "28"),
    "wa": ("WhatsApp 480p", "854x480", "30"),
    "ultra": ("Ultra Calidad", None, "23")
}

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "🎬 COMPRESOR PREMIUM 2025\n\n"
        "📤 Envíame un video (hasta 4GB)\n"
        "🎚️ Selecciona un preset profesional\n"
        "⚡ Barra de progreso real"
    )

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    media = message.video or message.document

    if media.file_size > MAX_FILE_SIZE:
        return await message.reply_text("❌ El archivo supera el límite de 4GB")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 Telegram", callback_data="tg")],
        [InlineKeyboardButton("💬 WhatsApp", callback_data="wa")],
        [InlineKeyboardButton("🎞 Ultra", callback_data="ultra")]
    ])

    message.chat.video_id = media.file_id
    await message.reply_text("🎚️ Selecciona el preset:", reply_markup=keyboard)

@app.on_callback_query()
async def compress(client, callback):
    preset = callback.data
    name, scale, crf = PRESETS[preset]

    status = await callback.message.edit_text("⬇️ Descargando video...")
    start_time = time.time()

    input_file = await client.download_media(
        callback.message.chat.video_id,
        file_name=f"{DOWNLOAD_DIR}/input.mp4",
        progress=progress,
        progress_args=(status, start_time, "⬇️ Descargando video...")
    )

    width, height = get_video_info(input_file)
    scale_filter = f"scale={scale}" if scale else "scale=iw:ih"

    output_file = f"{DOWNLOAD_DIR}/output_{preset}.mp4"

    await status.edit_text("⚙️ Comprimiendo video...")

    cmd = [
        "ffmpeg", "-y",
        "-i", input_file,
        "-vf", scale_filter,
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", crf,
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_file
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await process.communicate()

    start_time = time.time()
    await status.edit_text("⬆️ Subiendo video...")

    await client.send_video(
        callback.message.chat.id,
        output_file,
        caption=f"✅ Compresión PREMIUM completada\n🎚️ Preset: {name}",
        progress=progress,
        progress_args=(status, start_time, "⬆️ Subiendo video...")
    )

    os.remove(input_file)
    os.remove(output_file)
    await status.delete()

app.run()
