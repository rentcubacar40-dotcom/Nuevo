#!/bin/bash

echo "🚀 Video Compression Bot Pro - Iniciando..."

# Verificar dependencias
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python3 no está instalado"
    exit 1
fi

if ! command -v ffmpeg &> /dev/null; then
    echo "❌ Error: FFmpeg no está instalado"
    exit 1
fi

echo "✅ Dependencias verificadas"

# Crear directorios
mkdir -p /tmp/video_bot_pro/uploads /tmp/video_bot_pro/output

# Iniciar la aplicación
echo "🤖 Iniciando bot principal..."
exec python3 bot.py
