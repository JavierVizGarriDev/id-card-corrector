import numpy as np
import pytest
import math
from id_card_corrector.geometry import (
    _check_corners_shape,
    validate_quadrilateral,
    _is_self_intersecting,
    DegenerateQuadrilateralError,
    Issue,
    MAX_ASPECT_RATIO,  
    MIN_SIDE_PX,      
    MIN_AREA_PX2,
)


# --- Module invariants ---

def test_all_validation_constants_are_integers():
    """All validation constants must be integer-valued.

    Pixels are atomic units: MIN_SIDE_PX and MIN_AREA_PX2 are naturally
    integers. MAX_ASPECT_RATIO is a ratio, but we enforce integer values
    by convention so that boundary tests can construct exact boundaries.
    """
    assert MIN_AREA_PX2 == int(MIN_AREA_PX2), (
        f"MIN_AREA_PX2 must be integer-valued, got {MIN_AREA_PX2}"
    )
    assert MIN_SIDE_PX == int(MIN_SIDE_PX), (
        f"MIN_SIDE_PX must be integer-valued, got {MIN_SIDE_PX}"
    )
    assert MAX_ASPECT_RATIO == int(MAX_ASPECT_RATIO), (
        f"MAX_ASPECT_RATIO must be integer-valued, got {MAX_ASPECT_RATIO}"
    )


def test_min_side_px_is_at_least_two():
    """MIN_SIDE_PX must be >= 2 to allow testing "clearly below minimum".

    If MIN_SIDE_PX were 1, the test "tiny_side_alone" would construct a
    side of int(1 * 0.5) = 0, which collapses the quadrilateral to zero
    area (triggering DegenerateQuadrilateralError instead of TINY_SIDE).
    """
    assert MIN_SIDE_PX >= 2, (
        f"MIN_SIDE_PX must be >= 2 to avoid degenerate test geometry, "
        f"got {MIN_SIDE_PX}"
    )


def test_area_to_ratio_relationship():
    """MIN_AREA_PX2 must be <= MAX_ASPECT_RATIO for threshold tests.

    The test test_at_area_threshold_returns_only_tiny_side constructs a
    rectangle of width 1 and height MIN_AREA_PX2. Its aspect ratio is
    MIN_AREA_PX2 / 1 = MIN_AREA_PX2. If this exceeds MAX_ASPECT_RATIO,
    the test would trigger EXTREME_ASPECT_RATIO instead of just TINY_SIDE.
    """
    assert MIN_AREA_PX2 <= MAX_ASPECT_RATIO, (
        f"MIN_AREA_PX2 ({MIN_AREA_PX2}) must be <= MAX_ASPECT_RATIO "
        f"({MAX_ASPECT_RATIO}) to avoid triggering EXTREME_ASPECT_RATIO "
        f"in the area threshold test."
    )


# --- _check_corners_shape: happy path ---

@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int32, np.int64])
def test_check_corners_shape_accepts_valid_shape_and_dtype(dtype):
    """A (4, 2) array is accepted regardless of numeric dtype."""
    corners = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=dtype)
    _check_corners_shape(corners)  # should not raise


# --- _check_corners_shape: non-array input raises TypeError ---

def test_check_corners_shape_rejects_list_with_message():
    """A plain Python list is rejected with a clear TypeError."""
    with pytest.raises(TypeError, match="corners must be a numpy array"):
        _check_corners_shape([[0, 0], [10, 0], [10, 10], [0, 10]])


@pytest.mark.parametrize("bad_input", [
    ((0, 0), (10, 0), (10, 10), (0, 10)),  # tuple of tuples
    None,
    42,
    "corners",
    object(),
])
def test_check_corners_shape_rejects_non_array_types(bad_input):
    """Any non-ndarray input is rejected with TypeError."""
    with pytest.raises(TypeError):
        _check_corners_shape(bad_input)


# --- _check_corners_shape: wrong shape raises ValueError ---

def test_check_corners_shape_rejects_wrong_shape_with_message():
    """A (3, 2) array is rejected with a clear ValueError."""
    with pytest.raises(ValueError, match=r"must have shape \(4, 2\)"):
        _check_corners_shape(np.array([[0, 0], [10, 0], [10, 10]], dtype=np.float32))


@pytest.mark.parametrize("shape", [
    (3, 2),     # too few corners
    (5, 2),     # too many corners
    (4, 3),     # wrong coordinate dimension
    (4,),       # flat array
    (4, 2, 1),  # extra dimension
    (0, 2),     # empty
    (4, 0),     # empty
    (),         # scalar
])
def test_check_corners_shape_rejects_all_wrong_shapes(shape):
    """Any shape other than (4, 2) is rejected with ValueError."""
    with pytest.raises(ValueError):
        _check_corners_shape(np.zeros(shape, dtype=np.float32))


# --- _check_corners_shape: structural, not numeric, validation ---

def test_check_corners_shape_ignores_numeric_values():
    """The check is structural: inf/nan values are not its concern."""
    corners = np.array([
        [np.inf, 0],
        [10, np.nan],
        [10, 10],
        [0, 10],
    ], dtype=np.float32)
    _check_corners_shape(corners)  # should not raise


# --- validate_quadrilateral: happy path ---

def test_validate_square_returns_empty_tuple():
    """A large, simple square passes validation with no issues."""
    square = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.float64)
    assert validate_quadrilateral(square) == ()


def test_validate_rectangle_returns_empty_tuple():
    """A rectangle well within all thresholds has no issues."""
    rect = np.array([[0, 0], [150, 0], [150, 100], [0, 100]], dtype=np.float64)
    assert validate_quadrilateral(rect) == ()


def test_validate_does_not_mutate_corners():
    """validate_quadrilateral must be a pure function (no side effects).
    
    It should not modify the corners array in place. Using a non-trivial
    input ensures that mutations (like zeroing out or sorting) are caught.
    """
    # Usamos un cuadrilátero válido pero con valores no triviales
    corners = np.array([[10, 10], [90, 15], [85, 95], [15, 90]], dtype=np.float32)
    original_corners = corners.copy()
    
    validate_quadrilateral(corners)
    
    np.testing.assert_array_equal(corners, original_corners)

# --- validate_quadrilateral: shape validation is delegated ---

def test_validate_rejects_non_array_with_type_error():
    """Non-ndarray input is rejected with TypeError."""
    with pytest.raises(TypeError):
        validate_quadrilateral([[0, 0], [1, 0], [1, 1], [0, 1]])


def test_validate_rejects_wrong_shape_with_value_error():
    """Array with wrong shape is rejected with ValueError."""
    with pytest.raises(ValueError):
        validate_quadrilateral(np.array([[0, 0], [1, 0], [1, 1]], dtype=np.float64))


# --- validate_quadrilateral: self-intersection takes priority ---

def test_symmetric_bowtie_is_self_intersecting_and_does_not_raise():
    """A symmetric bowtie has zero shoelace area but must not raise DegenerateError."""
    bowtie = np.array([[0, 0], [100, 100], [100, 0], [0, 100]], dtype=np.float64)
    assert validate_quadrilateral(bowtie) == (Issue.SELF_INTERSECTING,)


def test_asymmetric_bowtie_is_self_intersecting_and_skips_other_checks():
    """Self-intersection short-circuits: no aspect ratio or tiny side issues."""
    # Asymmetric bowtie with non-trivial area
    bowtie = np.array([[0, 0], [200, 5], [200, 0], [0, 5]], dtype=np.float64)
    assert validate_quadrilateral(bowtie) == (Issue.SELF_INTERSECTING,)


def test_concave_quadrilateral_is_not_flagged_as_self_intersecting():
    """A concave but simple quadrilateral is evaluated normally."""
    concave = np.array([[0, 0], [100, 0], [100, 100], [50, 50]], dtype=np.float64)
    result = validate_quadrilateral(concave)
    assert Issue.SELF_INTERSECTING not in result


# --- validate_quadrilateral: area threshold ---

def test_tiny_square_raises_degenerate_error():
    """Area below MIN_AREA_PX2 raises DegenerateQuadrilateralError."""
    # Construimos un cuadrado cuya área sea exactamente la mitad del mínimo.
    # El float epsilon de sqrt es seguro aquí porque estamos muy por debajo del umbral.
    side = math.sqrt(MIN_AREA_PX2 * 0.5)
    tiny = np.array([[0, 0], [side, 0], [side, side], [0, side]], dtype=np.float64)
    with pytest.raises(DegenerateQuadrilateralError):
        validate_quadrilateral(tiny)


def test_collapsed_point_raises_degenerate_error():
    """Zero area raises DegenerateQuadrilateralError."""
    collapsed = np.array([[5, 5], [5, 5], [5, 5], [5, 5]], dtype=np.float64)
    with pytest.raises(DegenerateQuadrilateralError):
        validate_quadrilateral(collapsed)


def test_validate_rejects_collinear_overlap_via_area():
    """A quadrilateral with overlapping collinear sides is rejected by area.

    _segments_intersect intentionally does not handle collinearity (out
    of contract). The system relies on the area check to catch this
    degenerate geometry as a fatal error.
    """
    collinear_overlap = np.array(
        [[0, 0], [10, 0], [5, 0], [15, 0]],
        dtype=np.float64,
    )

    # Premise: collinear overlap is NOT detected as self-intersection
    assert _is_self_intersecting(collinear_overlap) is False, (
        "_segments_intersect now handles collinearity. This changes the "
        "design: re-evaluate whether the area check is still the right "
        "safety net, or if validate_quadrilateral should be reordered."
    )

    # Consequence: the area check catches it as a fatal error.
    with pytest.raises(DegenerateQuadrilateralError):
        validate_quadrilateral(collinear_overlap)


def test_at_area_threshold_returns_only_tiny_side():
    """Area == MIN_AREA_PX2 is not degenerate (strict <), but TINY_SIDE applies.
    
    We construct a rectangle of width 1 and height MIN_AREA_PX2.
    Since MIN_SIDE_PX >= 2 (invariant), the side of 1 always triggers TINY_SIDE.
    The aspect ratio is MIN_AREA_PX2 / 1 = MIN_AREA_PX2, which is guaranteed
    to be <= MAX_ASPECT_RATIO by the invariant test_area_to_ratio_relationship.
    """
    width = 1
    height = int(MIN_AREA_PX2)
    
    quad = np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float64)
    
    assert validate_quadrilateral(quad) == (Issue.TINY_SIDE,)


# --- validate_quadrilateral: EXTREME_ASPECT_RATIO ---

def test_extreme_aspect_ratio_alone():
    """A thin but long quadrilateral only reports EXTREME_ASPECT_RATIO.

    Assumes MIN_SIDE_PX is an integer (pixels are atomic units).
    """
    height = int(MIN_SIDE_PX * 1.1)  # Just above the minimum
    width = int(MAX_ASPECT_RATIO * height * 2)  # Double the allowed ratio
    thin = np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float64)
    assert validate_quadrilateral(thin) == (Issue.EXTREME_ASPECT_RATIO,)


def test_aspect_ratio_just_above_threshold():
    """Ratio marginally above the threshold triggers the issue.

    Assumes MIN_SIDE_PX is an integer. The +1 guarantees width > ratio * height,
    so the ratio is strictly greater than MAX_ASPECT_RATIO.
    """
    height = int(MIN_SIDE_PX * 1.1)
    width = int(MAX_ASPECT_RATIO * height) + 1
    thin = np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float64)
    assert validate_quadrilateral(thin) == (Issue.EXTREME_ASPECT_RATIO,)


def test_aspect_ratio_exactly_at_threshold_does_not_trigger():
    """Ratio == MAX_ASPECT_RATIO does not trigger the issue (strict >).

    Requires MAX_ASPECT_RATIO * height to be an integer so the actual
    ratio is exactly MAX_ASPECT_RATIO. This is guaranteed by the
    invariant "all validation constants are integer-valued"
    (enforced by test_all_validation_constants_are_integers).
    """
    height = int(MIN_SIDE_PX * 1.1)
    width = int(MAX_ASPECT_RATIO * height)  # Exactly at the threshold
    rect = np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float64)
    assert validate_quadrilateral(rect) == ()


def test_aspect_ratio_below_threshold_does_not_trigger():
    """Ratio below the threshold is fine."""
    height = int(MIN_SIDE_PX * 1.1)
    width = int(MAX_ASPECT_RATIO * height * 0.8)  # 20% below
    rect = np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float64)
    assert validate_quadrilateral(rect) == ()


# --- validate_quadrilateral: TINY_SIDE ---

def test_tiny_side_alone():
    """A short side triggers TINY_SIDE without aspect ratio issue.
    
    Uses a side 50% below MIN_SIDE_PX. Width is chosen so the ratio
    stays well below MAX_ASPECT_RATIO (to avoid EXTREME_ASPECT_RATIO).
    """
    short_side = int(MIN_SIDE_PX * 0.5) 
    width = int(MAX_ASPECT_RATIO * short_side * 0.25)
    
    quad = np.array([[0, 0], [width, 0], [width, short_side], [0, short_side]], dtype=np.float64)
    assert validate_quadrilateral(quad) == (Issue.TINY_SIDE,)


def test_tiny_side_just_below_threshold():
    """Min side exactly 1 pixel below threshold triggers TINY_SIDE."""
    # Restamos 1 píxel (respetando la invariante de enteros)
    short_side = MIN_SIDE_PX - 1
    
    # Ancho derivado de MAX_ASPECT_RATIO para evitar EXTREME_ASPECT_RATIO
    width = int(MAX_ASPECT_RATIO * short_side * 0.5)
    
    quad = np.array([[0, 0], [width, 0], [width, short_side], [0, short_side]], dtype=np.float64)
    assert validate_quadrilateral(quad) == (Issue.TINY_SIDE,)


def test_min_side_exactly_at_threshold_does_not_trigger():
    """Min side == MIN_SIDE_PX does not trigger (strict <)."""
    # Ancho derivado de MAX_ASPECT_RATIO (consistente con los otros tests)
    width = int(MIN_SIDE_PX * MAX_ASPECT_RATIO * 0.5)
    
    quad = np.array([[0, 0], [width, 0], [width, MIN_SIDE_PX], [0, MIN_SIDE_PX]], dtype=np.float64)
    assert validate_quadrilateral(quad) == ()


# --- validate_quadrilateral: combined issues ---

def _build_combined_issues_quad():
    """Helper to build a quad that triggers both EXTREME_ASPECT_RATIO and TINY_SIDE.
    
    The short side is guaranteed to be below MIN_SIDE_PX (to trigger TINY_SIDE).
    The long side is guaranteed to be above MAX_ASPECT_RATIO * short_side
    (to trigger EXTREME_ASPECT_RATIO), while keeping the long side integer.
    """
    
    # La invariante MIN_SIDE_PX >= 2 garantiza que int(MIN * 0.5) >= 1
    short_side = int(MIN_SIDE_PX * 0.5)
    # +1 es el mínimo matemático para garantizar que la ratio sea estrictamente mayor
    long_side = int(MAX_ASPECT_RATIO * short_side) + 1
    return np.array([[0, 0], [long_side, 0], [long_side, short_side], [0, short_side]], dtype=np.float64)


def test_combined_issues_have_correct_composition_and_order():
    """Both non-fatal issues are reported, in the correct order.
    
    Tuple equality in Python implies order: (A, B) == (A, B) but
    (A, B) != (B, A). So this single assertion covers both composition
    (which issues appear) and order (EXTREME before TINY).
    """
    quad = _build_combined_issues_quad()
    result = validate_quadrilateral(quad)
    assert result == (Issue.EXTREME_ASPECT_RATIO, Issue.TINY_SIDE)

# --- validate_quadrilateral: return type ---

def test_validate_returns_tuple():
    """Return type is always a tuple, even when empty."""
    square = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.float64)
    result = validate_quadrilateral(square)
    assert isinstance(result, tuple)


def test_validate_returns_tuple_of_issue_members():
    """Every element in the result is an Issue member."""
    quad = _build_combined_issues_quad()
    result = validate_quadrilateral(quad)
    # Evita que el test pase en vacuo si el helper devuelve una tupla vacía
    assert len(result) > 0, "Helper produced no issues; test would be vacuous"
    assert all(isinstance(item, Issue) for item in result)