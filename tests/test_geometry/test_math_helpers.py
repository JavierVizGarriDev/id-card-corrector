import numpy as np
import pytest
from id_card_corrector.geometry import (
    _cross_product_2d,
    _polygon_area,
    _side_lengths,
    _aspect_ratio,
    _min_side_length,
)


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


def test_cross_product_2d_is_antisymmetric():
    """Swapping p2 and p3 must negate the result.
    
    This is a fundamental property of the 2D cross product (determinant).
    It verifies the implementation against a universal mathematical law,
    not just hardcoded expected values.
    """
    p1 = np.array([10, 10])
    p2 = np.array([30, 15])
    p3 = np.array([20, 40])
    
    result_forward = _cross_product_2d(p1, p2, p3)
    result_swapped = _cross_product_2d(p1, p3, p2)
    
    assert result_forward == pytest.approx(-result_swapped)


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

# --- _polygon_area: misleading values for self-intersecting polygons ---

def test_polygon_area_of_symmetric_bowtie_is_zero():
    """A symmetric bowtie yields area 0 via shoelace formula.

    This is the mathematical premise for the short-circuit in
    validate_quadrilateral. If this ever changes, the short-circuit
    logic loses its justification and must be re-evaluated.
    """
    bowtie = np.array([[0, 0], [100, 100], [100, 0], [0, 100]], dtype=np.float64)
    assert _polygon_area(bowtie) == pytest.approx(0.0)

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

