"""OpenCV implementation of the UserInterface protocol."""

import os
from typing import Any

import cv2
import numpy as np

from id_card_corrector.geometry import Issue
from id_card_corrector.ui.interface import UserInterface
from .preview import preview_sheet
from .selector import select_corners, _show_issues_panel


class OpenCVInterface:
    """Concrete implementation of UserInterface using OpenCV HighGUI."""

    def select_corners(self, image: np.ndarray) -> np.ndarray:
        """Display the image and let the user select 4 corners."""
        return select_corners(image)

    def preview_sheet(self, sheet: np.ndarray) -> str:
        """Show the composed sheet and wait for confirm/swap/cancel."""
        return preview_sheet(sheet)

    def show_issues(self, issues: tuple[Issue, ...]) -> str:
        """Show non-fatal issues and wait for confirm/restart."""
        # Create a dummy black image to display the panel
        dummy = np.zeros((768, 1024, 3), dtype=np.uint8)
        return _show_issues_panel(dummy, issues)

    def show_error(self, message: str) -> None:
        """Show a fatal error message."""
        dummy = np.zeros((600, 800, 3), dtype=np.uint8)
        cv2.putText(
            dummy, message, (50, 300), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA
        )
        cv2.imshow("Error", dummy)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def notify(self, message: str) -> None:
        """Show a simple informational message."""
        print(message)

    def ask_open_pdf(self, path: str) -> bool:
        """Ask the user if they want to open the generated PDF."""
        ans = input(f"\n¿Abrir el PDF generado ahora ({path})? (S/n): ").strip().lower()
        return ans in ("", "s", "si", "y", "yes")
    