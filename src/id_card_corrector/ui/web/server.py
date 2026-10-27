"""FastAPI server for the Web UI - Island 2."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="ID Card Corrector - Test")

# Configurar la carpeta de archivos estáticos
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    return FileResponse(STATIC_DIR / "index.html")


class TestPoints(BaseModel):
    corners: list[list[float]]

@app.post("/api/test")
async def test_endpoint(data: TestPoints):
    print("\n--- ¡Coordenadas recibidas en Python! ---")
    print(data.corners)
    print("-----------------------------------------\n")
    return {"status": "ok"}