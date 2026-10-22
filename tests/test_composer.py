import pytest

import numpy as np

from id_card_corrector.config import (
    CardSpec, 
    SheetSpec,
)

from id_card_corrector.composer import (
    _validate_margin_mm,
    CardDoesNotFitError,
    LayoutVariant,
    _find_layout,
    CardPlacement,
    _validate_placement,
    LayoutPlan,
    _place_cards,
    compose_sheet,
)

# --- _validate_margin_mm: valid inputs ---

@pytest.mark.parametrize("margin_mm", [0.1, 1, 8.47, 100, 1000])
def test_validate_margin_mm_accepts_positive_numbers(margin_mm):
    """Positive ints and floats are accepted."""
    _validate_margin_mm(margin_mm)  # should not raise


def test_validate_margin_mm_accepts_typical_values():
    """The values used in the pipeline (MARGIN_MM, multiples of it) are accepted."""
    _validate_margin_mm(8.47)     # MARGIN_MM from config
    _validate_margin_mm(10.0)
    _validate_margin_mm(5)


def test_validate_margin_mm_accepts_huge_int():
    """An integer too large for float is still a valid Python int."""
    # Without the isinstance(margin_mm, float) guard, math.isfinite
    # would raise OverflowError here.
    _validate_margin_mm(10**400)


# --- _validate_margin_mm: TypeError for non-numbers ---

@pytest.mark.parametrize("margin_mm", [True, False])
def test_validate_margin_mm_rejects_bool(margin_mm):
    """bool is rejected even though it is a subclass of int."""
    with pytest.raises(TypeError, match="bool"):
        _validate_margin_mm(margin_mm)


@pytest.mark.parametrize("margin_mm", ["10", None, [10], {"margin": 10}, object()])
def test_validate_margin_mm_rejects_non_number_types(margin_mm):
    """Non-numeric values are rejected with TypeError."""
    with pytest.raises(TypeError):
        _validate_margin_mm(margin_mm)


# --- _validate_margin_mm: ValueError for non-finite floats ---

@pytest.mark.parametrize("margin_mm", [
    float("inf"),
    float("-inf"),
    float("nan"),
])
def test_validate_margin_mm_rejects_non_finite(margin_mm):
    """inf, -inf and nan are rejected with ValueError."""
    with pytest.raises(ValueError, match="must be finite"):
        _validate_margin_mm(margin_mm)


def test_validate_margin_mm_nan_reports_not_finite_not_not_positive():
    """nan must be caught by the finite check, not slip through."""
    # Without the finite guard, nan <= 0 is False, so nan would pass
    # silently and produce a nonsensical layout.
    with pytest.raises(ValueError, match="must be finite"):
        _validate_margin_mm(float("nan"))


# --- _validate_margin_mm: ValueError for non-positive values ---

@pytest.mark.parametrize("margin_mm", [0, 0.0, -1, -8.47, -0.5])
def test_validate_margin_mm_rejects_non_positive(margin_mm):
    """Zero and negative values are rejected with ValueError."""
    with pytest.raises(ValueError, match="must be positive"):
        _validate_margin_mm(margin_mm)


# --- _validate_margin_mm: return value ---

def test_validate_margin_mm_returns_none():
    """The validator returns None on success."""
    assert _validate_margin_mm(10.0) is None


CARD_W, CARD_H, MARGIN = 100, 60, 10


# --- _find_layout: preference order ---

def test_dual_side_by_side_preferred_when_both_dual_layouts_fit():
    """When both dual layouts fit, side-by-side wins (checked first)."""
    plan = _find_layout(n_cards=2, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=300, sheet_h=200, margin_px=MARGIN)
    assert plan.variant == LayoutVariant.DUAL_SIDE_BY_SIDE


def test_dual_stacked_chosen_when_side_by_side_does_not_fit():
    """Narrow but tall sheet: SBS fails on width, STACKED fits."""
    plan = _find_layout(n_cards=2, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=130, sheet_h=200, margin_px=MARGIN)
    assert plan.variant == LayoutVariant.DUAL_STACKED


def test_single_card_chosen_for_one_card_when_duals_irrelevant():
    """With n=1, dual layouts are skipped; SINGLE_CARD is preferred over rotated."""
    plan = _find_layout(n_cards=1, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=200, sheet_h=200, margin_px=MARGIN)
    assert plan.variant == LayoutVariant.SINGLE_CARD


def test_single_card_preferred_over_single_rotated_when_both_fit():
    """SINGLE is checked before ROTATED, so it wins when both fit."""
    # Wide and tall enough for both orientations
    plan = _find_layout(n_cards=1, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=200, sheet_h=200, margin_px=MARGIN)
    assert plan.variant == LayoutVariant.SINGLE_CARD


def test_single_card_fallback_for_two_cards_when_dual_fails():
    """No dual layout fits: SINGLE_CARD takes over, producing two pages."""
    plan = _find_layout(n_cards=2, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=130, sheet_h=90, margin_px=MARGIN)
    assert plan.variant == LayoutVariant.SINGLE_CARD
    assert len(plan.pages) == 2


def test_single_rotated_chosen_when_only_rotated_fits():
    """Portrait sheet too narrow for landscape, wide enough for rotated."""
    plan = _find_layout(n_cards=1, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=90, sheet_h=130, margin_px=MARGIN)
    assert plan.variant == LayoutVariant.SINGLE_ROTATED


def test_raises_when_nothing_fits():
    """Sheet too small for even the rotated card raises CardDoesNotFitError."""
    with pytest.raises(CardDoesNotFitError):
        _find_layout(n_cards=1, card_w=CARD_W, card_h=CARD_H,
                     sheet_w=50, sheet_h=50, margin_px=MARGIN)


def test_error_message_includes_sheet_size_and_margin():
    """The error message names the dimensions that failed."""
    with pytest.raises(CardDoesNotFitError, match=r"50x50.*10"):
        _find_layout(n_cards=1, card_w=CARD_W, card_h=CARD_H,
                     sheet_w=50, sheet_h=50, margin_px=MARGIN)


# --- _find_layout: plan structure ---

def test_dual_side_by_side_single_page_with_two_placements():
    plan = _find_layout(n_cards=2, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=300, sheet_h=200, margin_px=MARGIN)
    assert len(plan.pages) == 1
    assert len(plan.pages[0]) == 2


def test_dual_stacked_single_page_with_two_placements():
    plan = _find_layout(n_cards=2, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=130, sheet_h=200, margin_px=MARGIN)
    assert len(plan.pages) == 1
    assert len(plan.pages[0]) == 2


def test_single_card_one_page_for_one_card():
    plan = _find_layout(n_cards=1, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=200, sheet_h=200, margin_px=MARGIN)
    assert len(plan.pages) == 1
    assert len(plan.pages[0]) == 1


def test_single_card_two_pages_for_two_cards():
    plan = _find_layout(n_cards=2, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=130, sheet_h=90, margin_px=MARGIN)
    assert len(plan.pages) == 2
    assert len(plan.pages[0]) == 1
    assert len(plan.pages[1]) == 1


def test_single_rotated_two_pages_for_two_cards():
    plan = _find_layout(n_cards=2, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=90, sheet_h=130, margin_px=MARGIN)
    assert plan.variant == LayoutVariant.SINGLE_ROTATED
    assert len(plan.pages) == 2
    assert plan.pages[0][0].rotated is True
    assert plan.pages[1][0].rotated is True


# --- _find_layout: card_index assignment ---

def test_dual_side_by_side_card_indices_are_zero_and_one():
    plan = _find_layout(n_cards=2, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=300, sheet_h=200, margin_px=MARGIN)
    indices = [p.card_index for p in plan.pages[0]]
    assert indices == [0, 1]


def test_single_card_two_pages_have_distinct_card_indices():
    plan = _find_layout(n_cards=2, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=130, sheet_h=90, margin_px=MARGIN)
    assert plan.pages[0][0].card_index == 0
    assert plan.pages[1][0].card_index == 1


def test_every_card_index_appears_exactly_once_across_all_variants():
    """Invariant: for n=2, each card_index in {0,1} appears exactly once."""
    scenarios = [
        (300, 200),  # DUAL_SIDE_BY_SIDE
        (130, 200),  # DUAL_STACKED
        (130,  90),  # SINGLE_CARD (2 pages)
        ( 90, 130),  # SINGLE_ROTATED (2 pages)
    ]
    for sheet_w, sheet_h in scenarios:
        plan = _find_layout(n_cards=2, card_w=CARD_W, card_h=CARD_H,
                            sheet_w=sheet_w, sheet_h=sheet_h, margin_px=MARGIN)
        all_indices = sorted(p.card_index for page in plan.pages for p in page)
        assert all_indices == [0, 1], (
            f"Scenario ({sheet_w}x{sheet_h}) produced indices {all_indices}"
        )


# --- _find_layout: placement coordinates ---

def test_dual_side_by_side_positions_at_exact_minimum():
    """At the exact fit, cards are placed with equal 10 px gaps."""
    # sheet_w = 2*card_w + 3*margin = 230; sheet_h = card_h + 2*margin = 80
    plan = _find_layout(n_cards=2, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=230, sheet_h=80, margin_px=MARGIN)
    p0, p1 = plan.pages[0]
    assert (p0.x, p0.y) == (10, 10)
    assert (p1.x, p1.y) == (120, 10)


def test_dual_side_by_side_positions_with_extra_width():
    """Extra width is distributed evenly among the three horizontal gaps."""
    # sheet_w=300: actual_margin_w = (300-200)//3 = 33
    plan = _find_layout(n_cards=2, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=300, sheet_h=100, margin_px=MARGIN)
    p0, p1 = plan.pages[0]
    assert (p0.x, p0.y) == (33, 10)
    assert (p1.x, p1.y) == (33 + 100 + 33, 10)  # = 166


def test_dual_stacked_positions_at_exact_minimum():
    # sheet_w = card_w + 2*margin = 120; sheet_h = 2*card_h + 3*margin = 150
    plan = _find_layout(n_cards=2, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=120, sheet_h=150, margin_px=MARGIN)
    p0, p1 = plan.pages[0]
    assert (p0.x, p0.y) == (10, 10)
    assert (p1.x, p1.y) == (10, 80)


def test_single_card_is_top_aligned():
    """The card is placed at y=margin_px, not vertically centered."""
    # Sheet: 200x200. Horizontally centered at x=(200-100)//2=50.
    # Vertically top-aligned at y=10 (NOT centered at y=70).
    plan = _find_layout(n_cards=1, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=200, sheet_h=200, margin_px=MARGIN)
    p = plan.pages[0][0]
    assert (p.x, p.y) == (50, 10)
    assert p.rotated is False


def test_single_rotated_placement_uses_rotated_dimensions_for_x():
    """The rotated card is 60 wide, 100 tall: x is centered on that width."""
    # Sheet 90 wide: (90-60)//2 = 15. Sheet 130 tall: y = 10 (top-aligned).
    plan = _find_layout(n_cards=1, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=90, sheet_h=130, margin_px=MARGIN)
    p = plan.pages[0][0]
    assert (p.x, p.y) == (15, 10)
    assert p.rotated is True


# --- _find_layout: boundaries ---

def test_dual_side_by_side_at_exact_minimum_width_and_height():
    """Both dimensions exactly at the minimum fits."""
    plan = _find_layout(n_cards=2, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=230, sheet_h=80, margin_px=MARGIN)
    assert plan.variant == LayoutVariant.DUAL_SIDE_BY_SIDE


def test_dual_side_by_side_one_pixel_below_width_falls_to_stacked():
    """sheet_w = minimum - 1: SBS fails, STACKED takes over if it fits."""
    plan = _find_layout(n_cards=2, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=229, sheet_h=150, margin_px=MARGIN)
    assert plan.variant == LayoutVariant.DUAL_STACKED


def test_single_card_at_exact_minimum():
    # sheet_w=120, sheet_h=80: minimum for SINGLE.
    plan = _find_layout(n_cards=1, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=120, sheet_h=80, margin_px=MARGIN)
    p = plan.pages[0][0]
    assert (p.x, p.y) == (10, 10)


def test_single_rotated_at_exact_minimum():
    # Rotated card is 60 wide, 100 tall. Minimum: 80 x 120.
    # SINGLE requires 120 wide, so fails on width; ROTATED fits exactly.
    plan = _find_layout(n_cards=1, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=80, sheet_h=120, margin_px=MARGIN)
    assert plan.variant == LayoutVariant.SINGLE_ROTATED
    p = plan.pages[0][0]
    assert (p.x, p.y) == (10, 10)


def test_margin_zero_produces_exact_fit_layout():
    """margin_px=0 is a valid boundary: cards touch the edges."""
    plan = _find_layout(n_cards=1, card_w=CARD_W, card_h=CARD_H,
                        sheet_w=100, sheet_h=60, margin_px=0)
    assert plan.variant == LayoutVariant.SINGLE_CARD
    p = plan.pages[0][0]
    assert (p.x, p.y) == (0, 0)


# Card helper: shape (H, W, 3) = (60, 100, 3) → h=60, w=100.
# Rotated: h=100, w=60.


# --- _validate_placement: valid placements ---

def test_validate_placement_accepts_valid_non_rotated():
    """A card well inside the sheet passes."""
    placement = CardPlacement(x=10, y=20, rotated=False, card_index=0)
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    _validate_placement(placement, card, sheet_w=200, sheet_h=200)


def test_validate_placement_accepts_valid_rotated():
    """A rotated card uses swapped dimensions; a valid placement passes."""
    placement = CardPlacement(x=10, y=20, rotated=True, card_index=0)
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    _validate_placement(placement, card, sheet_w=200, sheet_h=200)


def test_validate_placement_accepts_at_origin():
    """x=0, y=0 is valid (checks < 0, not <= 0)."""
    placement = CardPlacement(x=0, y=0, rotated=False, card_index=0)
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    _validate_placement(placement, card, sheet_w=100, sheet_h=60)


# --- _validate_placement: exact boundaries ---

def test_validate_placement_accepts_exact_fit_width():
    """x + w == sheet_w is valid (uses >, not >=)."""
    placement = CardPlacement(x=100, y=0, rotated=False, card_index=0)
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    _validate_placement(placement, card, sheet_w=200, sheet_h=60)


def test_validate_placement_accepts_exact_fit_height():
    """y + h == sheet_h is valid (uses >, not >=)."""
    placement = CardPlacement(x=0, y=40, rotated=False, card_index=0)
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    _validate_placement(placement, card, sheet_w=100, sheet_h=100)


# --- _validate_placement: negative coordinates ---

def test_validate_placement_rejects_negative_x():
    placement = CardPlacement(x=-1, y=10, rotated=False, card_index=0)
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="negative coordinates"):
        _validate_placement(placement, card, sheet_w=200, sheet_h=200)


def test_validate_placement_rejects_negative_y():
    placement = CardPlacement(x=10, y=-5, rotated=False, card_index=0)
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="negative coordinates"):
        _validate_placement(placement, card, sheet_w=200, sheet_h=200)


def test_validate_placement_rejects_negative_x_within_numeric_bounds():
    """A negative x is rejected even when x + w <= sheet_w numerically."""
    # x=-10, w=50, sheet_w=100: x+w=40 <= 100, would pass boundary check.
    # Without the negative check, slicing with -10 would behave erratically.
    placement = CardPlacement(x=-10, y=10, rotated=False, card_index=0)
    card = np.zeros((60, 50, 3), dtype=np.uint8)  # w=50
    with pytest.raises(ValueError, match="negative coordinates"):
        _validate_placement(placement, card, sheet_w=100, sheet_h=100)


# --- _validate_placement: exceeds width ---

def test_validate_placement_rejects_width_exceeded_by_one():
    """x + w == sheet_w + 1 is rejected."""
    placement = CardPlacement(x=101, y=0, rotated=False, card_index=0)
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="exceeds sheet width"):
        _validate_placement(placement, card, sheet_w=200, sheet_h=60)


def test_validate_placement_rejects_card_wider_than_sheet():
    placement = CardPlacement(x=0, y=0, rotated=False, card_index=0)
    card = np.zeros((60, 500, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="exceeds sheet width"):
        _validate_placement(placement, card, sheet_w=200, sheet_h=100)


# --- _validate_placement: exceeds height ---

def test_validate_placement_rejects_height_exceeded_by_one():
    """y + h == sheet_h + 1 is rejected."""
    placement = CardPlacement(x=0, y=41, rotated=False, card_index=0)
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="exceeds sheet height"):
        _validate_placement(placement, card, sheet_w=100, sheet_h=100)


# --- _validate_placement: rotation swaps dimensions ---

def test_validate_placement_nonrotated_fit_can_fail_rotated_width():
    """Card fits width non-rotated, exceeds width rotated."""
    # Card: h=60, w=100. Sheet: 90x130.
    # Non-rotated: w=100, x+w=110 > 90 → fails.
    # Rotated: w=60, h=100; x+w=70 ≤ 90, y+h=110 ≤ 130 → passes.
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    non_rotated = CardPlacement(x=10, y=10, rotated=False, card_index=0)
    rotated = CardPlacement(x=10, y=10, rotated=True, card_index=0)
    with pytest.raises(ValueError, match="exceeds sheet width"):
        _validate_placement(non_rotated, card, sheet_w=90, sheet_h=130)
    _validate_placement(rotated, card, sheet_w=90, sheet_h=130)


def test_validate_placement_nonrotated_fit_can_fail_rotated_height():
    """Card fits height non-rotated, exceeds height rotated."""
    # Card: h=60, w=100. Sheet: 200x90.
    # Rotated: h=100, y+h=10+100=110 > 90.
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    rotated = CardPlacement(x=10, y=10, rotated=True, card_index=0)
    with pytest.raises(ValueError, match="exceeds sheet height"):
        _validate_placement(rotated, card, sheet_w=200, sheet_h=90)


# --- _validate_placement: error message content ---

def test_validate_placement_error_message_includes_coordinates():
    placement = CardPlacement(x=-5, y=-7, rotated=False, card_index=0)
    card = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match=r"\(-5, -7\)"):
        _validate_placement(placement, card, sheet_w=100, sheet_h=100)


def test_validate_placement_width_error_includes_size_and_sheet_width():
    placement = CardPlacement(x=0, y=0, rotated=False, card_index=0)
    card = np.zeros((60, 500, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match=r"500x60.*sheet width 200"):
        _validate_placement(placement, card, sheet_w=200, sheet_h=100)


# --- _validate_placement: return value ---

def test_validate_placement_returns_none():
    """The validator returns None on success."""
    placement = CardPlacement(x=0, y=0, rotated=False, card_index=0)
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    assert _validate_placement(placement, card, sheet_w=100, sheet_h=60) is None

# --- _place_cards: output structure ---

def test_place_cards_returns_one_page_per_plan_page():
    """Number of output pages matches number of plan pages."""
    cards = [np.zeros((60, 100, 3), dtype=np.uint8)]
    plan = LayoutPlan(
        variant=LayoutVariant.SINGLE_CARD,
        pages=[
            [CardPlacement(10, 10, rotated=False, card_index=0)],
            [CardPlacement(10, 10, rotated=False, card_index=0)],
        ],
    )
    result = _place_cards(cards, plan, sheet_w=200, sheet_h=200)
    assert len(result) == 2


def test_place_cards_page_shape_and_dtype():
    """Each page has shape (sheet_h, sheet_w, 3) and dtype uint8."""
    cards = [np.zeros((60, 100, 3), dtype=np.uint8)]
    plan = LayoutPlan(
        variant=LayoutVariant.SINGLE_CARD,
        pages=[[CardPlacement(10, 10, rotated=False, card_index=0)]],
    )
    result = _place_cards(cards, plan, sheet_w=200, sheet_h=300)
    assert result[0].shape == (300, 200, 3)
    assert result[0].dtype == np.uint8


def test_place_cards_empty_page_produces_white_canvas():
    """A plan with an empty page still yields a blank white page."""
    cards = [np.zeros((10, 10, 3), dtype=np.uint8)]
    plan = LayoutPlan(variant=LayoutVariant.SINGLE_CARD, pages=[[]])
    result = _place_cards(cards, plan, sheet_w=50, sheet_h=50)
    assert (result[0] == 255).all()


# --- _place_cards: paste location ---

def test_place_cards_pastes_at_exact_coordinates():
    """A uniform card ends up at exactly the placement coordinates."""
    card = np.full((60, 100, 3), 42, dtype=np.uint8)
    plan = LayoutPlan(
        variant=LayoutVariant.SINGLE_CARD,
        pages=[[CardPlacement(20, 30, rotated=False, card_index=0)]],
    )
    canvas = _place_cards([card], plan, sheet_w=200, sheet_h=150)[0]
    assert (canvas[30:90, 20:120] == 42).all()


def test_place_cards_leaves_outside_area_white():
    """Pixels outside the pasted card remain white (255)."""
    card = np.full((60, 100, 3), 0, dtype=np.uint8)
    plan = LayoutPlan(
        variant=LayoutVariant.SINGLE_CARD,
        pages=[[CardPlacement(20, 30, rotated=False, card_index=0)]],
    )
    canvas = _place_cards([card], plan, sheet_w=200, sheet_h=150)[0]
    assert (canvas[:30, :] == 255).all()       # top strip
    assert (canvas[90:, :] == 255).all()       # bottom strip
    assert (canvas[:, :20] == 255).all()       # left strip
    assert (canvas[:, 120:] == 255).all()      # right strip


# --- _place_cards: rotation direction ---

def test_place_cards_rotates_card_clockwise():
    """A marker at top-left of the original ends up at top-right after CW rotation."""
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    card[0, 0] = (255, 255, 255)  # mark top-left pixel
    plan = LayoutPlan(
        variant=LayoutVariant.SINGLE_ROTATED,
        pages=[[CardPlacement(10, 10, rotated=True, card_index=0)]],
    )
    canvas = _place_cards([card], plan, sheet_w=150, sheet_h=150)[0]
    # Rotated card is 100 tall × 60 wide. Pasted at (x=10, y=10).
    # Top-right of pasted region: (y=10, x=10 + 60 - 1) = (10, 69).
    assert (canvas[10, 69] == 255).all()


def test_place_cards_does_not_rotate_when_not_requested():
    """Without rotation, the card keeps its original orientation."""
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    card[0, 0] = (255, 255, 255)
    plan = LayoutPlan(
        variant=LayoutVariant.SINGLE_CARD,
        pages=[[CardPlacement(10, 10, rotated=False, card_index=0)]],
    )
    canvas = _place_cards([card], plan, sheet_w=150, sheet_h=150)[0]
    assert (canvas[10, 10] == 255).all()  # marker still at top-left


# --- _place_cards: multiple placements ---

def test_place_cards_multiple_placements_same_page():
    """Two cards are pasted on the same page at distinct positions."""
    card_a = np.full((60, 100, 3), 10, dtype=np.uint8)
    card_b = np.full((60, 100, 3), 20, dtype=np.uint8)
    plan = LayoutPlan(
        variant=LayoutVariant.DUAL_SIDE_BY_SIDE,
        pages=[[
            CardPlacement(10, 10, rotated=False, card_index=0),
            CardPlacement(120, 10, rotated=False, card_index=1),
        ]],
    )
    canvas = _place_cards([card_a, card_b], plan, sheet_w=250, sheet_h=100)[0]
    assert (canvas[10:70, 10:110] == 10).all()
    assert (canvas[10:70, 120:220] == 20).all()


def test_place_cards_uses_card_index_not_iteration_order():
    """Cards are resolved by card_index, not by placement order."""
    card_a = np.full((60, 100, 3), 10, dtype=np.uint8)
    card_b = np.full((60, 100, 3), 20, dtype=np.uint8)
    plan = LayoutPlan(
        variant=LayoutVariant.DUAL_SIDE_BY_SIDE,
        pages=[[
            CardPlacement(10, 10, rotated=False, card_index=1),   # b at first position
            CardPlacement(120, 10, rotated=False, card_index=0),  # a at second
        ]],
    )
    canvas = _place_cards([card_a, card_b], plan, sheet_w=250, sheet_h=100)[0]
    assert (canvas[10:70, 10:110] == 20).all()
    assert (canvas[10:70, 120:220] == 10).all()


def test_place_cards_pages_are_independent():
    """Modifying one page does not affect another."""
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    plan = LayoutPlan(
        variant=LayoutVariant.SINGLE_CARD,
        pages=[
            [CardPlacement(10, 10, rotated=False, card_index=0)],
            [CardPlacement(10, 10, rotated=False, card_index=0)],
        ],
    )
    pages = _place_cards([card], plan, sheet_w=150, sheet_h=100)
    pages[0][0, 0] = 99
    assert tuple(pages[1][0, 0]) == (255, 255, 255)


# --- _place_cards: input immutability ---

def test_place_cards_does_not_mutate_input_cards():
    """The card arrays in the input list are not modified."""
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    card[0, 0] = (255, 255, 255)
    original = card.copy()
    plan = LayoutPlan(
        variant=LayoutVariant.SINGLE_ROTATED,
        pages=[[CardPlacement(10, 10, rotated=True, card_index=0)]],
    )
    _place_cards([card], plan, sheet_w=150, sheet_h=150)
    assert np.array_equal(card, original)


# --- _place_cards: card_index validation ---

def test_place_cards_rejects_card_index_out_of_range():
    """A card_index >= len(cards) raises ValueError."""
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    plan = LayoutPlan(
        variant=LayoutVariant.SINGLE_CARD,
        pages=[[CardPlacement(10, 10, rotated=False, card_index=1)]],
    )
    with pytest.raises(ValueError, match="card_index=1.*out of range.*1 cards"):
        _place_cards([card], plan, sheet_w=150, sheet_h=100)


def test_place_cards_rejects_negative_card_index():
    """A negative card_index is rejected."""
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    plan = LayoutPlan(
        variant=LayoutVariant.SINGLE_CARD,
        pages=[[CardPlacement(10, 10, rotated=False, card_index=-1)]],
    )
    with pytest.raises(ValueError, match="card_index=-1"):
        _place_cards([card], plan, sheet_w=150, sheet_h=100)


# --- _place_cards: bounds validation (delegated) ---

def test_place_cards_propagates_bounds_error():
    """An out-of-bounds placement raises ValueError from _validate_placement."""
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    plan = LayoutPlan(
        variant=LayoutVariant.SINGLE_CARD,
        pages=[[CardPlacement(200, 10, rotated=False, card_index=0)]],
    )
    with pytest.raises(ValueError, match="exceeds sheet width"):
        _place_cards([card], plan, sheet_w=150, sheet_h=100)


def test_place_cards_reports_card_index_error_before_bounds_error():
    """When both card_index and bounds are wrong, card_index wins."""
    card = np.zeros((60, 100, 3), dtype=np.uint8)
    plan = LayoutPlan(
        variant=LayoutVariant.SINGLE_CARD,
        pages=[[CardPlacement(200, 10, rotated=False, card_index=5)]],
    )
    with pytest.raises(ValueError, match="card_index=5"):
        _place_cards([card], plan, sheet_w=150, sheet_h=100)


# --- compose_sheet: cards list length ---

def test_compose_sheet_rejects_zero_cards():
    """An empty cards list is rejected."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    with pytest.raises(ValueError, match="Expected 1 or 2 cards, got 0"):
        compose_sheet([], sheet, margin_mm=10.0)


def test_compose_sheet_rejects_three_cards():
    """More than 2 cards is rejected."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    cards = [np.zeros((60, 100, 3), dtype=np.uint8) for _ in range(3)]
    with pytest.raises(ValueError, match="Expected 1 or 2 cards, got 3"):
        compose_sheet(cards, sheet, margin_mm=10.0)


def test_compose_sheet_rejects_four_cards():
    """The check is 'not in (1, 2)', so 4 is rejected too."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    cards = [np.zeros((60, 100, 3), dtype=np.uint8) for _ in range(4)]
    with pytest.raises(ValueError):
        compose_sheet(cards, sheet, margin_mm=10.0)


# --- compose_sheet: per-card shape validation ---

def test_compose_sheet_rejects_2d_card():
    """A 2D (grayscale) card is rejected with the card index in the message."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    with pytest.raises(ValueError, match=r"Card 0 must have shape \(H, W, 3\)"):
        compose_sheet([np.zeros((60, 100), dtype=np.uint8)], sheet, margin_mm=10.0)


def test_compose_sheet_rejects_rgba_card():
    """A 4-channel card is rejected (channel count mismatch)."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    with pytest.raises(ValueError, match=r"Card 0 must have shape"):
        compose_sheet([np.zeros((60, 100, 4), dtype=np.uint8)], sheet, margin_mm=10.0)


def test_compose_sheet_rejects_4d_card():
    """A 4D card is rejected."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    with pytest.raises(ValueError, match=r"Card 0 must have shape"):
        compose_sheet([np.zeros((60, 100, 3, 1), dtype=np.uint8)], sheet, margin_mm=10.0)


def test_compose_sheet_rejects_invalid_second_card_shape():
    """When card 1 is invalid, the error names index 1, not 0."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    valid = np.zeros((60, 100, 3), dtype=np.uint8)
    invalid = np.zeros((60, 100), dtype=np.uint8)
    with pytest.raises(ValueError, match=r"Card 1 must have shape"):
        compose_sheet([valid, invalid], sheet, margin_mm=10.0)


# --- compose_sheet: per-card dtype validation ---

def test_compose_sheet_rejects_float_card():
    """A float32 card is rejected with the dtype in the message."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    with pytest.raises(ValueError, match=r"Card 0 must have dtype uint8, got float32"):
        compose_sheet(
            [np.zeros((60, 100, 3), dtype=np.float32)], sheet, margin_mm=10.0
        )


def test_compose_sheet_rejects_invalid_second_card_dtype():
    """When card 1 has wrong dtype, the error names index 1."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    valid = np.zeros((60, 100, 3), dtype=np.uint8)
    invalid = np.zeros((60, 100, 3), dtype=np.int32)
    with pytest.raises(ValueError, match=r"Card 1 must have dtype uint8"):
        compose_sheet([valid, invalid], sheet, margin_mm=10.0)


# --- compose_sheet: shape uniformity ---

def test_compose_sheet_rejects_cards_with_different_shapes():
    """Two valid cards with different sizes are rejected."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    a = np.zeros((60, 100, 3), dtype=np.uint8)
    b = np.zeros((70, 100, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="All cards must have the same shape"):
        compose_sheet([a, b], sheet, margin_mm=10.0)


# --- compose_sheet: validation order ---

def test_compose_sheet_reports_length_error_before_card_validation():
    """Empty list: length error wins over per-card validation (which is vacuous)."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    with pytest.raises(ValueError, match="Expected 1 or 2 cards"):
        compose_sheet([], sheet, margin_mm=10.0)


def test_compose_sheet_reports_shape_error_before_uniformity():
    """A 2D card is reported as 'Card N must have shape', not as a uniformity error."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    valid = np.zeros((60, 100, 3), dtype=np.uint8)
    invalid = np.zeros((60, 100), dtype=np.uint8)
    # The per-card check catches it first, with the more specific message.
    with pytest.raises(ValueError, match=r"Card 1 must have shape"):
        compose_sheet([valid, invalid], sheet, margin_mm=10.0)


def test_compose_sheet_reports_first_invalid_card():
    """When both cards are invalid, the first one is reported."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    bad_a = np.zeros((60, 100), dtype=np.uint8)
    bad_b = np.zeros((60, 100, 3), dtype=np.float32)
    with pytest.raises(ValueError, match=r"Card 0"):
        compose_sheet([bad_a, bad_b], sheet, margin_mm=10.0)


# --- compose_sheet: return contract ---

def test_compose_sheet_returns_list_of_uint8_arrays():
    """The return value is a list of uint8 BGR arrays."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    card = np.zeros((638, 1011, 3), dtype=np.uint8)
    pages = compose_sheet([card], sheet, margin_mm=8.47)
    assert isinstance(pages, list)
    assert all(isinstance(p, np.ndarray) for p in pages)
    assert all(p.dtype == np.uint8 for p in pages)


def test_compose_sheet_pages_match_sheet_dimensions():
    """Every page has shape (sheet_h, sheet_w, 3)."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    card = np.zeros((638, 1011, 3), dtype=np.uint8)
    pages = compose_sheet([card], sheet, margin_mm=8.47)
    for page in pages:
        assert page.shape == (sheet.height_px, sheet.width_px, 3)


# --- compose_sheet: end-to-end with real pipeline parameters ---

def test_compose_sheet_end_to_end_with_ci_card_on_letter():
    """The realistic case: one CI card at 300 DPI on US Letter, margin 8.47mm."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    card_spec = CardSpec(width_mm=85.6, height_mm=53.98, dpi=300)
    card = np.full((card_spec.height_px, card_spec.width_px, 3), 42, dtype=np.uint8)

    pages = compose_sheet([card], sheet, margin_mm=8.47)

    assert len(pages) == 1
    canvas = pages[0]
    # margin_px = round(8.47/25.4*300) = 100. SINGLE_CARD layout.
    # Card placed at x=(2550-1011)//2=769, y=100.
    assert (canvas[100:100+card_spec.height_px, 769:769+card_spec.width_px] == 42).all()
    # Top margin strip is white.
    assert (canvas[:100] == 255).all()


def test_compose_sheet_two_ci_cards_fit_side_by_side():
    """Two CI cards fit side-by-side on US Letter at 300 DPI."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    card_spec = CardSpec(width_mm=85.6, height_mm=53.98, dpi=300)
    card = np.full((card_spec.height_px, card_spec.width_px, 3), 42, dtype=np.uint8)

    pages = compose_sheet([card, card], sheet, margin_mm=8.47)

    assert len(pages) == 1
    canvas = pages[0]
    # DUAL_SIDE_BY_SIDE: actual_margin_w=(2550-2022)//3=176
    # x1=176, x2=176+1011+176=1363, y=100.
    assert (canvas[100, 176] == 42).all()
    assert (canvas[100, 1363] == 42).all()


def test_compose_sheet_two_ci_cards_with_large_margin_produce_two_pages():
    """A margin large enough to defeat both dual layouts falls back to 2 pages."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    card_spec = CardSpec(width_mm=85.6, height_mm=53.98, dpi=300)
    card = np.full((card_spec.height_px, card_spec.width_px, 3), 42, dtype=np.uint8)

    # margin_mm=60 → margin_px≈709. DUAL fails both orientations; SINGLE fits.
    pages = compose_sheet([card, card], sheet, margin_mm=60.0)

    assert len(pages) == 2


# --- compose_sheet: margin conversion ---

def test_compose_sheet_margin_converts_to_expected_pixels():
    """margin_mm is converted via MM_PER_INCH and sheet DPI, verified by position."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    card = np.full((200, 400, 3), 42, dtype=np.uint8)

    # margin_mm=8.47 → margin_px=100. Small card → SINGLE_CARD.
    # Card placed at y=100, so canvas[:100] is white and canvas[100, x] is card.
    pages = compose_sheet([card], sheet, margin_mm=8.47)
    canvas = pages[0]
    # x = (2550-400)//2 = 1075
    assert (canvas[99, 1075] == 255).all()
    assert (canvas[100, 1075] == 42).all()


def test_compose_sheet_doubling_margin_doubles_vertical_offset():
    """With SINGLE_CARD, doubling margin_mm doubles the card's y position."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    card = np.full((200, 400, 3), 42, dtype=np.uint8)

    # margin_mm=8.47 → y=100; margin_mm=16.94 → y=200.
    canvas_1 = compose_sheet([card], sheet, margin_mm=8.47)[0]
    canvas_2 = compose_sheet([card], sheet, margin_mm=16.94)[0]
    x = (2550 - 400) // 2
    assert (canvas_1[100, x] == 42).all()
    assert (canvas_2[200, x] == 42).all()
    assert (canvas_2[100, x] == 255).all()  # top strip is now bigger


# --- compose_sheet: card dimensions used with correct orientation ---

def test_compose_sheet_uses_card_shape_h_w_correctly():
    """A non-square card is laid out with its real width and height (not swapped)."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    # 400 wide, 200 tall: shape (200, 400, 3)
    card = np.full((200, 400, 3), 42, dtype=np.uint8)

    canvas = compose_sheet([card], sheet, margin_mm=8.47)[0]

    # Correct: x=(2550-400)//2=1075. If orientation were swapped,
    # x=(2550-200)//2=1175, and the card would appear at the wrong place.
    assert (canvas[100:300, 1075:1475] == 42).all()
    assert (canvas[100:300, 1175] == 42).all()   # inside; 1175+200=1375 < 1475
    assert (canvas[100, 1075] == 42).all()       # leftmost card pixel
    assert (canvas[100, 1074] == 255).all()      # just left of the card


# --- compose_sheet: error propagation ---

def test_compose_sheet_propagates_margin_type_error():
    """A non-numeric margin_mm raises TypeError from _validate_margin_mm."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    card = np.zeros((200, 400, 3), dtype=np.uint8)
    with pytest.raises(TypeError, match="margin_mm must be a number"):
        compose_sheet([card], sheet, margin_mm="8.47")


@pytest.mark.parametrize("margin_mm", [0, -5, float("nan"), float("inf")])
def test_compose_sheet_propagates_margin_value_error(margin_mm):
    """A zero, negative, or non-finite margin_mm raises ValueError."""
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    card = np.zeros((200, 400, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        compose_sheet([card], sheet, margin_mm=margin_mm)


def test_compose_sheet_propagates_card_does_not_fit_error():
    """A sheet too small for even a rotated card raises CardDoesNotFitError."""
    small_sheet = SheetSpec(width_mm=30, height_mm=30, dpi=300)  # ~354x354 px
    card = np.zeros((500, 500, 3), dtype=np.uint8)
    with pytest.raises(CardDoesNotFitError):
        compose_sheet([card], small_sheet, margin_mm=5.0)


def test_compose_sheet_no_filesystem_side_effects_on_error():
    """All validation happens before any rendering (no partial state leaks)."""
    # This test is really about the structure: exceptions raised before
    # _place_cards is called mean no pages are returned.
    sheet = SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300)
    card = np.zeros((200, 400, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        result = compose_sheet([card], sheet, margin_mm=-1)
        assert result is None  # never reached
