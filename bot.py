import os
import logging
import requests
import time

# Configuración básica de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("🔍 INICIANDO DIAGNÓSTICO CHOREO WORKER")
    
    # 1. Verificar variable de entorno
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("❌ TELEGRAM_TOKEN NO CONFIGURADO")
        return
    
    logger.info(f"✅ TELEGRAM_TOKEN: {token[:10]}...")
    
    # 2. Verificar conexión a internet
    try:
        response = requests.get("https://httpbin.org/get", timeout=10)
        logger.info("✅ Conexión a internet: OK")
    except Exception as e:
        logger.error(f"❌ Sin conexión a internet: {e}")
        return
    
    # 3. Verificar conexión a Telegram
    try:
        api_url = f"https://api.telegram.org/bot{token}/getMe"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            bot_info = response.json()
            logger.info(f"✅ Conexión Telegram: OK - @{bot_info['result']['username']}")
        else:
            logger.error(f"❌ Error Telegram API: {response.status_code} - {response.text}")
            return
            
    except Exception as e:
        logger.error(f"❌ Error conectando a Telegram: {e}")
        return
    
    # 4. Probar polling simple
    logger.info("🔄 Probando polling...")
    offset = None
    
    for i in range(5):  # Solo 5 intentos para prueba
        try:
            params = {"timeout": 10, "offset": offset}
            response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    updates = data.get("result", [])
                    logger.info(f"📥 Ciclo {i+1}: {len(updates)} mensajes")
                    
                    if updates:
                        for update in updates:
                            logger.info(f"📩 Mensaje: {update}")
                            offset = update["update_id"] + 1
                else:
                    logger.error(f"❌ Telegram error: {data}")
            else:
                logger.error(f"❌ HTTP error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Error en polling: {e}")
        
        time.sleep(2)
    
    logger.info("🏁 Diagnóstico completado")

if __name__ == "__main__":
    main()
