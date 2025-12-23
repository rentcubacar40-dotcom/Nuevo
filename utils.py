# =========================
# ARCHIVO: utils.py
# =========================

import time
import subprocess
import json

def human(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f}{unit}"
        size /= 1024
    return f"{size:.2f}TB"

def progress_bar(current, total):
    percent = current * 100 / total if total else 0
    filled = int(percent / 10)
    return f"[{'█'*filled}{'░'*(10-filled)}] {percent:.1f}%"

async def progress(current, total, message, start, text):
    now = time.time()
    if now - start < 1:
        return
    speed = current / (now - start) if now - start > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0

    await message.edit(
        f"{text}\n\n"
        f"{progress_bar(current, total)}\n"
        f"📦 {human(current)} / {human(total)}\n"
        f"⚡ {human(speed)}/s | ⏳ {int(eta)}s"
    )

def get_video_info(file):
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,bit_rate,r_frame_rate",
        "-of", "json", file
    ]
    data = json.loads(subprocess.check_output(cmd))
    s = data["streams"][0]
    return s["width"], s["height"]
