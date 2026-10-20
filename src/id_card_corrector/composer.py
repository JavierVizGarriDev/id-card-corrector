"""Page composition for ID cards.

This module handles the layout and rendering of corrected cards onto
a larger sheet (e.g. US Letter). It knows about pixels, margins, and
image arrays, but knows nothing about files, OpenCV windows, or the
pipeline's configuration.
"""

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np

from id_card_corrector.config import MM_PER_INCH, SheetSpec


# ---------------------------------------------------------------------------
# Errors and Enums
# ---------------------------------------------------------------------------

class CardDoesNotFitError(ValueError):
    """The card does not fit on the sheet, even when rotated."""


class LayoutVariant(str, Enum):
    """The overall layout strategy chosen for a given sheet."""
    SINGLE_CARD = "single_card"
    DUAL_SIDE_BY_SIDE = "dual_side_by_side"
    DUAL_STACKED = "dual_stacked"
    SINGLE_ROTATED = "single_rotated"  # one card per page, rotated


# ---------------------------------------------------------------------------
# Data structures for the layout plan
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CardPlacement:
    """Where a single card goes on a page."""
    x: int
    y: int
    rotated: bool
    card_index: int = 0  # Explicit index into the input cards list


@dataclass(frozen=True)
class LayoutPlan:
    """The complete composition plan.

    `pages` is a list of pages, where each page is a list of
    CardPlacement objects (one per card on that page).
    """
    variant: LayoutVariant
    pages: list[list[CardPlacement]]


# ---------------------------------------------------------------------------
# Block A: Pure layout calculation
# ---------------------------------------------------------------------------

def _validate_margin_mm(margin_mm: int | float) -> None:
    """Validate that margin_mm is a finite positive number.

    Args:
        margin_mm: The margin value to validate.

    Raises:
        TypeError: if `margin_mm` is not a number or is a bool.
        ValueError: if `margin_mm` is not finite or is not positive.
    """
    if isinstance(margin_mm, bool) or not isinstance(margin_mm, (int, float)):
        raise TypeError(
            f"margin_mm must be a number, got {type(margin_mm).__name__}: {margin_mm!r}"
        )
    if isinstance(margin_mm, float) and not math.isfinite(margin_mm):
        raise ValueError(f"margin_mm must be finite, got {margin_mm}")
    if margin_mm <= 0:
        raise ValueError(f"margin_mm must be positive, got {margin_mm}")  


def _find_layout(
    n_cards: int,
    card_w: int,
    card_h: int,
    sheet_w: int,
    sheet_h: int,
    margin_px: int,
) -> LayoutPlan:
    """Determine the layout plan.

    The usable space for each variant is calculated as follows:
      - Side-by-side (2 cards): sheet_w >= 2*card_w + 3*margin,
        sheet_h >= card_h + 2*margin.
      - Stacked (2 cards): sheet_w >= card_w + 2*margin,
        sheet_h >= 2*card_h + 3*margin.
      - Single card: sheet_w >= card_w + 2*margin,
        sheet_h >= card_h + 2*margin.
      - Single rotated card: same as single card, but with card_w
        and card_h swapped.

    If no variant fits, raises CardDoesNotFitError.

    Args:
        n_cards: Number of cards. Guaranteed to be 1 or 2 by the caller
            (`compose_sheet`), which validates it.
        card_w, card_h: Dimensions of a single card, in pixels.
        sheet_w, sheet_h: Dimensions of the sheet, in pixels.
        margin_px: The master margin, in pixels.

    Returns:
        A LayoutPlan describing which cards go on which pages,
        their coordinates, and whether they are rotated.
    """
    # --- 1. DUAL_SIDE_BY_SIDE ---
    if n_cards == 2:
        actual_margin_w = (sheet_w - 2 * card_w) // 3
        if actual_margin_w >= margin_px and sheet_h >= card_h + 2 * margin_px:
            x1 = actual_margin_w
            x2 = actual_margin_w + card_w + actual_margin_w
            y = margin_px
            page = [
                CardPlacement(x1, y, rotated=False, card_index=0),
                CardPlacement(x2, y, rotated=False, card_index=1),
            ]
            return LayoutPlan(LayoutVariant.DUAL_SIDE_BY_SIDE, [page])

    # --- 2. DUAL_STACKED ---
    if n_cards == 2:
        actual_margin_w = (sheet_w - card_w) // 2
        actual_margin_h = (sheet_h - 2 * card_h) // 3
        if actual_margin_w >= margin_px and actual_margin_h >= margin_px:
            x = actual_margin_w
            y1 = actual_margin_h
            y2 = actual_margin_h + card_h + actual_margin_h
            page = [
                CardPlacement(x, y1, rotated=False, card_index=0),
                CardPlacement(x, y2, rotated=False, card_index=1),
            ]
            return LayoutPlan(LayoutVariant.DUAL_STACKED, [page])

    # --- 3. SINGLE_CARD (1 card per page) ---
    actual_margin_w = (sheet_w - card_w) // 2
    if actual_margin_w >= margin_px and sheet_h >= card_h + 2 * margin_px:
        x = actual_margin_w
        y = margin_px
        if n_cards == 2:
            pages = [
                [CardPlacement(x, y, rotated=False, card_index=0)],
                [CardPlacement(x, y, rotated=False, card_index=1)],
            ]
        else:
            pages = [[CardPlacement(x, y, rotated=False, card_index=0)]]
        return LayoutPlan(LayoutVariant.SINGLE_CARD, pages)

    # --- 4. SINGLE_ROTATED (1 card per page, rotated) ---
    rot_w = card_h
    rot_h = card_w
    actual_margin_w = (sheet_w - rot_w) // 2
    if actual_margin_w >= margin_px and sheet_h >= rot_h + 2 * margin_px:
        x = actual_margin_w
        y = margin_px
        if n_cards == 2:
            pages = [
                [CardPlacement(x, y, rotated=True, card_index=0)],
                [CardPlacement(x, y, rotated=True, card_index=1)],
            ]
        else:
            pages = [[CardPlacement(x, y, rotated=True, card_index=0)]]
        return LayoutPlan(LayoutVariant.SINGLE_ROTATED, pages)

    # --- 5. Nothing fits ---
    raise CardDoesNotFitError(
        f"Neither orientation fits on a {sheet_w}x{sheet_h} sheet "
        f"with a {margin_px}px margin."
    )


# ---------------------------------------------------------------------------
# Block B: Image rendering
# ---------------------------------------------------------------------------

def _validate_placement(
    placement: CardPlacement,
    card: np.ndarray,
    sheet_w: int,
    sheet_h: int,
) -> None:
    """Validate that a placement is safe to render.

    Raises:
        ValueError: if the placement coordinates are negative, or if
            the card would fall outside the sheet boundaries.
    """
    h, w = card.shape[:2]
    if placement.rotated:
        h, w = w, h

    if placement.x < 0 or placement.y < 0:
        raise ValueError(
            f"placement at ({placement.x}, {placement.y}) has negative coordinates."
        )
    if placement.x + w > sheet_w:
        raise ValueError(
            f"placement at ({placement.x}, {placement.y}) with size {w}x{h} "
            f"exceeds sheet width {sheet_w}."
        )
    if placement.y + h > sheet_h:
        raise ValueError(
            f"placement at ({placement.x}, {placement.y}) with size {w}x{h} "
            f"exceeds sheet height {sheet_h}."
        )


def _place_cards(
    cards: list[np.ndarray],
    plan: LayoutPlan,
    sheet_w: int,
    sheet_h: int,
) -> list[np.ndarray]:
    """Render the cards onto white sheets according to the plan.

    Args:
        cards: The corrected BGR images (uint8, (H, W, 3)).
        plan: The LayoutPlan produced by _find_layout.
        sheet_w, sheet_h: Dimensions of the sheet in pixels.

    Returns:
        A list of BGR images, one per page in the plan.
    """
    result_pages = []
    for page in plan.pages:
        canvas = np.full((sheet_h, sheet_w, 3), 255, dtype=np.uint8)
        
        for placement in page:
            # 1. Validate card_index before accessing the array
            if not (0 <= placement.card_index < len(cards)):
                raise ValueError(
                    f"placement.card_index={placement.card_index} is out of range "
                    f"for {len(cards)} cards."
                )
            
            card = cards[placement.card_index]
            
            # 2. Validate bounds (accounts for rotation)
            _validate_placement(placement, card, sheet_w, sheet_h)

            # 3. Render
            if placement.rotated:
                card = np.rot90(card, k=-1)
            h, w = card.shape[:2]
            canvas[placement.y:placement.y+h, placement.x:placement.x+w] = card
            
        result_pages.append(canvas)
    return result_pages


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compose_sheet(
    cards: list[np.ndarray],
    sheet_spec: SheetSpec,
    margin_mm: float,
) -> list[np.ndarray]:
    """Compose one or more pages from the given cards.

    Args:
        cards: A list of 1 or 2 BGR images (uint8, (H, W, 3)).
            It is assumed they come from warp_to_rectangle and are
            therefore already corrected and normalized.
        sheet_spec: The physical dimensions of the sheet.
        margin_mm: The master margin, in millimeters.

    Returns:
        A list of BGR images, one per page. Most cases produce a
        single page with all cards. The SINGLE_ROTATED variant
        produces two pages (one card per page).

    Raises:
        CardDoesNotFitError: if no layout fits the cards on the sheet.
        ValueError: if `cards` is empty or contains more than 2 cards,
            if the cards do not share the same shape, or if `margin_mm`
            is not finite or not positive.
        TypeError: if `margin_mm` is not a number or is a bool.
    """
    if len(cards) not in (1, 2):
        raise ValueError(f"Expected 1 or 2 cards, got {len(cards)}")

    # Validate each card's shape and dtype before doing anything else
    for i, card in enumerate(cards):
        if card.ndim != 3 or card.shape[2] != 3:
            raise ValueError(
                f"Card {i} must have shape (H, W, 3), got {card.shape}"
            )
        if card.dtype != np.uint8:
            raise ValueError(
                f"Card {i} must have dtype uint8, got {card.dtype}"
            )

    if not all(c.shape == cards[0].shape for c in cards):
        raise ValueError(
            f"All cards must have the same shape. "
            f"Got {[c.shape for c in cards]}."
        )


    _validate_margin_mm(margin_mm)

    # Convert margin to pixels
    margin_px = round(margin_mm / MM_PER_INCH * sheet_spec.dpi)

    # Extract card dimensions
    card_h, card_w = cards[0].shape[:2]

    # Calculate the layout plan
    plan = _find_layout(
        n_cards=len(cards),
        card_w=card_w,
        card_h=card_h,
        sheet_w=sheet_spec.width_px,
        sheet_h=sheet_spec.height_px,
        margin_px=margin_px,
    )

    # Render the plan
    return _place_cards(
        cards=cards,
        plan=plan,
        sheet_w=sheet_spec.width_px,
        sheet_h=sheet_spec.height_px,
    )