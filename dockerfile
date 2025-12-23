# =========================
# ARCHIVO: Dockerfile
# =========================

# Imagen base estable (NO uses Python 3.13)
FROM python:3.10-slim

# Evitar prompts interactivos
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema (FFmpeg)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar archivos del proyecto
COPY . .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Crear carpeta de descargas
RUN mkdir -p downloads

# Comando de inicio
CMD ["python", "bot.py"]
