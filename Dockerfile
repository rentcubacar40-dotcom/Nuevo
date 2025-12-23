FROM python:3.11-slim-bullseye

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    gnupg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no root para seguridad
RUN useradd -m -u 1000 -s /bin/bash botuser
USER botuser

# Establecer directorio de trabajo
WORKDIR /home/botuser/app

# Copiar archivos de dependencias
COPY --chown=botuser:botuser requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir --user -r requirements.txt

# Agregar Python user bin al PATH
ENV PATH="/home/botuser/.local/bin:${PATH}"

# Copiar código fuente
COPY --chown=botuser:botuser . .

# Crear directorios necesarios
RUN mkdir -p workdir compressed logs

# Puerto para Render (requerido para health checks)
EXPOSE 8080

# Health check para Render
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(2); result = s.connect_ex(('localhost', 8080)); s.close(); exit(result == 0)"

# Comando de inicio con gunicorn para mantener el servicio web activo
CMD ["sh", "-c", "python -m http.server 8080 & python bot.py"]
