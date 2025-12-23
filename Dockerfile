FROM python:3.11-slim

# Instalar FFmpeg (CRÍTICO para tu bot)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Crear directorios necesarios
RUN mkdir -p /tmp/video_bot

# Puerto expuesto (Render inyecta la variable PORT)
EXPOSE 10000

# Comando de inicio DIRECTO
CMD ["python", "bot.py"]
