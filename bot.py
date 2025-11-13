from flask import Flask, request
import requests
import os
import platform
import psutil
import datetime
import socket

app = Flask(__name__)

# Token del bot desde variables de entorno
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}"

# Función para enviar mensajes a Telegram
def send_message(chat_id, text):
    requests.post(
        f"{API_URL}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    )

# Webhook principal que recibe mensajes de Telegram
@app.route("/elielthali/eliel/v1.0", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "").lower()

        if text == "/start":
            send_message(chat_id, "👋 ¡Hola! Soy tu bot en Choreo 🚀\nUsa /status para ver información del servidor.")

        elif text == "/status":
            send_message(chat_id, get_server_status())

        else:
            send_message(chat_id, "🤖 No entendí tu mensaje, pero estoy activo en Choreo 😎")

    return "ok", 200

# Función que devuelve información completa del servidor
def get_server_status():
    uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time())
    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_count = psutil.cpu_count()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    try:
        ip_addr = socket.gethostbyname(socket.gethostname())
    except:
        ip_addr = "No disponible"

    # Variables de entorno públicas
    env_vars = {k:v for k,v in os.environ.items() if k.startswith("PUBLIC_") or k=="HOSTNAME"}

    info = (
        "🖥️ *Estado del servidor Choreo*\n"
        f"🏠 Hostname: `{socket.gethostname()}`\n"
        f"💻 Plataforma: `{platform.system()} {platform.release()} ({platform.machine()})`\n"
        f"⏱️ Uptime: `{str(uptime).split('.')[0]}`\n"
        f"🌐 IP contenedor: `{ip_addr}`\n"
        f"⚙️ CPU: `{cpu_percent}%` ({cpu_count} núcleos)\n"
        f"💾 Memoria: `{mem.percent}%` usada (Total: {convert_bytes(mem.total)}, Disponible: {convert_bytes(mem.available)})\n"
        f"🗄️ Disco: `{disk.percent}%` usado (Total: {convert_bytes(disk.total)}, Libre: {convert_bytes(disk.free)})\n"
        f"🔧 Variables de entorno públicas: `{env_vars}`"
    )
    return info

# Función para convertir bytes a formato legible
def convert_bytes(size):
    for unit in ['B','KB','MB','GB','TB']:
        if size < 1024.0:
            return f"{size:.2f}{unit}"
        size /= 1024.0
    return f"{size:.2f}PB"

# Endpoint GET para probar en navegador
@app.route("/", methods=["GET"])
def home():
    return "✅ Bot de Telegram en Choreo funcionando", 200

if __name__ == "__main__":
    app.run(port=8000)
