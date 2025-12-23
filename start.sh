mkdir server
mkdir -p /tmp/video_bot
#python3 -m http.server -d server &
python3 bot.py

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
