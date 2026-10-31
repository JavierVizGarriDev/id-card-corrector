"""Web implementation of the UserInterface protocol."""

import threading
import time
import webbrowser
from typing import Any
import os
import subprocess
import urllib.request
import urllib.error

import numpy as np
import uvicorn

from id_card_corrector.geometry import Issue
from id_card_corrector.ui.interface import UserInterface
from id_card_corrector.ui.web import server


class WebInterface:
    """Concrete implementation of UserInterface using a local web browser."""

    def __init__(self, port: int = 8000):
        self.port = port
        self._event = threading.Event()
        self._server_started = False
        self._browser_opened = False  # <--- Arreglo 1: Control de pestañas

    def _start_server(self) -> None:
        """Start the FastAPI server in a background thread (once)."""
        if self._server_started:
            return

        def run_server():
            uvicorn.run(server.app, host="127.0.0.1", port=self.port, log_level="error")

        threading.Thread(target=run_server, daemon=True).start()
        time.sleep(1.5)
        self._server_started = True

        subprocess.Popen("npm run dev", cwd="frontend", shell=True)

    def _wait_for_vite(self, url: str, retries: int = 3, delay: int = 2) -> None:
        """Hace peticiones a Vite hasta que responda o se agoten los reintentos."""
        for intento in range(retries):
            try:
                # Intentamos abrir la URL. Si Vite está vivo, no lanzará error.
                urllib.request.urlopen(url)
                return  # ¡Éxito! Salimos de la función.
            except urllib.error.URLError:
                print(f"Vite aún no responde. Reintentando en {delay}s... ({intento + 1}/{retries})")
                time.sleep(delay)
        
        # Si el bucle termina sin haber hecho 'return', es que fallaron todos los intentos
        raise ConnectionError(f"No se pudo conectar con Vite en {url} tras {retries} intentos.")

    def _wait_for_action(self, task_name: str, image: np.ndarray | None = None, prompt: str = "") -> dict[str, Any]:
        """Block the pipeline until the web UI sends an action."""
        self._start_server()
        
        server.state.current_task = task_name
        server.state.prompt_text = prompt
        if image is not None:
            server.set_image_for_display(image)
        else:
            server.state.image_b64 = ""
            server.state.image_version += 1

        server.adapter_event = self._event
        server.adapter_result = {}
        self._event.clear()
        
        # <--- Arreglo 2: Abrir el navegador apuntando a Vite (5173)
        if not self._browser_opened:
            vite_url = "http://localhost:5173"
            self._wait_for_vite(vite_url) # Espera activa con reintentos
            webbrowser.open(vite_url)
            self._browser_opened = True
            
        success = self._event.wait(timeout=1800)
        if not success:
            raise TimeoutError("The web UI timed out waiting for user action.")
        
        return server.adapter_result

    # --- Métodos del Protocolo (con textos guía) ---

    def select_corners(self, image: np.ndarray) -> np.ndarray:
        prompt = "Haz clic en las 4 esquinas del carnet (Sup. Izq, Sup. Der, Inf. Der, Inf. Izq)"
        result = self._wait_for_action("select_corners", image=image, prompt=prompt)
        return np.array(result.get("corners", []), dtype=np.float32)

    def preview_sheet(self, sheet: np.ndarray) -> str:
        prompt = "Revisa la hoja generada. Puedes confirmar, intercambiar (S) o cancelar (ESC)."
        result = self._wait_for_action("preview_sheet", image=sheet, prompt=prompt)
        return str(result.get("action", "cancel"))

    def show_issues(self, issues: tuple[Issue, ...]) -> str:
        issue_messages = {
            Issue.SELF_INTERSECTING: "Las esquinas están en orden incorrecto.",
            Issue.EXTREME_ASPECT_RATIO: "La selección es demasiado alargada.",
            Issue.TINY_SIDE: "Uno de los lados es demasiado pequeño.",
        }
        messages = "Problemas detectados:\n" + "\n".join([issue_messages.get(i, str(i)) for i in issues])
        result = self._wait_for_action("show_issues", prompt=messages)
        return str(result.get("action", "restart"))

    def show_error(self, message: str) -> None:
        self._wait_for_action("show_error", prompt=f"Error: {message}")

    def notify(self, message: str) -> None:
        print(message)

    def show_pdf_success(self, path: str) -> None:
        prompt = f"¡PDF generado exitosamente!\nRuta: {path}\n\nEl archivo se abrirá en tu visor."
        self._wait_for_action("show_success", prompt=prompt)
        try:
            os.startfile(path)
        except Exception as e:
            print(f"No se pudo abrir el PDF: {e}")