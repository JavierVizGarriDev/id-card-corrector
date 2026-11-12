import numpy as np
import pytest
from id_card_corrector.geometry import (
    _segments_intersect,
    _is_self_intersecting,
)


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

@pytest.mark.parametrize("p1, p2, p3, p4, description", [
    pytest.param(
        (0, 0), (5, 5), (10, 3), (15, 6), 
        "non-parallel disjoint", 
        id="non-parallel"
    ),
    pytest.param(
        (0, 0), (10, 0), (0, 5), (10, 5), 
        "parallel, aligned x", 
        id="parallel-aligned"
    ),
    pytest.param(
        (0, 0), (10, 0), (100, 100), (110, 100), 
        "parallel, far apart", 
        id="parallel-far"
    ),
    pytest.param(
        (0, 0), (10, 0), (5, 1), (5, 11), 
        "one line crosses, segments don't", 
        id="near-miss"
    ),
])
def test_segments_do_not_intersect_when_disjoint(p1, p2, p3, p4, description):
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
