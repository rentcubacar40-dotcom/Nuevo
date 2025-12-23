FROM python:3.11-slim-bullseye

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos de dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Crear directorios necesarios
RUN mkdir -p workdir compressed logs

# ⚠️ CRÍTICO: Exponer el puerto que Render asignará dinámicamente.
# La variable $PORT se inyectará en tiempo de ejecución.
EXPOSE ${PORT:-8080}

# Health check: usar el puerto dinámico $PORT, no un puerto fijo.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8080}/ || exit 1

# Comando de inicio
CMD ["python", "bot.py"]
