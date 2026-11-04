"""FastAPI server for the Web UI."""

import base64
import threading
from typing import Any
import sys
import os

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import cv2
import numpy as np
from fastapi import FastAPI

from pydantic import BaseModel

# --- Estado de la sesión ---
class SessionState:
    def __init__(self):
        self.current_task: str = "idle"
        self.image_b64: str = ""
        self.prompt_text: str = ""
        self.image_version: int = 0

state = SessionState()

# --- Puente de sincronización con el Adaptador ---
adapter_event: threading.Event | None = None
adapter_result: dict[str, Any] = {}

class ActionRequest(BaseModel):
    action: str
    corners: list[list[float]] | None = None

# --- Aplicación FastAPI ---
app = FastAPI(title="ID Card Corrector Web UI")

@app.get("/api/state")
async def get_state():
    """Devuelve solo datos ligeros, sin la imagen."""
    return {
        "task": state.current_task,
        "prompt": state.prompt_text,
        "image_version": state.image_version,
    }

@app.get("/api/image")
async def get_image():
    """Devuelve la imagen pesada (solo cuando el JS la pide)."""
    return {"image_b64": state.image_b64}

@app.post("/api/action")
async def post_action(request: ActionRequest):
    """Recibe acciones del navegador y despierta al Adaptador."""
    global adapter_event, adapter_result
    
    adapter_result = request.model_dump()
    if adapter_event is not None:
        adapter_event.set()
    
    return {"status": "ok"}

def set_image_for_display(image: np.ndarray) -> None:
    """Convierte la imagen de OpenCV a Base64 para el navegador."""
    # Al quitar el cvtColor, pasamos la imagen BGR directamente, que es lo que imencode espera.
    success, buffer = cv2.imencode(".png", image)
    if success:
        state.image_b64 = base64.b64encode(buffer).decode("utf-8")
        state.image_version += 1
    else:
        state.image_b64 = ""

# --- Configuración para producción / PyInstaller ---
# Detecta si estamos ejecutando el .exe empaquetado o el código fuente
if getattr(sys, 'frozen', False):
    # Ruta donde PyInstaller descomprime los archivos (ej. .../_MEIPASS/frontend/dist)
    base_dir = sys._MEIPASS
else:
    # Ruta relativa desde src/id_card_corrector/ui/web/server.py hasta frontend/dist
    base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")

frontend_dist = os.path.join(base_dir, "frontend", "frontend_dist")

# Solo montamos si la carpeta existe (evita errores si se ejecuta en modo dev sin build)
if os.path.isdir(frontend_dist):
    # 1. Monta los assets (JS, CSS) para que el navegador los cargue
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    # 2. Ruta "catch-all" para servir el index.html en cualquier otra ruta (SPA)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Si la ruta solicitada es un archivo existente (ej. favicon), lo devuelve
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # Si no, devuelve el index.html para que Vue maneje la ruta
        return FileResponse(os.path.join(frontend_dist, "index.html"))