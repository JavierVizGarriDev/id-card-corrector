"""Tests for the selector state machine.

This file covers the pure layer of the selector module:
- The private validators `_validate_state` and `_validate_n_points`.
- The public state machine `process_event`.

The OpenCV UI layer (`select_corners`, `_draw_*`) is intentionally not
tested in the MVP; mocking `cv2.imshow`/`cv2.waitKey`/`cv2.setMouseCallback`
is fragile and tightly coupled to the OpenCV version. The valuable logic
lives in the functions tested here.
"""

import pytest

from id_card_corrector.selector import (
    Phase,
    SelectionAction,
    SelectionEvent,
    SelectorState,
    _validate_n_points,
    _validate_state,
    process_event,
)


# ===========================================================================
# _validate_state
# ===========================================================================

# --- _validate_state: valid states ---

def test_validate_state_accepts_collecting():
    """COLLECTING with warning_return_to=None is valid."""
    _validate_state(SelectorState(phase=Phase.COLLECTING))


def test_validate_state_accepts_ready_to_confirm():
    """READY_TO_CONFIRM with warning_return_to=None is valid."""
    _validate_state(SelectorState(phase=Phase.READY_TO_CONFIRM))


def test_validate_state_accepts_warning_from_collecting():
    """WARNING with warning_return_to=COLLECTING is valid."""
    _validate_state(
        SelectorState(phase=Phase.WARNING, warning_return_to=Phase.COLLECTING)
    )


def test_validate_state_accepts_warning_from_ready():
    """WARNING with warning_return_to=READY_TO_CONFIRM is valid."""
    _validate_state(
        SelectorState(phase=Phase.WARNING, warning_return_to=Phase.READY_TO_CONFIRM)
    )

def test_validate_state_error_uses_clean_phase_value():
    """The error message uses the phase value, not 'Phase.X'."""
    with pytest.raises(ValueError, match="phase is collecting"):
        _validate_state(SelectorState(Phase.COLLECTING, Phase.COLLECTING))

# --- _validate_state: CLOSED is rejected ---

def test_validate_state_rejects_closed():
    """CLOSED is a terminal state and cannot be validated for processing."""
    with pytest.raises(ValueError, match="CLOSED"):
        _validate_state(SelectorState(phase=Phase.CLOSED))


def test_validate_state_rejects_closed_with_warning_return_to():
    """Even with warning_return_to set, CLOSED is rejected first."""
    with pytest.raises(ValueError, match="CLOSED"):
        _validate_state(
            SelectorState(phase=Phase.CLOSED, warning_return_to=Phase.COLLECTING)
        )


# --- _validate_state: WARNING invariants ---

def test_validate_state_rejects_warning_without_return_to():
    """WARNING requires warning_return_to to be set."""
    with pytest.raises(ValueError, match="WARNING phase requires warning_return_to"):
        _validate_state(SelectorState(phase=Phase.WARNING))


def test_validate_state_rejects_warning_returning_to_warning():
    """warning_return_to cannot be WARNING (would create an implicit loop)."""
    with pytest.raises(ValueError, match="Invalid warning_return_to"):
        _validate_state(
            SelectorState(phase=Phase.WARNING, warning_return_to=Phase.WARNING)
        )


def test_validate_state_rejects_warning_returning_to_closed():
    """warning_return_to cannot be CLOSED (would trap the user)."""
    with pytest.raises(ValueError, match="Invalid warning_return_to"):
        _validate_state(
            SelectorState(phase=Phase.WARNING, warning_return_to=Phase.CLOSED)
        )


# --- _validate_state: non-WARNING phases must have None ---

@pytest.mark.parametrize("phase", [Phase.COLLECTING, Phase.READY_TO_CONFIRM])
def test_validate_state_rejects_non_none_warning_return_to(phase):
    """warning_return_to must be None when phase is not WARNING."""
    with pytest.raises(ValueError, match="warning_return_to must be None"):
        _validate_state(
            SelectorState(phase=phase, warning_return_to=Phase.COLLECTING)
        )


# --- _validate_state: return value ---

def test_validate_state_returns_none_on_valid_input():
    """The validator returns None on success."""
    assert _validate_state(SelectorState(phase=Phase.COLLECTING)) is None


# ===========================================================================
# _validate_n_points
# ===========================================================================

# --- _validate_n_points: COLLECTING ---

@pytest.mark.parametrize("n_points", [0, 1, 2, 3])
def test_validate_n_points_accepts_collecting_range(n_points):
    """All values 0..3 are valid for COLLECTING."""
    _validate_n_points(SelectorState(phase=Phase.COLLECTING), n_points)


@pytest.mark.parametrize("n_points", [-1, -100, 4, 5, 100])
def test_validate_n_points_rejects_collecting_out_of_range(n_points):
    """Values outside 0..3 are rejected for COLLECTING."""
    with pytest.raises(ValueError, match="COLLECTING requires"):
        _validate_n_points(SelectorState(phase=Phase.COLLECTING), n_points)


# --- _validate_n_points: READY_TO_CONFIRM ---

def test_validate_n_points_accepts_ready_exactly_four():
    """Only n_points == 4 is valid for READY_TO_CONFIRM."""
    _validate_n_points(SelectorState(phase=Phase.READY_TO_CONFIRM), 4)


@pytest.mark.parametrize("n_points", [0, 1, 2, 3, 5, 100])
def test_validate_n_points_rejects_ready_non_four(n_points):
    """Any value other than 4 is rejected for READY_TO_CONFIRM."""
    with pytest.raises(ValueError, match="READY_TO_CONFIRM requires n_points == 4"):
        _validate_n_points(SelectorState(phase=Phase.READY_TO_CONFIRM), n_points)


# --- _validate_n_points: WARNING returning to COLLECTING ---

@pytest.mark.parametrize("n_points", [0, 1, 2, 3])
def test_validate_n_points_accepts_warning_from_collecting_range(n_points):
    """WARNING returning to COLLECTING follows the COLLECTING range."""
    state = SelectorState(phase=Phase.WARNING, warning_return_to=Phase.COLLECTING)
    _validate_n_points(state, n_points)


@pytest.mark.parametrize("n_points", [-1, 4, 5])
def test_validate_n_points_rejects_warning_from_collecting_out_of_range(n_points):
    """WARNING returning to COLLECTING rejects out-of-range values."""
    state = SelectorState(phase=Phase.WARNING, warning_return_to=Phase.COLLECTING)
    with pytest.raises(ValueError, match=r"WARNING \(returning to collecting\)"):
        _validate_n_points(state, n_points)


# --- _validate_n_points: WARNING returning to READY_TO_CONFIRM ---

def test_validate_n_points_accepts_warning_from_ready_exactly_four():
    """WARNING returning to READY_TO_CONFIRM requires n_points == 4."""
    state = SelectorState(
        phase=Phase.WARNING, warning_return_to=Phase.READY_TO_CONFIRM
    )
    _validate_n_points(state, 4)


@pytest.mark.parametrize("n_points", [0, 1, 2, 3, 5])
def test_validate_n_points_rejects_warning_from_ready_non_four(n_points):
    """WARNING returning to READY_TO_CONFIRM rejects values other than 4."""
    state = SelectorState(
        phase=Phase.WARNING, warning_return_to=Phase.READY_TO_CONFIRM
    )
    with pytest.raises(ValueError, match=r"WARNING \(returning to ready\)"):
        _validate_n_points(state, n_points)


# --- _validate_n_points: return value ---

def test_validate_n_points_returns_none_on_valid_input():
    """The validator returns None on success."""
    assert _validate_n_points(SelectorState(phase=Phase.COLLECTING), 0) is None


# ===========================================================================
# process_event: COLLECTING
# ===========================================================================

@pytest.mark.parametrize("n_points", [0, 1, 2])
def test_collecting_click_below_three_stays_in_collecting(n_points):
    """Click with 0..2 points already collected stays in COLLECTING."""
    new_state, action = process_event(
        SelectorState(Phase.COLLECTING), SelectionEvent.CLICK, n_points=n_points
    )
    assert new_state == SelectorState(Phase.COLLECTING)
    assert action == SelectionAction.ADD_POINT


def test_collecting_click_with_three_points_transitions_to_ready():
    """The fourth click adds the point and moves to READY_TO_CONFIRM."""
    new_state, action = process_event(
        SelectorState(Phase.COLLECTING), SelectionEvent.CLICK, n_points=3
    )
    assert new_state == SelectorState(Phase.READY_TO_CONFIRM)
    assert action == SelectionAction.ADD_POINT


def test_collecting_enter_is_no_op():
    """ENTER in COLLECTING does nothing (nothing to confirm yet)."""
    new_state, action = process_event(
        SelectorState(Phase.COLLECTING), SelectionEvent.ENTER, n_points=2
    )
    assert new_state == SelectorState(Phase.COLLECTING)
    assert action == SelectionAction.NONE


def test_collecting_restart_resets_points():
    """R in COLLECTING clears the points and stays in COLLECTING."""
    new_state, action = process_event(
        SelectorState(Phase.COLLECTING), SelectionEvent.RESTART, n_points=2
    )
    assert new_state == SelectorState(Phase.COLLECTING)
    assert action == SelectionAction.RESET_POINTS


def test_collecting_cancel_enters_warning_remembering_collecting():
    """ESC in COLLECTING raises the warning and records COLLECTING as return target."""
    new_state, action = process_event(
        SelectorState(Phase.COLLECTING), SelectionEvent.CANCEL, n_points=2
    )
    assert new_state == SelectorState(Phase.WARNING, Phase.COLLECTING)
    assert action == SelectionAction.SHOW_WARNING


# ===========================================================================
# process_event: READY_TO_CONFIRM
# ===========================================================================

def test_ready_click_is_no_op():
    """Click in READY_TO_CONFIRM is ignored (already have 4 points)."""
    new_state, action = process_event(
        SelectorState(Phase.READY_TO_CONFIRM), SelectionEvent.CLICK, n_points=4
    )
    assert new_state == SelectorState(Phase.READY_TO_CONFIRM)
    assert action == SelectionAction.NONE


def test_ready_enter_confirms_and_closes():
    """ENTER in READY_TO_CONFIRM emits CONFIRM and closes the state machine."""
    new_state, action = process_event(
        SelectorState(Phase.READY_TO_CONFIRM), SelectionEvent.ENTER, n_points=4
    )
    assert new_state == SelectorState(Phase.CLOSED)
    assert action == SelectionAction.CONFIRM


def test_ready_restart_returns_to_collecting():
    """R in READY_TO_CONFIRM drops the 4 points and starts over."""
    new_state, action = process_event(
        SelectorState(Phase.READY_TO_CONFIRM), SelectionEvent.RESTART, n_points=4
    )
    assert new_state == SelectorState(Phase.COLLECTING)
    assert action == SelectionAction.RESET_POINTS


def test_ready_cancel_enters_warning_remembering_ready():
    """ESC in READY_TO_CONFIRM raises the warning and records READY as return target."""
    new_state, action = process_event(
        SelectorState(Phase.READY_TO_CONFIRM), SelectionEvent.CANCEL, n_points=4
    )
    assert new_state == SelectorState(Phase.WARNING, Phase.READY_TO_CONFIRM)
    assert action == SelectionAction.SHOW_WARNING


# ===========================================================================
# process_event: WARNING (came from COLLECTING)
# ===========================================================================

def test_warning_from_collecting_click_preserves_return_target():
    """Click in WARNING is ignored and preserves warning_return_to."""
    state = SelectorState(Phase.WARNING, Phase.COLLECTING)
    new_state, action = process_event(state, SelectionEvent.CLICK, n_points=2)
    assert new_state == SelectorState(Phase.WARNING, Phase.COLLECTING)
    assert action == SelectionAction.NONE


def test_warning_from_collecting_enter_returns_to_collecting():
    """ENTER dismisses the warning and returns to where the user was."""
    state = SelectorState(Phase.WARNING, Phase.COLLECTING)
    new_state, action = process_event(state, SelectionEvent.ENTER, n_points=2)
    assert new_state == SelectorState(Phase.COLLECTING)
    assert action == SelectionAction.NONE


def test_warning_from_collecting_restart_resets_and_returns_to_collecting():
    """R in WARNING resets and lands in COLLECTING regardless of origin."""
    state = SelectorState(Phase.WARNING, Phase.COLLECTING)
    new_state, action = process_event(state, SelectionEvent.RESTART, n_points=2)
    assert new_state == SelectorState(Phase.COLLECTING)
    assert action == SelectionAction.RESET_POINTS


def test_warning_from_collecting_cancel_closes_all():
    """A second ESC (CANCEL) in WARNING aborts the program."""
    state = SelectorState(Phase.WARNING, Phase.COLLECTING)
    new_state, action = process_event(state, SelectionEvent.CANCEL, n_points=2)
    assert new_state == SelectorState(Phase.CLOSED)
    assert action == SelectionAction.CLOSE_ALL


# ===========================================================================
# process_event: WARNING (came from READY_TO_CONFIRM)
# ===========================================================================

def test_warning_from_ready_click_preserves_return_target():
    """Click in WARNING preserves a READY_TO_CONFIRM return target."""
    state = SelectorState(Phase.WARNING, Phase.READY_TO_CONFIRM)
    new_state, action = process_event(state, SelectionEvent.CLICK, n_points=4)
    assert new_state == SelectorState(Phase.WARNING, Phase.READY_TO_CONFIRM)
    assert action == SelectionAction.NONE


def test_warning_from_ready_enter_returns_to_ready():
    """ENTER dismisses the warning and returns to READY_TO_CONFIRM."""
    state = SelectorState(Phase.WARNING, Phase.READY_TO_CONFIRM)
    new_state, action = process_event(state, SelectionEvent.ENTER, n_points=4)
    assert new_state == SelectorState(Phase.READY_TO_CONFIRM)
    assert action == SelectionAction.NONE


def test_warning_from_ready_restart_returns_to_collecting():
    """R in WARNING lands in COLLECTING regardless of where it came from."""
    state = SelectorState(Phase.WARNING, Phase.READY_TO_CONFIRM)
    new_state, action = process_event(state, SelectionEvent.RESTART, n_points=4)
    assert new_state == SelectorState(Phase.COLLECTING)
    assert action == SelectionAction.RESET_POINTS


def test_warning_from_ready_cancel_closes_all():
    """A second ESC aborts even when the warning came from READY."""
    state = SelectorState(Phase.WARNING, Phase.READY_TO_CONFIRM)
    new_state, action = process_event(state, SelectionEvent.CANCEL, n_points=4)
    assert new_state == SelectorState(Phase.CLOSED)
    assert action == SelectionAction.CLOSE_ALL


# ===========================================================================
# process_event: validation is delegated before any transition
# ===========================================================================

def test_process_event_rejects_closed_state():
    """CLOSED is rejected by _validate_state before any transition logic."""
    with pytest.raises(ValueError, match="CLOSED"):
        process_event(SelectorState(Phase.CLOSED), SelectionEvent.ENTER, n_points=4)


def test_process_event_rejects_inconsistent_n_points():
    """n_points inconsistent with phase is rejected before any transition."""
    with pytest.raises(ValueError, match="COLLECTING requires"):
        process_event(
            SelectorState(Phase.COLLECTING), SelectionEvent.CLICK, n_points=4
        )


def test_process_event_rejects_warning_without_return_target():
    """WARNING missing warning_return_to is rejected before dispatch."""
    with pytest.raises(ValueError, match="WARNING phase requires"):
        process_event(SelectorState(Phase.WARNING), SelectionEvent.ENTER, n_points=2)


# ===========================================================================
# process_event: integration sequences
# ===========================================================================

def test_full_happy_path_sequence():
    """Four clicks then ENTER: the state machine reaches CONFIRM + CLOSED."""
    state = SelectorState(Phase.COLLECTING)
    n = 0
    for _ in range(3):
        state, action = process_event(state, SelectionEvent.CLICK, n)
        assert state == SelectorState(Phase.COLLECTING)
        assert action == SelectionAction.ADD_POINT
        n += 1
    state, action = process_event(state, SelectionEvent.CLICK, n)
    assert state == SelectorState(Phase.READY_TO_CONFIRM)
    assert action == SelectionAction.ADD_POINT
    n += 1
    state, action = process_event(state, SelectionEvent.ENTER, n)
    assert state == SelectorState(Phase.CLOSED)
    assert action == SelectionAction.CONFIRM


def test_cancel_then_dismiss_returns_to_previous_phase():
    """ESC then ENTER returns to the original phase, preserving n_points."""
    state = SelectorState(Phase.COLLECTING)
    n = 2
    state, _ = process_event(state, SelectionEvent.CANCEL, n)
    assert state == SelectorState(Phase.WARNING, Phase.COLLECTING)
    state, action = process_event(state, SelectionEvent.ENTER, n)
    assert state == SelectorState(Phase.COLLECTING)
    assert action == SelectionAction.NONE
    # Can continue collecting
    state, action = process_event(state, SelectionEvent.CLICK, n)
    assert action == SelectionAction.ADD_POINT


def test_closed_state_after_confirm_cannot_be_reprocessed():
    """Once CONFIRM closes the machine, further events raise ValueError."""
    state, _ = process_event(
        SelectorState(Phase.READY_TO_CONFIRM), SelectionEvent.ENTER, n_points=4
    )
    assert state == SelectorState(Phase.CLOSED)
    with pytest.raises(ValueError, match="CLOSED"):
        process_event(state, SelectionEvent.CLICK, n_points=4)


# ===========================================================================
# process_event: completeness invariant
# ===========================================================================

def test_every_valid_state_event_combination_is_handled():
    """Every (state, event) reachable through validation produces a transition,
    not the defensive 'unhandled' error."""
    combos = [
        (SelectorState(Phase.COLLECTING), range(0, 4)),
        (SelectorState(Phase.READY_TO_CONFIRM), [4]),
        (SelectorState(Phase.WARNING, Phase.COLLECTING), range(0, 4)),
        (SelectorState(Phase.WARNING, Phase.READY_TO_CONFIRM), [4]),
    ]
    for state, valid_ns in combos:
        for n in valid_ns:
            for event in SelectionEvent:
                # Should not raise the defensive error.
                process_event(state, event, n)