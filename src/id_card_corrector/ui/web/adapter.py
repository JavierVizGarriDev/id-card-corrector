"""Web implementation of the UserInterface protocol."""

import threading
import time
import webbrowser
from typing import Any

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

    def _start_server(self) -> None:
        """Start the FastAPI server in a background thread (once)."""
        if self._server_started:
            return

        def run_server():
            # Desactivamos los logs de Uvicorn para no ensuciar la consola
            uvicorn.run(server.app, host="127.0.0.1", port=self.port, log_level="error")

        threading.Thread(target=run_server, daemon=True).start()
        time.sleep(1.5)  # Dar tiempo a Uvicorn para arrancar
        self._server_started = True

    def _wait_for_action(self, task_name: str, image: np.ndarray | None = None, prompt: str = "") -> dict[str, Any]:
        """Block the pipeline until the web UI sends an action."""
        self._start_server()
        
        # 1. Configurar el estado para el navegador
        server.state.current_task = task_name
        server.state.prompt_text = prompt
        if image is not None:
            server.set_image_for_display(image)
        else:
            server.state.image_b64 = ""
            server.state.image_version += 1

        # 2. Preparar el Evento y abrir el navegador
        server.adapter_event = self._event
        server.adapter_result = {}
        self._event.clear()
        webbrowser.open(f"http://127.0.0.1:{self.port}")

        # 3. Bloquear Python hasta que el servidor reciba la acción (timeout 30 min)
        success = self._event.wait(timeout=1800)
        if not success:
            raise TimeoutError("The web UI timed out waiting for user action.")
        
        return server.adapter_result

    # --- Métodos del Protocolo ---

    def select_corners(self, image: np.ndarray) -> np.ndarray:
        result = self._wait_for_action("select_corners", image)
        return np.array(result.get("corners", []), dtype=np.float32)

    def preview_sheet(self, sheet: np.ndarray) -> str:
        result = self._wait_for_action("preview_sheet", sheet)
        return str(result.get("action", "cancel"))

    def show_issues(self, issues: tuple[Issue, ...]) -> str:
        issue_messages = {
            Issue.SELF_INTERSECTING: "Las esquinas están en orden incorrecto.",
            Issue.EXTREME_ASPECT_RATIO: "La selección es demasiado alargada.",
            Issue.TINY_SIDE: "Uno de los lados es demasiado pequeño.",
        }
        messages = "\n".join([issue_messages.get(i, str(i)) for i in issues])
        result = self._wait_for_action("show_issues", prompt=messages)
        return str(result.get("action", "restart"))

    def show_error(self, message: str) -> None:
        self._wait_for_action("show_error", prompt=message)

    def notify(self, message: str) -> None:
        print(message)

    def show_pdf_success(self, path: str) -> None:
        print(f"\nPDF generado exitosamente: {path}")