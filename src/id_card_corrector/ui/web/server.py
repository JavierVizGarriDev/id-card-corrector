"""FastAPI server for the Web UI - Island 1."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="ID Card Corrector - Test")

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <head><title>Test</title></head>
        <body style="font-family: sans-serif; padding: 2rem;">
            <h1>¡Servidor FastAPI funcionando!</h1>
            <p>Si ves esto en el navegador, la Isla 1 está completa.</p>
        </body>
    </html>
    """