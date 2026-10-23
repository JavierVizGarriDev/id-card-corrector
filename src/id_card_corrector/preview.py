"""Interactive preview of the composed sheet.

This module provides a simple modal window that shows the final sheet
and waits for the user to confirm, swap the two cards, or cancel.
It is intentionally separated from `selector.py` because its purpose
is different: it does not handle state machines, just a simple key
polling loop.
"""

from typing import Final

import cv2
import numpy as np

# Reuse key codes (could also import from selector, but keeping this
# module independent avoids a dependency on selector's constants).
KEY_ENTER: Final[int] = 13
KEY_ESC: Final[int] = 27
KEY_S_LOWER: Final[int] = ord("s")
KEY_S_UPPER: Final[int] = ord("S")

WINDOW_NAME: Final[str] = "Vista Previa"


def preview_sheet(sheet: np.ndarray, max_display: int = 1200) -> str:
    """Show the composed sheet and wait for user action.

    Args:
        sheet: The full-resolution composed sheet (BGR).
        max_display: Max dimension for the window. The sheet is
            downscaled for display.

    Returns:
        "confirm" if the user presses ENTER.
        "swap" if the user presses S.
        "cancel" if the user presses ESC or closes the window.
    """
    h, w = sheet.shape[:2]

    # Scale down for display if necessary
    scale = min(1.0, max_display / max(h, w))
    if scale < 1.0:
        display_w, display_h = int(w * scale), int(h * scale)
        display = cv2.resize(
            sheet, (display_w, display_h), interpolation=cv2.INTER_AREA
        )
    else:
        display = sheet.copy()
        display_w, display_h = w, h

    # Create a banner at the bottom with instructions
    banner_h = 50
    y0 = display_h - banner_h
    overlay = display.copy()
    cv2.rectangle(overlay, (0, y0), (display_w, display_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, display, 0.4, 0, display)

    banner_text = "ENTER: Confirmar e Imprimir  |  S: Intercambiar Anverso/Reverso  |  ESC: Cancelar"
    cv2.putText(
        display,
        banner_text,
        (10, display_h - 18),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)

    try:
        while True:
            cv2.imshow(WINDOW_NAME, display)
            key = cv2.waitKey(20) & 0xFF

            # Handle window closed via the 'X' button
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                return "cancel"

            if key == KEY_ENTER:
                return "confirm"
            if key in (KEY_S_LOWER, KEY_S_UPPER):
                return "swap"
            if key == KEY_ESC:
                return "cancel"

    finally:
        cv2.destroyAllWindows()