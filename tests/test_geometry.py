"""Tests for the geometry module."""

import numpy as np
import pytest
from id_card_corrector.geometry import (
    _check_corners_shape,
    _cross_product_2d,
    _segments_intersect,
    _polygon_area,
    _side_lengths,
    _aspect_ratio,
    _min_side_length,
    _is_self_intersecting,
    validate_quadrilateral,
    warp_to_rectangle,
    DegenerateQuadrilateralError,
    Issue
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

# --- _cross_product_2d: sign indicates orientation ---

def test_cross_product_2d_positive_when_point_is_left():
    """p3 to the left of p1->p2 yields a positive value."""
    p1 = np.array([0, 0])
    p2 = np.array([10, 0])
    p3 = np.array([5, 5])
    assert _cross_product_2d(p1, p2, p3) > 0


def test_cross_product_2d_negative_when_point_is_right():
    """p3 to the right of p1->p2 yields a negative value."""
    p1 = np.array([0, 0])
    p2 = np.array([10, 0])
    p3 = np.array([5, -5])
    assert _cross_product_2d(p1, p2, p3) < 0


def test_cross_product_2d_zero_when_collinear():
    """p3 on the line through p1 and p2 yields zero."""
    p1 = np.array([0, 0])
    p2 = np.array([10, 0])
    p3 = np.array([5, 0])
    assert _cross_product_2d(p1, p2, p3) == 0.0


@pytest.mark.parametrize("p1, p2, p3, expected_sign", [
    # Horizontal segment
    ((0, 0), (10, 0), (5, 5), 1),
    ((0, 0), (10, 0), (5, -5), -1),
    # Vertical segment
    ((0, 0), (0, 10), (-5, 5), 1),
    ((0, 0), (0, 10), (5, 5), -1),
    # Diagonal segment
    ((0, 0), (10, 10), (0, 10), 1),
    ((0, 0), (10, 10), (10, 0), -1),
])
def test_cross_product_2d_sign_for_various_orientations(p1, p2, p3, expected_sign):
    """Sign matches the side of p3 relative to p1->p2."""
    result = _cross_product_2d(
        np.array(p1, dtype=np.float64),
        np.array(p2, dtype=np.float64),
        np.array(p3, dtype=np.float64),
    )
    assert (result > 0) if expected_sign > 0 else (result < 0)


# --- _cross_product_2d: zero cases ---

@pytest.mark.parametrize("p3", [
    (0, 0),   # coincides with p1
    (5, 0),   # midpoint
    (10, 0),  # coincides with p2
    (100, 0), # beyond p2, still on the line
])
def test_cross_product_2d_zero_for_points_on_the_line(p3):
    """Any p3 collinear with p1 and p2 yields zero."""
    p1 = np.array([0, 0])
    p2 = np.array([10, 0])
    result = _cross_product_2d(p1, p2, np.array(p3))
    assert result == 0.0


def test_cross_product_2d_zero_when_p1_equals_p2():
    """Degenerate segment: any p3 yields zero."""
    p1 = np.array([3, 4])
    p2 = np.array([3, 4])
    p3 = np.array([10, 20])
    assert _cross_product_2d(p1, p2, p3) == 0.0


# --- _cross_product_2d: exact value ---

def test_cross_product_2d_returns_exact_parallelogram_area():
    """The magnitude equals the area of the parallelogram spanned by the vectors."""
    p1 = np.array([0, 0])
    p2 = np.array([3, 0])
    p3 = np.array([0, 4])
    # (3, 0) x (0, 4) = 3*4 - 0*0 = 12
    assert _cross_product_2d(p1, p2, p3) == pytest.approx(12.0)


def test_cross_product_2d_translation_invariant():
    """Translating all three points by the same vector does not change the result."""
    p1 = np.array([0, 0])
    p2 = np.array([3, 0])
    p3 = np.array([0, 4])
    offset = np.array([1000, -500])
    assert _cross_product_2d(p1, p2, p3) == pytest.approx(
        _cross_product_2d(p1 + offset, p2 + offset, p3 + offset)
    )


# --- _cross_product_2d: dtype independence and return type ---

@pytest.mark.parametrize("dtype", [np.int32, np.int64, np.float32, np.float64])
def test_cross_product_2d_accepts_various_dtypes(dtype):
    """Result is the same regardless of the input dtype."""
    p1 = np.array([0, 0], dtype=dtype)
    p2 = np.array([10, 0], dtype=dtype)
    p3 = np.array([5, 5], dtype=dtype)
    assert _cross_product_2d(p1, p2, p3) == pytest.approx(50.0)


def test_cross_product_2d_returns_python_float():
    """The return type is a Python float, not a numpy scalar."""
    p1 = np.array([0, 0], dtype=np.int32)
    p2 = np.array([10, 0], dtype=np.int32)
    p3 = np.array([5, 5], dtype=np.int32)
    result = _cross_product_2d(p1, p2, p3)
    assert isinstance(result, float)

# --- _segments_intersect: clean crossings ---

def test_segments_intersect_for_crossing_diagonals():
    """Two diagonals of a square cross at their midpoint."""
    p1, p2 = np.array([0, 0]), np.array([10, 10])
    p3, p4 = np.array([0, 10]), np.array([10, 0])
    assert _segments_intersect(p1, p2, p3, p4) is True


def test_segments_intersect_for_t_shape_crossing():
    """A vertical segment crossing a horizontal one in its interior."""
    p1, p2 = np.array([0, 0]), np.array([10, 0])
    p3, p4 = np.array([5, -5]), np.array([5, 5])
    assert _segments_intersect(p1, p2, p3, p4) is True


def test_segments_intersect_is_symmetric():
    """Swapping the two segments does not change the result."""
    p1, p2 = np.array([0, 0]), np.array([10, 10])
    p3, p4 = np.array([0, 10]), np.array([10, 0])
    assert _segments_intersect(p1, p2, p3, p4) == _segments_intersect(p3, p4, p1, p2)


# --- _segments_intersect: no crossing ---

@pytest.mark.parametrize("p1, p2, p3, p4", [
    # Disjoint horizontally
    ((0, 0), (5, 5), (10, 0), (15, 5)),
    # Parallel, no overlap
    ((0, 0), (10, 0), (0, 5), (10, 5)),
    # Far apart
    ((0, 0), (1, 1), (100, 100), (101, 101)),
])
def test_segments_do_not_intersect_when_disjoint(p1, p2, p3, p4):
    """Disjoint segments report no intersection."""
    assert _segments_intersect(
        np.array(p1, dtype=np.float64),
        np.array(p2, dtype=np.float64),
        np.array(p3, dtype=np.float64),
        np.array(p4, dtype=np.float64),
    ) is False


# --- _segments_intersect: documented out-of-contract cases ---

def test_segments_sharing_endpoint_return_false():
    """Endpoint contact is out of contract and returns False."""
    p1, p2 = np.array([0, 0]), np.array([10, 0])
    p3, p4 = np.array([10, 0]), np.array([10, 10])
    assert _segments_intersect(p1, p2, p3, p4) is False


def test_endpoint_touching_other_segment_interior_returns_false():
    """An endpoint lying exactly on the other segment is treated as no crossing."""
    p1, p2 = np.array([0, 0]), np.array([10, 0])
    p3, p4 = np.array([5, 0]), np.array([5, 10])
    assert _segments_intersect(p1, p2, p3, p4) is False


def test_identical_segments_return_false():
    """Two identical segments are collinear and out of contract."""
    p1, p2 = np.array([0, 0]), np.array([10, 0])
    assert _segments_intersect(p1, p2, p1, p2) is False


def test_partially_overlapping_collinear_segments_return_false():
    """Collinear overlap is out of contract and returns False."""
    p1, p2 = np.array([0, 0]), np.array([10, 0])
    p3, p4 = np.array([5, 0]), np.array([15, 0])
    assert _segments_intersect(p1, p2, p3, p4) is False


# --- _segments_intersect: degenerate inputs ---

def test_degenerate_segment_returns_false():
    """A point (zero-length segment) never crosses a real segment."""
    p1, p2 = np.array([5, 5]), np.array([5, 5])  # degenerate
    p3, p4 = np.array([0, 0]), np.array([10, 10])
    assert _segments_intersect(p1, p2, p3, p4) is False

# --- _polygon_area: exact values ---

def test_polygon_area_of_unit_square():
    """A 1x1 square has area 1."""
    square = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float64)
    assert _polygon_area(square) == pytest.approx(1.0)


def test_polygon_area_of_square():
    """A 10x10 square has area 100."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    assert _polygon_area(square) == pytest.approx(100.0)


def test_polygon_area_of_rectangle():
    """A 20x5 rectangle has area 100."""
    rect = np.array([[0, 0], [20, 0], [20, 5], [0, 5]], dtype=np.float64)
    assert _polygon_area(rect) == pytest.approx(100.0)


def test_polygon_area_of_rotated_square_is_preserved():
    """Rotating the vertices does not change the area (90-degree rotation)."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    # Rotate 90 degrees around origin: (x, y) -> (-y, x)
    rotated = np.array([[-y, x] for x, y in square], dtype=np.float64)
    assert _polygon_area(rotated) == pytest.approx(100.0)


# --- _polygon_area: order independence ---

def test_polygon_area_is_independent_of_winding_order():
    """CW and CCW orderings yield the same area."""
    ccw = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    cw = np.array([[0, 10], [10, 10], [10, 0], [0, 0]], dtype=np.float64)
    assert _polygon_area(ccw) == pytest.approx(_polygon_area(cw))


@pytest.mark.parametrize("start_index", [0, 1, 2, 3])
def test_polygon_area_is_independent_of_starting_vertex(start_index):
    """Rotating which vertex comes first does not change the area."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    rolled = np.roll(square, -start_index, axis=0)
    assert _polygon_area(rolled) == pytest.approx(100.0)


# --- _polygon_area: zero-area cases ---

def test_polygon_area_of_collapsed_point_is_zero():
    """All vertices at the same coordinate -> area 0."""
    collapsed = np.array([[5, 5], [5, 5], [5, 5], [5, 5]], dtype=np.float64)
    assert _polygon_area(collapsed) == 0.0


def test_polygon_area_of_collinear_vertices_is_zero():
    """All vertices on a straight line -> area 0."""
    collinear = np.array([[0, 0], [5, 0], [10, 0], [15, 0]], dtype=np.float64)
    assert _polygon_area(collinear) == 0.0


def test_polygon_area_with_three_equal_vertices_is_zero():
    """A 'triangle' with three identical vertices -> area 0."""
    triangle = np.array([[0, 0], [0, 0], [0, 0], [10, 0]], dtype=np.float64)
    assert _polygon_area(triangle) == 0.0


# --- _polygon_area: geometric invariants ---

def test_polygon_area_is_translation_invariant():
    """Translating all vertices by the same offset does not change the area."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    offset = np.array([1000.0, -500.0])
    translated = square + offset
    assert _polygon_area(translated) == pytest.approx(_polygon_area(square))


# --- _polygon_area: dtype independence and return type ---

@pytest.mark.parametrize("dtype", [np.int32, np.int64, np.float32, np.float64])
def test_polygon_area_accepts_various_dtypes(dtype):
    """Result is correct regardless of the input dtype."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=dtype)
    assert _polygon_area(square) == pytest.approx(100.0)


def test_polygon_area_returns_python_float():
    """Return type is a Python float, not a numpy scalar."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    assert isinstance(_polygon_area(square), float)


# --- _polygon_area: large values ---

def test_polygon_area_with_large_coordinates():
    """Large coordinates do not overflow."""
    square = np.array(
        [[0, 0], [10000, 0], [10000, 10000], [0, 10000]], dtype=np.float64
    )
    assert _polygon_area(square) == pytest.approx(1e8)

# --- _side_lengths: exact values for known shapes ---

def test_side_lengths_of_unit_square():
    """All sides of a 1x1 square have length 1."""
    square = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float64)
    lengths = _side_lengths(square)
    assert lengths == pytest.approx([1.0, 1.0, 1.0, 1.0])


def test_side_lengths_of_square():
    """All sides of a 10x10 square have length 10."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    lengths = _side_lengths(square)
    assert lengths == pytest.approx([10.0, 10.0, 10.0, 10.0])


def test_side_lengths_of_rectangle():
    """A 20x5 rectangle has sides [20, 5, 20, 5] in order."""
    rect = np.array([[0, 0], [20, 0], [20, 5], [0, 5]], dtype=np.float64)
    lengths = _side_lengths(rect)
    assert lengths == pytest.approx([20.0, 5.0, 20.0, 5.0])


def test_side_lengths_of_rhombus():
    """A rhombus with diagonals 6 and 8 has all sides of length 5."""
    # Diagonals along axes, centered at origin
    rhombus = np.array([[3, 0], [0, 4], [-3, 0], [0, -4]], dtype=np.float64)
    lengths = _side_lengths(rhombus)
    assert lengths == pytest.approx([5.0, 5.0, 5.0, 5.0])


# --- _side_lengths: order matches vertex order ---

def test_side_lengths_are_in_vertex_order():
    """Each position corresponds to the side starting at that vertex."""
    # Irregular quadrilateral with distinct side lengths
    quad = np.array([[0, 0], [3, 0], [5, 4], [0, 5]], dtype=np.float64)
    lengths = _side_lengths(quad)
    expected = [
        np.linalg.norm(np.array([3, 0]) - np.array([0, 0])),  # P0->P1 = 3
        np.linalg.norm(np.array([5, 4]) - np.array([3, 0])),  # P1->P2 = sqrt(4+16)=sqrt(20)
        np.linalg.norm(np.array([0, 5]) - np.array([5, 4])),  # P2->P3 = sqrt(25+1)=sqrt(26)
        np.linalg.norm(np.array([0, 0]) - np.array([0, 5])),  # P3->P0 = 5
    ]
    assert lengths == pytest.approx(expected)


# --- _side_lengths: degenerate cases ---

def test_side_lengths_with_coincident_consecutive_vertices():
    """A zero-length side is reported as 0."""
    quad = np.array([[0, 0], [0, 0], [10, 0], [10, 10]], dtype=np.float64)
    lengths = _side_lengths(quad)
    # P0->P1 is 0, P1->P2 is 10, P2->P3 is 10, P3->P0 is sqrt(200)
    assert lengths[0] == 0.0
    assert lengths[1] == pytest.approx(10.0)


def test_side_lengths_with_all_vertices_equal():
    """All sides are zero when all vertices coincide."""
    quad = np.array([[5, 5], [5, 5], [5, 5], [5, 5]], dtype=np.float64)
    lengths = _side_lengths(quad)
    assert lengths == pytest.approx([0.0, 0.0, 0.0, 0.0])


# --- _side_lengths: shape and dtype of the result ---

def test_side_lengths_returns_array_of_shape_4():
    """Result is a 1-D array with exactly four elements."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    lengths = _side_lengths(square)
    assert isinstance(lengths, np.ndarray)
    assert lengths.shape == (4,)


def test_side_lengths_returns_floating_dtype():
    """Result dtype is floating-point, not integer."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.int32)
    lengths = _side_lengths(square)
    assert np.issubdtype(lengths.dtype, np.floating)


# --- _side_lengths: geometric invariants ---

def test_side_lengths_are_translation_invariant():
    """Translating all vertices does not change side lengths."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    offset = np.array([1000.0, -500.0])
    assert _side_lengths(square + offset) == pytest.approx(_side_lengths(square))


def test_side_lengths_are_rotation_invariant():
    """Rotating all vertices around the origin preserves side lengths."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    # Rotate 90 degrees: (x, y) -> (-y, x)
    rotated = np.array([[-y, x] for x, y in square], dtype=np.float64)
    assert _side_lengths(rotated) == pytest.approx(_side_lengths(square))


# --- _side_lengths: dtype independence ---

@pytest.mark.parametrize("dtype", [np.int32, np.int64, np.float32, np.float64])
def test_side_lengths_accepts_various_dtypes(dtype):
    """Same lengths regardless of input dtype (within tolerance)."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=dtype)
    lengths = _side_lengths(square)
    assert lengths == pytest.approx([10.0, 10.0, 10.0, 10.0])

# --- _aspect_ratio: exact ratios for known shapes ---

def test_aspect_ratio_of_square_is_one():
    """A square has aspect ratio exactly 1."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    assert _aspect_ratio(square) == pytest.approx(1.0)


def test_aspect_ratio_of_2_to_1_rectangle():
    """A 2:1 rectangle has aspect ratio 2."""
    rect = np.array([[0, 0], [20, 0], [20, 10], [0, 10]], dtype=np.float64)
    assert _aspect_ratio(rect) == pytest.approx(2.0)


def test_aspect_ratio_of_1_to_10_rectangle():
    """A tall, thin rectangle has aspect ratio 10 (orientation does not matter)."""
    rect = np.array([[0, 0], [10, 0], [10, 100], [0, 100]], dtype=np.float64)
    assert _aspect_ratio(rect) == pytest.approx(10.0)


def test_aspect_ratio_is_symmetric_under_transpose():
    """Swapping width and height does not change the ratio."""
    wide = np.array([[0, 0], [100, 0], [100, 10], [0, 10]], dtype=np.float64)
    tall = np.array([[0, 0], [10, 0], [10, 100], [0, 100]], dtype=np.float64)
    assert _aspect_ratio(wide) == pytest.approx(_aspect_ratio(tall))


# --- _aspect_ratio: order independence ---

@pytest.mark.parametrize("start_index", [0, 1, 2, 3])
def test_aspect_ratio_is_independent_of_starting_vertex(start_index):
    """Rotating which vertex comes first does not change the ratio."""
    rect = np.array([[0, 0], [20, 0], [20, 10], [0, 10]], dtype=np.float64)
    rolled = np.roll(rect, -start_index, axis=0)
    assert _aspect_ratio(rolled) == pytest.approx(2.0)


# --- _aspect_ratio: zero-length side ---

def test_aspect_ratio_is_infinite_when_two_vertices_coincide():
    """A zero-length side makes the ratio infinite."""
    quad = np.array([[0, 0], [0, 0], [10, 0], [10, 10]], dtype=np.float64)
    assert _aspect_ratio(quad) == float("inf")


def test_aspect_ratio_is_infinite_when_all_vertices_coincide():
    """All sides zero -> infinite ratio."""
    quad = np.array([[5, 5], [5, 5], [5, 5], [5, 5]], dtype=np.float64)
    assert _aspect_ratio(quad) == float("inf")


def test_aspect_ratio_is_infinite_with_a_single_zero_side():
    """Even one zero-length side among positive ones triggers infinity."""
    quad = np.array([[0, 0], [10, 0], [10, 0], [0, 10]], dtype=np.float64)
    # Sides: P0->P1 = 10, P1->P2 = 0, P2->P3 = sqrt(200), P3->P0 = 10
    assert _aspect_ratio(quad) == float("inf")


# --- _aspect_ratio: geometric invariants ---

def test_aspect_ratio_is_translation_invariant():
    """Translating all vertices does not change the ratio."""
    rect = np.array([[0, 0], [20, 0], [20, 10], [0, 10]], dtype=np.float64)
    offset = np.array([1000.0, -500.0])
    assert _aspect_ratio(rect + offset) == pytest.approx(_aspect_ratio(rect))


def test_aspect_ratio_is_rotation_invariant():
    """Rotating all vertices preserves the ratio."""
    rect = np.array([[0, 0], [20, 0], [20, 10], [0, 10]], dtype=np.float64)
    rotated = np.array([[-y, x] for x, y in rect], dtype=np.float64)
    assert _aspect_ratio(rotated) == pytest.approx(_aspect_ratio(rect))


# --- _aspect_ratio: return type ---

def test_aspect_ratio_returns_python_float():
    """Return type is a Python float, not a numpy scalar."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    assert isinstance(_aspect_ratio(square), float)


def test_aspect_ratio_infinity_is_python_float():
    """The infinite case also returns a Python float."""
    quad = np.array([[0, 0], [0, 0], [10, 0], [10, 10]], dtype=np.float64)
    result = _aspect_ratio(quad)
    assert isinstance(result, float)
    assert result == float("inf")


# --- _aspect_ratio: dtype independence ---

@pytest.mark.parametrize("dtype", [np.int32, np.int64, np.float32, np.float64])
def test_aspect_ratio_accepts_various_dtypes(dtype):
    """Same ratio regardless of input dtype."""
    rect = np.array([[0, 0], [20, 0], [20, 10], [0, 10]], dtype=dtype)
    assert _aspect_ratio(rect) == pytest.approx(2.0)

# --- _min_side_length: shortest side ---

def test_min_side_length_of_square():
    """All sides equal: the minimum is any of them."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    assert _min_side_length(square) == pytest.approx(10.0)


def test_min_side_length_of_wide_rectangle():
    """Wide rectangle returns its shorter dimension."""
    rect = np.array([[0, 0], [20, 0], [20, 5], [0, 5]], dtype=np.float64)
    assert _min_side_length(rect) == pytest.approx(5.0)


def test_min_side_length_of_tall_rectangle():
    """Tall rectangle returns its shorter dimension too."""
    rect = np.array([[0, 0], [5, 0], [5, 20], [0, 20]], dtype=np.float64)
    assert _min_side_length(rect) == pytest.approx(5.0)


def test_min_side_length_is_independent_of_starting_vertex():
    """Rotation of vertex order does not change the minimum."""
    rect = np.array([[0, 0], [20, 0], [20, 5], [0, 5]], dtype=np.float64)
    rolled = np.roll(rect, -2, axis=0)
    assert _min_side_length(rolled) == pytest.approx(5.0)


# --- _min_side_length: zero-length sides ---

def test_min_side_length_is_zero_when_two_vertices_coincide():
    """A single zero-length side is the minimum."""
    quad = np.array([[0, 0], [0, 0], [10, 0], [10, 10]], dtype=np.float64)
    assert _min_side_length(quad) == 0.0


def test_min_side_length_is_zero_when_all_vertices_coincide():
    """All sides zero -> minimum 0."""
    quad = np.array([[5, 5], [5, 5], [5, 5], [5, 5]], dtype=np.float64)
    assert _min_side_length(quad) == 0.0


# --- _min_side_length: consistency with _side_lengths ---

def test_min_side_length_matches_min_of_side_lengths():
    """The value equals the minimum of _side_lengths."""
    quad = np.array([[0, 0], [3, 0], [5, 4], [0, 5]], dtype=np.float64)
    assert _min_side_length(quad) == pytest.approx(_side_lengths(quad).min())


# --- _min_side_length: return type ---

def test_min_side_length_returns_python_float():
    """Return type is a Python float, not a numpy scalar."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    assert isinstance(_min_side_length(square), float)

# --- _is_self_intersecting: simple quadrilaterals ---

def test_simple_square_is_not_self_intersecting():
    """A convex square in any winding order is not self-intersecting."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    assert _is_self_intersecting(square) is False


def test_clockwise_square_is_not_self_intersecting():
    """Reversing the vertex order still gives a simple quadrilateral."""
    square = np.array([[0, 10], [10, 10], [10, 0], [0, 0]], dtype=np.float64)
    assert _is_self_intersecting(square) is False


@pytest.mark.parametrize("start_index", [0, 1, 2, 3])
def test_square_is_not_self_intersecting_from_any_starting_vertex(start_index):
    """Cyclic rotation of vertices does not create self-intersection."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    rolled = np.roll(square, -start_index, axis=0)
    assert _is_self_intersecting(rolled) is False


def test_irregular_convex_quadrilateral_is_not_self_intersecting():
    """An arbitrary convex quadrilateral is simple."""
    quad = np.array([[0, 0], [15, 3], [12, 12], [2, 8]], dtype=np.float64)
    assert _is_self_intersecting(quad) is False


def test_concave_quadrilateral_is_not_self_intersecting():
    """A concave quadrilateral has a reflex angle but no crossing sides."""
    # P3 is 'inside' the triangle P0-P1-P2, making the shape concave.
    concave = np.array([[0, 0], [10, 0], [10, 10], [5, 5]], dtype=np.float64)
    assert _is_self_intersecting(concave) is False


# --- _is_self_intersecting: bowties ---

def test_bowtie_crossing_p0p1_and_p2p3_is_detected():
    """Opposite sides P0P1 and P2P3 crossing -> self-intersecting."""
    bowtie = np.array([[0, 0], [10, 10], [10, 0], [0, 10]], dtype=np.float64)
    assert _is_self_intersecting(bowtie) is True


def test_bowtie_crossing_p1p2_and_p3p0_is_detected():
    """Opposite sides P1P2 and P3P0 crossing -> self-intersecting."""
    bowtie = np.array([[0, 0], [10, 0], [0, 10], [10, 10]], dtype=np.float64)
    assert _is_self_intersecting(bowtie) is True


@pytest.mark.parametrize("start_index", [0, 1, 2, 3])
def test_bowtie_is_detected_from_any_starting_vertex(start_index):
    """Cyclic rotation of a bowtie does not hide the crossing."""
    bowtie = np.array([[0, 0], [10, 10], [10, 0], [0, 10]], dtype=np.float64)
    rolled = np.roll(bowtie, -start_index, axis=0)
    assert _is_self_intersecting(rolled) is True


# --- _is_self_intersecting: degenerate cases ---

def test_collapsed_quadrilateral_is_not_self_intersecting():
    """All vertices coincident: no segment has length, nothing crosses."""
    collapsed = np.array([[5, 5], [5, 5], [5, 5], [5, 5]], dtype=np.float64)
    assert _is_self_intersecting(collapsed) is False


def test_quadrilateral_with_two_consecutive_coincident_vertices_is_simple():
    """A zero-length side does not create a crossing."""
    quad = np.array([[0, 0], [0, 0], [10, 0], [10, 10]], dtype=np.float64)
    assert _is_self_intersecting(quad) is False


# --- _is_self_intersecting: return type ---

def test_is_self_intersecting_returns_python_bool():
    """Return type is a Python bool, not a numpy bool."""
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
    assert isinstance(_is_self_intersecting(square), bool)

# --- validate_quadrilateral: happy path ---

def test_validate_square_returns_empty_tuple():
    """A large, simple square passes validation with no issues."""
    square = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.float64)
    assert validate_quadrilateral(square) == ()


def test_validate_rectangle_returns_empty_tuple():
    """A rectangle well within all thresholds has no issues."""
    rect = np.array([[0, 0], [150, 0], [150, 100], [0, 100]], dtype=np.float64)
    assert validate_quadrilateral(rect) == ()


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


def test_area_exactly_at_threshold_does_not_raise():
    """Area == MIN_AREA_PX2 is not degenerate (strict <)."""
    # Unit square: area = 1.0 exactly
    unit = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float64)
    # Does not raise; may return issues (tiny side) but that's fine
    validate_quadrilateral(unit)  # should not raise


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

# --- warp_to_rectangle: validation of corners ---

def test_warp_rejects_non_array_with_type_error():
    """Non-ndarray corners are rejected with TypeError."""
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    with pytest.raises(TypeError):
        warp_to_rectangle(image, [[0, 0], [99, 0], [99, 99], [0, 99]], 50, 50)


def test_warp_rejects_wrong_shape_with_value_error():
    """Corners with wrong shape are rejected with ValueError."""
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    bad_corners = np.array([[0, 0], [99, 0], [99, 99]], dtype=np.float32)
    with pytest.raises(ValueError):
        warp_to_rectangle(image, bad_corners, 50, 50)


# --- warp_to_rectangle: validation of destination dimensions ---

@pytest.mark.parametrize("width, height", [
    (1, 50),
    (50, 1),
    (0, 50),
    (50, 0),
    (-1, 50),
    (50, -1),
])
def test_warp_rejects_dimensions_below_two(width, height):
    """Destination dimensions must be at least 2 in each axis."""
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    corners = np.array([[0, 0], [99, 0], [99, 99], [0, 99]], dtype=np.float32)
    with pytest.raises(ValueError):
        warp_to_rectangle(image, corners, width, height)


def test_warp_accepts_minimal_2x2_destination():
    """The smallest valid destination (2x2) works."""
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    corners = np.array([[0, 0], [99, 0], [99, 99], [0, 99]], dtype=np.float32)
    result = warp_to_rectangle(image, corners, 2, 2)
    assert result.shape == (2, 2, 3)


# --- warp_to_rectangle: output shape and dtype ---

def test_warp_returns_correct_shape():
    """Output shape is (height_px, width_px, 3)."""
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    corners = np.array([[0, 0], [99, 0], [99, 99], [0, 99]], dtype=np.float32)
    result = warp_to_rectangle(image, corners, 50, 30)
    assert result.shape == (30, 50, 3)


def test_warp_preserves_uint8_dtype():
    """uint8 input produces uint8 output."""
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    corners = np.array([[0, 0], [99, 0], [99, 99], [0, 99]], dtype=np.float32)
    result = warp_to_rectangle(image, corners, 50, 50)
    assert result.dtype == np.uint8


def test_warp_accepts_integer_corner_dtype():
    """Integer corner arrays are accepted (cast internally to float32)."""
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    corners = np.array([[0, 0], [99, 0], [99, 99], [0, 99]], dtype=np.int32)
    result = warp_to_rectangle(image, corners, 50, 50)
    assert result.shape == (50, 50, 3)


# --- warp_to_rectangle: functional behavior ---

def test_warp_of_uniform_image_is_uniform():
    """A solid-color image produces a solid-color output in the interior."""
    image = np.full((100, 100, 3), 200, dtype=np.uint8)
    corners = np.array([[0, 0], [99, 0], [99, 99], [0, 99]], dtype=np.float32)
    result = warp_to_rectangle(image, corners, 50, 50)
    # Ignore border pixels (Lanczos ringing), check interior
    interior = result[5:-5, 5:-5]
    assert np.allclose(interior, 200, atol=2)


def test_warp_with_identity_corners_preserves_interior_pattern():
    """Warping a shape onto a same-sized destination preserves its interior."""
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    image[25:75, 25:75] = 255
    corners = np.array([[0, 0], [99, 0], [99, 99], [0, 99]], dtype=np.float32)
    result = warp_to_rectangle(image, corners, 100, 100)
    # Central region stays white
    assert (result[40:60, 40:60] > 240).all()
    # Far corners stay black
    assert (result[:10, :10] < 15).all()
    assert (result[-10:, -10:] < 15).all()


def test_warp_maps_source_corners_to_destination_corners():
    """Markers at the four source corners land at the four destination corners."""
    image = np.zeros((200, 200, 3), dtype=np.uint8)
    # Place 11x11 white markers centered on the four corners of the source quad
    marker_half = 5
    source_corners = [(20, 20), (179, 20), (179, 179), (20, 179)]
    for cx, cy in source_corners:
        image[cy - marker_half:cy + marker_half + 1,
              cx - marker_half:cx + marker_half + 1] = 255

    corners = np.array(source_corners, dtype=np.float32)
    result = warp_to_rectangle(image, corners, 100, 100)

    # Each corner region of the output should contain the bright marker
    assert result[:15, :15].max() > 200       # top-left
    assert result[:15, -15:].max() > 200      # top-right
    assert result[-15:, :15].max() > 200      # bottom-left
    assert result[-15:, -15:].max() > 200     # bottom-right