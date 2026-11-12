import numpy as np
import pytest
from id_card_corrector.geometry import (
    _check_corners_shape,
    validate_quadrilateral,
    _is_self_intersecting,
    DegenerateQuadrilateralError,
    Issue,
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
    tiny = np.array([[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5]], dtype=np.float64)
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
    # (_segments_intersect intentionally skips collinear cases).
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
    
    A unit square has area 1.0 (exactly the threshold) so it must NOT
    raise DegenerateQuadrilateralError. However, its sides are 1 px
    (well below MIN_SIDE_PX), so it MUST return exactly TINY_SIDE.
    """
    unit = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float64)
    
    assert validate_quadrilateral(unit) == (Issue.TINY_SIDE,)


# --- validate_quadrilateral: EXTREME_ASPECT_RATIO ---

def test_extreme_aspect_ratio_alone():
    """A thin but long quadrilateral only reports EXTREME_ASPECT_RATIO."""
    # 221 x 11: ratio = 221/11 ≈ 20.09 > 20, min side = 11 >= 10
    thin = np.array([[0, 0], [221, 0], [221, 11], [0, 11]], dtype=np.float64)
    assert validate_quadrilateral(thin) == (Issue.EXTREME_ASPECT_RATIO,)


def test_aspect_ratio_just_above_threshold():
    """Ratio marginally above 20 triggers the issue."""
    # 201 x 10: ratio = 20.1 > 20, min side = 10 (no TINY_SIDE)
    thin = np.array([[0, 0], [201, 0], [201, 10], [0, 10]], dtype=np.float64)
    assert validate_quadrilateral(thin) == (Issue.EXTREME_ASPECT_RATIO,)


def test_aspect_ratio_exactly_at_threshold_does_not_trigger():
    """Ratio == MAX_ASPECT_RATIO does not trigger the issue (strict >)."""
    # 200 x 10: ratio = 20 exactly, min side = 10
    rect = np.array([[0, 0], [200, 0], [200, 10], [0, 10]], dtype=np.float64)
    assert validate_quadrilateral(rect) == ()


def test_aspect_ratio_below_threshold_does_not_trigger():
    """Ratio below 20 is fine."""
    rect = np.array([[0, 0], [150, 0], [150, 10], [0, 10]], dtype=np.float64)
    assert validate_quadrilateral(rect) == ()


# --- validate_quadrilateral: TINY_SIDE ---

def test_tiny_side_alone():
    """A short side triggers TINY_SIDE without aspect ratio issue."""
    # 100 x 5: ratio = 20 (no EXTREME), min side = 5 < 10
    quad = np.array([[0, 0], [100, 0], [100, 5], [0, 5]], dtype=np.float64)
    assert validate_quadrilateral(quad) == (Issue.TINY_SIDE,)


def test_tiny_side_just_below_threshold():
    """Min side marginally below 10 triggers TINY_SIDE."""
    quad = np.array([[0, 0], [100, 0], [100, 9.99], [0, 9.99]], dtype=np.float64)
    assert validate_quadrilateral(quad) == (Issue.TINY_SIDE,)


def test_min_side_exactly_at_threshold_does_not_trigger():
    """Min side == MIN_SIDE_PX does not trigger (strict <)."""
    quad = np.array([[0, 0], [100, 0], [100, 10], [0, 10]], dtype=np.float64)
    # ratio = 10 (no EXTREME), min side = 10 (no TINY)
    assert validate_quadrilateral(quad) == ()


# --- validate_quadrilateral: combined issues ---

def test_extreme_aspect_ratio_and_tiny_side_together():
    """Both non-fatal issues are reported together."""
    # 1000 x 5: ratio = 200 > 20, min side = 5 < 10
    quad = np.array([[0, 0], [1000, 0], [1000, 5], [0, 5]], dtype=np.float64)
    assert validate_quadrilateral(quad) == (
        Issue.EXTREME_ASPECT_RATIO,
        Issue.TINY_SIDE,
    )


def test_combined_issues_preserve_order():
    """Issue order in the tuple matches the order of checks in the function."""
    quad = np.array([[0, 0], [1000, 0], [1000, 5], [0, 5]], dtype=np.float64)
    result = validate_quadrilateral(quad)
    assert result[0] is Issue.EXTREME_ASPECT_RATIO
    assert result[1] is Issue.TINY_SIDE


# --- validate_quadrilateral: return type ---

def test_validate_returns_tuple():
    """Return type is always a tuple, even when empty."""
    square = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.float64)
    result = validate_quadrilateral(square)
    assert isinstance(result, tuple)


def test_validate_returns_tuple_of_issue_members():
    """Every element in the result is an Issue member."""
    quad = np.array([[0, 0], [1000, 0], [1000, 5], [0, 5]], dtype=np.float64)
    result = validate_quadrilateral(quad)
    assert all(isinstance(item, Issue) for item in result)
