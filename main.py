import os
import io
import socket
import base64
from datetime import datetime
from typing import List
import qrcode
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Local Cloud File Drop")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(UPLOADS_DIR, exist_ok=True)
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def get_local_ip() -> str:
    """Определение IP адреса компьютера в домашней сети Wi-Fi/LAN"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Не выполняет реальный сетевой запрос наружу, но ОС заполняет локальный IP интерфейса
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def generate_qr_base64(url: str) -> str:
    """Генерация QR-кода в формате Data URI base64"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1E1B4B", back_color="#FFFFFF")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    elif size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 1)} КБ"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{round(size_bytes / (1024 * 1024), 1)} МБ"
    else:
        return f"{round(size_bytes / (1024 ** 3), 2)} ГБ"


@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    local_ip = get_local_ip()
    port = 8005
    network_url = f"http://{local_ip}:{port}"
    qr_data = generate_qr_base64(network_url)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "local_ip": local_ip,
        "network_url": network_url,
        "qr_code": qr_data
    })


@app.get("/api/files")
async def list_files():
    files = []
    for fname in os.listdir(UPLOADS_DIR):
        fpath = os.path.join(UPLOADS_DIR, fname)
        if os.path.isfile(fpath):
            stat = os.stat(fpath)
            ext = os.path.splitext(fname)[1].lower()
            is_image = ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"]
            is_video = ext in [".mp4", ".mov", ".mkv", ".webm"]
            files.append({
                "name": fname,
                "size_raw": stat.st_size,
                "size_formatted": format_size(stat.st_size),
                "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M"),
                "is_image": is_image,
                "is_video": is_video,
                "download_url": f"/download/{fname}"
            })
    files.sort(key=lambda x: x["created_at"], reverse=True)
    return {"files": files}


@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    saved_files = []
    for file in files:
        # Очистка имени от traversal атак
        safe_name = os.path.basename(file.filename)
        dest_path = os.path.join(UPLOADS_DIR, safe_name)
        
        # Если файл уже существует, добавляем суффикс
        if os.path.exists(dest_path):
            name, ext = os.path.splitext(safe_name)
            safe_name = f"{name}_{int(datetime.now().timestamp())}{ext}"
            dest_path = os.path.join(UPLOADS_DIR, safe_name)

        with open(dest_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                f.write(chunk)
        saved_files.append(safe_name)

    return {"status": "ok", "uploaded": saved_files}


@app.get("/download/{filename}")
async def download_file(filename: str):
    safe_name = os.path.basename(filename)
    path = os.path.join(UPLOADS_DIR, safe_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path, filename=safe_name)


@app.delete("/api/files/{filename}")
async def delete_file(filename: str):
    safe_name = os.path.basename(filename)
    path = os.path.join(UPLOADS_DIR, safe_name)
    if os.path.exists(path):
        os.remove(path)
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Файл не найден")


if __name__ == "__main__":
    import uvicorn
    ip = get_local_ip()
    print("=" * 60)
    print(f"🚀 [Local Cloud Drop] Сервер запущен!")
    print(f"👉 Локально на ПК:   http://localhost:8005")
    print(f"📱 С телефона по Wi-Fi: http://{ip}:8005")
    print("=" * 60)
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=False)
