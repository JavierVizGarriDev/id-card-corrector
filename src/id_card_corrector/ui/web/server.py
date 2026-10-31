"""FastAPI server for the Web UI."""

import base64
import threading
from typing import Any

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