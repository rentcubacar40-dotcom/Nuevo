from flask import Flask, request
import requests
import os
import platform
import socket
import datetime

app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}"

def send_message(chat_id, text):
    try:
        requests.post(
            f"{API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        )
    except:
        pass  # Error silencioso para producción

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "").lower()

        if text == "/start":
            send_message(chat_id, "🤖 Bot de Choreo activo\nUsa /info para ver datos del host")

        elif text == "/info":
            send_message(chat_id, get_host_info())

    return "ok", 200

def get_host_info():
    try:
        hostname = socket.gethostname()
        system = platform.system()
        release = platform.release()
        
        # Información básica del contenedor Choreo
        info = (
            "🖥️ *Información del Host Choreo*\n"
            f"• Hostname: `{hostname}`\n"
            f"• Sistema: `{system} {release}`\n"
            f"• Arquitectura: `{platform.machine()}`\n"
            f"• Python: `{platform.python_version()}`\n"
            f"• Timestamp: `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        )
        return info
    except Exception as e:
        return f"❌ Error obteniendo info: {str(e)}"

@app.route("/", methods=["GET"])
def home():
    return "Bot de Telegram funcionando en Choreo", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
