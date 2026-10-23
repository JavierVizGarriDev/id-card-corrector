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
    """Draw a semi-transparent banner at the bottom of the image."""
    # TODO: use cv2.rectangle and cv2.addWeighted for transparency,
    # then cv2.putText for the text.
    ...


def _draw_warning_panel(image: np.ndarray) -> None:
    """Draw the warning panel over the image."""
    # TODO: draw a darker overlay and the warning text.
    ...


def _draw_points(image: np.ndarray, points: list[tuple[int, int]]) -> None:
    """Draw circles and order numbers on the collected points."""
    # TODO: iterate over points, draw cv2.circle and cv2.putText.
    ...


def _show_issues_panel(image: np.ndarray, issues: tuple[Issue, ...]) -> str:
    """Show a panel with the issues found and wait for ENTER or R.
    
    Returns:
        "confirm" if the user presses ENTER, "restart" if R.
    """
    # TODO: draw text explaining the issues, wait for key.
    # Map ENTER to "confirm", R to "restart".
    ...


def select_corners(image: np.ndarray, max_display: int = 1200) -> np.ndarray:
    """Run the interactive selection loop and return the 4 corners.
    
    Args:
        image: The image to display.
        max_display: Max dimension for the window. The image is
            downscaled for display, but points are returned in the
            original image coordinates.
            
    Returns:
        np.ndarray of shape (4, 2), dtype float32, in TL, TR, BR, BL order.
        
    Raises:
        SelectionCancelledError: if the user cancels the selection.
    """
    # TODO:
    # 1. Setup display (resize if needed, calculate scale factor).
    # 2. Create window and set mouse callback.
    # 3. Initialize state = SelectorState(Phase.COLLECTING), points = []
    # 4. Loop:
    #    a. Draw points and banner.
    #    b. cv2.imshow(window_name, display_image)
    #    c. key = cv2.waitKey(20)
    #    d. Translate key to event.
    #    e. If ENTER in READY_TO_CONFIRM: run validate_quadrilateral first!
    #       - If DegenerateQuadrilateralError: show error, restart.
    #       - If issues: show_issues_panel. If restart, reset. If confirm, fall through.
    #    f. state, action = process_event(state, event, len(points))
    #    g. Execute action (ADD_POINT, RESET, CLOSE, etc.)
    #    h. If action == CLOSE_ALL: raise SelectionCancelledError()
    #    i. If action == CONFIRM: break loop.
    # 5. cv2.destroyAllWindows()
    # 6. Convert points to original coordinates (divide by scale).
    # 7. Return np.array(points, dtype=np.float32)
    ...
