#!/bin/bash

mkdir -p /tmp/video_bot

echo "Iniciando Bot de Compresión de Videos..."

# Verificar si Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python3 no está instalado"
    exit 1
fi

# Verificar si FFmpeg está instalado
if ! command -v ffmpeg &> /dev/null; then
    echo "Error: FFmpeg no está instalado"
    echo " Instala FFmpeg con: sudo apt install ffmpeg"
    exit 1
fi

echo "✅ Verificaciones completadas"
echo "🚀 Iniciando el bot..."

# Iniciar el servidor web simple en segundo plano
python3 -m http.server 8080 &

# Iniciar el bot principal
python3 bot.py
