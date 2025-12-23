FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements primero (para caching de capas)
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY bot.py .
COPY start.sh .

# Hacer ejecutable el script
RUN chmod +x start.sh

# Crear directorios necesarios
RUN mkdir -p /tmp/video_bot_pro/uploads /tmp/video_bot_pro/output

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=10000

# Exponer puerto
EXPOSE 10000

# Comando de inicio
CMD ["./start.sh"]
