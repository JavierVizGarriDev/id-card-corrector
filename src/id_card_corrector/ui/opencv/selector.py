"""Interactive corner selection with OpenCV.

This module is split into two layers:

1. A pure state machine (`process_event`, `_validate_state`,
   `_validate_n_points`) that handles all the logic of clicks, keys,
   warnings, and confirmations. This layer is fully testable with pytest.

2. An OpenCV UI shell (`select_corners`, `_draw_*`) that creates a window,
   captures mouse and keyboard events, translates them to the state machine,
   and renders the visual feedback.

The UI layer is intentionally NOT tested in the MVP. Mocking `cv2.imshow`,
`cv2.waitKey`, and `cv2.setMouseCallback` is fragile and tightly coupled
to the OpenCV version. The valuable logic lives in `process_event`.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final

import cv2
import numpy as np

from id_card_corrector.geometry import (
    DegenerateQuadrilateralError,
    Issue,
    validate_quadrilateral,
)


# ---------------------------------------------------------------------------
# OpenCV key codes (avoid magic numbers)
# ---------------------------------------------------------------------------

KEY_ENTER: Final[int] = 13
KEY_ESC: Final[int] = 27
KEY_R_LOWER: Final[int] = ord("r")
KEY_R_UPPER: Final[int] = ord("R")


# ---------------------------------------------------------------------------
# Errors, Enums, and State
# ---------------------------------------------------------------------------

class SelectionCancelledError(ValueError):
    """The user cancelled the selection (ESC pressed twice or window closed)."""


class Phase(str, Enum):
    """The phase of the selection state machine."""
    COLLECTING = "collecting"
    READY_TO_CONFIRM = "ready"
    WARNING = "warning"
    CLOSED = "closed"


class SelectionEvent(str, Enum):
    """Events that the state machine can process."""
    CLICK = "click"
    ENTER = "enter"
    RESTART = "restart"
    CANCEL = "cancel"


class SelectionAction(str, Enum):
    """Actions that the UI layer must execute."""
    ADD_POINT = "add_point"
    RESET_POINTS = "reset"
    SHOW_WARNING = "show_warning"
    CONFIRM = "confirm"
    CLOSE_ALL = "close_all"
    NONE = "none"


@dataclass(frozen=True)
class SelectorState:
    """The immutable state of the selection process.

    `warning_return_to` is only meaningful when `phase == WARNING`.
    It records the phase to return to if the user presses ENTER to
    dismiss the warning.
    """
    phase: Phase
    warning_return_to: Phase | None = None


# ---------------------------------------------------------------------------
# Layer 1: Pure state machine
# ---------------------------------------------------------------------------

def _validate_state(state: SelectorState) -> None:
    """Validate the invariants of a SelectorState.
    
    Raises:
        ValueError: if phase is CLOSED, or if warning_return_to is
            inconsistent with phase.
    """
    if state.phase == Phase.CLOSED:
        raise ValueError("Cannot process events on a CLOSED state.")
    
    if state.phase == Phase.WARNING:
        if state.warning_return_to is None:
            raise ValueError(
                "WARNING phase requires warning_return_to to be set."
            )
        if state.warning_return_to not in (
            Phase.COLLECTING, 
            Phase.READY_TO_CONFIRM
        ):
            raise ValueError(
                f"Invalid warning_return_to: {state.warning_return_to.value}. "
                f"Must be COLLECTING or READY_TO_CONFIRM."
            )
    else:
        if state.warning_return_to is not None:
            raise ValueError(
                f"warning_return_to must be None when phase is {state.phase.value}."
            )


def _validate_n_points(state: SelectorState, n_points: int) -> None:
    """Validate that n_points is coherent with the current phase.
    
    Assumes the state has been validated by `_validate_state` and is
    therefore not CLOSED, and that `warning_return_to` (if any) is
    COLLECTING or READY_TO_CONFIRM.
    
    Raises:
        ValueError: if n_points is not valid for the current phase.
    """
    if state.phase == Phase.COLLECTING:
        if not (0 <= n_points <= 3):
            raise ValueError(
                f"COLLECTING requires 0 <= n_points <= 3, got {n_points}."
            )
    elif state.phase == Phase.READY_TO_CONFIRM:
        if n_points != 4:
            raise ValueError(
                f"READY_TO_CONFIRM requires n_points == 4, got {n_points}."
            )
    elif state.phase == Phase.WARNING:
        if state.warning_return_to == Phase.COLLECTING:
            if not (0 <= n_points <= 3):
                raise ValueError(
                    f"WARNING (returning to collecting) requires "
                    f"0 <= n_points <= 3, got {n_points}."
                )
        elif state.warning_return_to == Phase.READY_TO_CONFIRM:
            if n_points != 4:
                raise ValueError(
                    f"WARNING (returning to ready) requires "
                    f"n_points == 4, got {n_points}."
                )
    # Phase.CLOSED is unreachable here: _validate_state rejects it first.


def process_event(
    state: SelectorState,
    event: SelectionEvent,
    n_points: int,
) -> tuple[SelectorState, SelectionAction]:
    """Process a single event against the state machine.

    Args:
        state: The current state.
        event: The event to process.
        n_points: The number of points collected so far.

    Returns:
        A tuple (new_state, action_to_execute).

    Raises:
        ValueError: if state or n_points violate the invariants.
    """
    _validate_state(state)
    _validate_n_points(state, n_points)

    if state.phase == Phase.COLLECTING:
        if event == SelectionEvent.CLICK:
            if n_points < 3:
                return (
                    SelectorState(Phase.COLLECTING),
                    SelectionAction.ADD_POINT,
                )
            # n_points == 3 (validated): this click is the fourth point
            return (
                SelectorState(Phase.READY_TO_CONFIRM),
                SelectionAction.ADD_POINT,
            )
        if event == SelectionEvent.ENTER:
            return (SelectorState(Phase.COLLECTING), SelectionAction.NONE)
        if event == SelectionEvent.RESTART:
            return (SelectorState(Phase.COLLECTING), SelectionAction.RESET_POINTS)
        if event == SelectionEvent.CANCEL:
            return (
                SelectorState(Phase.WARNING, Phase.COLLECTING),
                SelectionAction.SHOW_WARNING,
            )

    elif state.phase == Phase.READY_TO_CONFIRM:
        if event == SelectionEvent.CLICK:
            return (SelectorState(Phase.READY_TO_CONFIRM), SelectionAction.NONE)
        if event == SelectionEvent.ENTER:
            return (SelectorState(Phase.CLOSED), SelectionAction.CONFIRM)
        if event == SelectionEvent.RESTART:
            return (SelectorState(Phase.COLLECTING), SelectionAction.RESET_POINTS)
        if event == SelectionEvent.CANCEL:
            return (
                SelectorState(Phase.WARNING, Phase.READY_TO_CONFIRM),
                SelectionAction.SHOW_WARNING,
            )

    elif state.phase == Phase.WARNING:
        if event == SelectionEvent.CLICK:
            # Preserve warning_return_to: we stay in WARNING.
            return (
                SelectorState(Phase.WARNING, state.warning_return_to),
                SelectionAction.NONE,
            )
        if event == SelectionEvent.ENTER:
            # Return to whichever phase we came from, clearing the marker.
            return (
                SelectorState(state.warning_return_to),
                SelectionAction.NONE,
            )
        if event == SelectionEvent.RESTART:
            return (SelectorState(Phase.COLLECTING), SelectionAction.RESET_POINTS)
        if event == SelectionEvent.CANCEL:
            return (SelectorState(Phase.CLOSED), SelectionAction.CLOSE_ALL)

    # Defensive: with all 4 phases × 4 events covered above, and CLOSED
    # rejected by _validate_state, this branch is unreachable. It exists
    # to surface future bugs if a new phase or event is added.
    raise ValueError(
        f"Unhandled state/event combination: "
        f"{state.phase.value} + {event.value}"
    )

# ---------------------------------------------------------------------------
# Layer 2: OpenCV UI shell
# ---------------------------------------------------------------------------

def _draw_banner(image: np.ndarray, text: str) -> None:
    """Draw a semi-transparent banner at the bottom of the image.
    
    Modifies `image` in place. The banner is a black rectangle at
    ~60% opacity, with white text on top. Height is fixed at 50px.
    """
    h, w = image.shape[:2]
    banner_h = 50
    y0 = h - banner_h

    # Create a copy with a black rectangle over the banner area
    overlay = image.copy()
    cv2.rectangle(overlay, (0, y0), (w, h), (0, 0, 0), thickness=-1)

    # Blend: overlay * alpha + image * (1 - alpha)
    # Inside the banner: (1-alpha) of original remains (darker)
    # Outside: (1-alpha)*image + alpha*image = image (no change)
    alpha = 0.6
    cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

    # Draw the text
    cv2.putText(
        image,
        text,
        (10, h - 18),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )

def _draw_warning_panel(image: np.ndarray) -> None:
    """Draw the warning panel over the image.
    
    Modifies `image` in place. The entire image is dimmed, and a
    centered message with the three options is drawn on top.
    """
    h, w = image.shape[:2]

    # Dim the entire image with a semi-transparent black overlay
    overlay = np.zeros_like(image)
    alpha = 0.7
    cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

    # Lines to display
    lines = [
        "¿Seguro que quieres cerrar?",
        "Se perderá el progreso.",
        "",
        "ESC: cerrar todo  |  R: reiniciar  |  ENTER: continuar",
    ]

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    font_thickness = 2
    line_height = 35

    # Calculate total height and starting y
    total_h = line_height * len(lines)
    y_start = (h - total_h) // 2 + 30  # +30 to account for text baseline

    for i, line in enumerate(lines):
        if not line:
            continue
        (text_w, text_h), _ = cv2.getTextSize(line, font, font_scale, font_thickness)
        x = (w - text_w) // 2
        y = y_start + i * line_height
        cv2.putText(
            image,
            line,
            (x, y),
            font,
            font_scale,
            (255, 255, 255),
            font_thickness,
            cv2.LINE_AA,
        )


def _draw_points(image: np.ndarray, points: list[tuple[int, int]]) -> None:
    """Draw numbered circles on the collected points.
    
    Modifies `image` in place. Each point gets a filled green circle
    and its 1-based order number next to it.
    """
    for i, (x, y) in enumerate(points, start=1):
        # Filled circle
        cv2.circle(image, (x, y), radius=8, color=(0, 255, 0), thickness=-1)
        
        # Number offset up and to the right of the point
        cv2.putText(
            image,
            str(i),
            (x + 12, y - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

def _show_issues_panel(image: np.ndarray, issues: tuple[Issue, ...]) -> str:
    """Show a panel with the issues found and wait for ENTER or R.
    
    Blocks until the user presses one of the relevant keys. Renders
    the panel on a copy of the image (does not modify the input).
    
    Args:
        image: The image to render the panel on.
        issues: The issues reported by `validate_quadrilateral`.
        
    Returns:
        "confirm" if the user presses ENTER, "restart" if R.
    """
    # Mapping from Issue to a human-readable message
    issue_messages = {
        Issue.SELF_INTERSECTING: "Las esquinas están en orden incorrecto.",
        Issue.EXTREME_ASPECT_RATIO: "La selección es demasiado alargada.",
        Issue.TINY_SIDE: "Uno de los lados es demasiado pequeño.",
    }

    # Work on a copy to avoid mutating the caller's image
    display = image.copy()
    h, w = display.shape[:2]

    # Dim the background
    overlay = np.zeros_like(display)
    alpha = 0.75
    cv2.addWeighted(overlay, alpha, display, 1 - alpha, 0, display)

    # Prepare the lines of text
    lines = ["La selección tiene problemas:", ""]
    for issue in issues:
        lines.append(f"- {issue_messages[issue]}")
    lines.append("")
    lines.append("ENTER: continuar  |  R: reiniciar")

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.65
    font_thickness = 2
    line_height = 35

    total_h = line_height * len(lines)
    y_start = (h - total_h) // 2 + 30

    for i, line in enumerate(lines):
        if not line:
            continue
        # Use a slightly different color for the options line
        color = (200, 200, 200) if line.startswith("ENTER") else (255, 255, 255)
        (text_w, _), _ = cv2.getTextSize(line, font, font_scale, font_thickness)
        x = (w - text_w) // 2
        y = y_start + i * line_height
        cv2.putText(
            display,
            line,
            (x, y),
            font,
            font_scale,
            color,
            font_thickness,
            cv2.LINE_AA,
        )

    # Blocking loop: wait for ENTER or R
    while True:
        cv2.imshow("Verificacion de esquinas", display)
        key = cv2.waitKey(20) & 0xFF
        if key == KEY_ENTER:
            return "confirm"
        if key in (KEY_R_LOWER, KEY_R_UPPER):
            return "restart"
        # Any other key: ignore and keep waiting


def select_corners(image: np.ndarray, max_display: int = 1200) -> np.ndarray:
    """Run the interactive selection loop and return the 4 corners.

    This function only handles the UI loop for clicks and keys.
    It does NOT validate the quadrilateral; that is the pipeline's job.

    Raises:
        SelectionCancelledError: if the user cancels the selection.
    """
    h, w = image.shape[:2]
    scale = min(1.0, max_display / max(h, w))
    if scale < 1.0:
        display_w, display_h = int(w * scale), int(h * scale)
        display = cv2.resize(image, (display_w, display_h), interpolation=cv2.INTER_AREA)
    else:
        display = image.copy()
        display_w, display_h = w, h

    window_name = "Selector de esquinas"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    
    state = SelectorState(Phase.COLLECTING)
    points: list[tuple[int, int]] = []
    pending_clicks: list[tuple[int, int]] = []

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            pending_clicks.append((x, y))

    cv2.setMouseCallback(window_name, on_mouse)

    try:
        while state.phase != Phase.CLOSED:
            event = None
            current_click = None
            if pending_clicks:
                click_x, click_y = pending_clicks.pop(0)
                event = SelectionEvent.CLICK
                current_click = (click_x, click_y)

            key = cv2.waitKey(20) & 0xFF
            
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                raise SelectionCancelledError("Window closed by user.")
                
            if key == KEY_ENTER:
                event = SelectionEvent.ENTER
            elif key in (KEY_R_LOWER, KEY_R_UPPER):
                event = SelectionEvent.RESTART
            elif key == KEY_ESC:
                event = SelectionEvent.CANCEL

            if event is not None:
                state, action = process_event(state, event, len(points))

                if action == SelectionAction.ADD_POINT:
                    if current_click:
                        points.append(current_click)
                elif action == SelectionAction.RESET_POINTS:
                    points.clear()
                    pending_clicks.clear()
                elif action == SelectionAction.CLOSE_ALL:
                    raise SelectionCancelledError("User cancelled.")
                elif action == SelectionAction.CONFIRM:
                    break

            canvas = display.copy()
            if state.phase == Phase.WARNING:
                _draw_warning_panel(canvas)
            else:
                _draw_points(canvas, points)
                if state.phase == Phase.COLLECTING:
                    banner_text = "Clic en sentido horario desde Sup.Izq | R: reiniciar | ESC: cancelar"
                else:
                    banner_text = "Clic en sentido horario desde Sup.Izq | ENTER: confirmar | R: reiniciar | ESC: cancelar"
                _draw_banner(canvas, banner_text)

            cv2.imshow(window_name, canvas)
            
    finally:
        cv2.destroyAllWindows()

    original_points = [(int(x / scale), int(y / scale)) for x, y in points]
    return np.array(original_points, dtype=np.float32)
