"""Pure geometric operations for perspective correction.

No UI, no file I/O, no knowledge of the business domain (card sizes,
sheet sizes). It only knows about points, images, and the mathematics
of perspective transformations.
"""

from enum import Enum

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Validation thresholds (provisional, to be adjusted visually on PC)
# ---------------------------------------------------------------------------

MIN_AREA_PX2 = 1.0
MIN_SIDE_PX = 10
MAX_ASPECT_RATIO = 20.0


# ---------------------------------------------------------------------------
# Errors and issues
# ---------------------------------------------------------------------------

class DegenerateQuadrilateralError(ValueError):
    """The quadrilateral has near-zero area and cannot be warped.

    Raised by `validate_quadrilateral` when the area is so small that
    the perspective transformation would fail or produce undefined values.
    """


class Issue(str, Enum):
    """Possible non-fatal issues detected during quadrilateral validation."""
    SELF_INTERSECTING = "self_intersecting"
    EXTREME_ASPECT_RATIO = "extreme_aspect_ratio"
    TINY_SIDE = "tiny_side"


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _check_corners_shape(corners: np.ndarray) -> None:
    """Validate that `corners` is a numpy array with shape (4, 2).

    Raises:
        TypeError: if `corners` is not a numpy array.
        ValueError: if its shape is not (4, 2).
    """
    if not isinstance(corners, np.ndarray):
        raise TypeError(
            f"corners must be a numpy array, got {type(corners).__name__}"
        )
    if corners.shape != (4, 2):
        raise ValueError(
            f"corners must have shape (4, 2), got {corners.shape}"
        )


def _cross_product_2d(
    p1: np.ndarray,
    p2: np.ndarray,
    p3: np.ndarray,
) -> float:
    """Return the 2D cross product of vectors (p2 - p1) and (p3 - p1).

    The sign of the result indicates which side of the line p1->p2 the
    point p3 lies on:
      - Positive: p3 is to the left.
      - Negative: p3 is to the right.
      - Zero: p3 is collinear with p1 and p2.
    """
    return float(
        (p2[0] - p1[0]) * (p3[1] - p1[1])
        - (p2[1] - p1[1]) * (p3[0] - p1[0])
    )


def _segments_intersect(
    p1: np.ndarray,
    p2: np.ndarray,
    p3: np.ndarray,
    p4: np.ndarray,
) -> bool:
    """Return True if segment p1-p2 intersects segment p3-p4.

    Collinear cases are not handled: they are assumed to be caught by
    other validation rules (e.g. near-zero area).
    """
    d1 = _cross_product_2d(p3, p4, p1)
    d2 = _cross_product_2d(p3, p4, p2)
    d3 = _cross_product_2d(p1, p2, p3)
    d4 = _cross_product_2d(p1, p2, p4)
    return (d1 * d2 < 0) and (d3 * d4 < 0)


def _polygon_area(corners: np.ndarray) -> float:
    """Return the (unsigned) area of the quadrilateral in square pixels.

    Uses the shoelace formula. The signed result is converted to absolute
    value, so the order of the points (clockwise or counter-clockwise)
    does not matter.
    """
    xs = corners[:, 0]
    ys = corners[:, 1]
    xs_next = np.roll(xs, -1)
    ys_next = np.roll(ys, -1)
    cross = xs * ys_next - xs_next * ys
    return float(0.5 * abs(cross.sum()))


def _side_lengths(corners: np.ndarray) -> np.ndarray:
    """Return the lengths of the four sides of the quadrilateral.

    Sides are returned in order: P0->P1, P1->P2, P2->P3, P3->P0.
    """
    points_next = np.roll(corners, -1, axis=0)
    diffs = points_next - corners
    return np.sqrt((diffs ** 2).sum(axis=1))


def _aspect_ratio(corners: np.ndarray) -> float:
    """Return the ratio between the longest and shortest sides.

    If any side has length zero (two clicks on the same pixel), returns
    float('inf') to indicate an infinitely stretched quadrilateral.
    """
    lengths = _side_lengths(corners)
    shortest = float(lengths.min())
    if shortest == 0.0:
        return float("inf")
    return float(lengths.max() / shortest)


def _min_side_length(corners: np.ndarray) -> float:
    """Return the length of the shortest side, in pixels."""
    return float(_side_lengths(corners).min())


def _is_self_intersecting(corners: np.ndarray) -> bool:
    """Return True if the quadrilateral's opposite sides cross each other.

    A self-intersecting quadrilateral indicates the points were marked
    in the wrong order.
    """
    p0, p1, p2, p3 = corners
    return (
        _segments_intersect(p0, p1, p2, p3)
        or _segments_intersect(p1, p2, p3, p0)
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_quadrilateral(corners: np.ndarray) -> tuple[Issue, ...]:
    """Validate a quadrilateral before warping.

    Self-intersection is checked first and returned immediately, because
    the shoelace formula is misleading for self-intersecting polygons.

    Args:
        corners: Array of shape (4, 2) with the four corner points.

    Returns:
        A tuple of `Issue` members found. An empty tuple means the
        quadrilateral is fine.

    Raises:
        TypeError: if `corners` is not a numpy array.
        ValueError: if `corners` does not have shape (4, 2).
        DegenerateQuadrilateralError: if the area is near zero and the
            perspective transformation would fail. Not raised for
            self-intersecting quadrilaterals, which are reported as an
            issue instead.
    """
    _check_corners_shape(corners)

    # Self-intersection is checked before area: the shoelace formula
    # assumes a simple polygon and returns misleading values for
    # self-intersecting ones. A symmetric bowtie, for example, yields
    # area 0 even though its lobes cover real surface.
    if _is_self_intersecting(corners):
        return (Issue.SELF_INTERSECTING,)

    area = _polygon_area(corners)
    if area < MIN_AREA_PX2:
        raise DegenerateQuadrilateralError(
            f"Quadrilateral area ({area:.2f} px²) is below the minimum "
            f"of {MIN_AREA_PX2} px²; warping would fail."
        )

    issues: list[Issue] = []
    if _aspect_ratio(corners) > MAX_ASPECT_RATIO:
        issues.append(Issue.EXTREME_ASPECT_RATIO)
    if _min_side_length(corners) < MIN_SIDE_PX:
        issues.append(Issue.TINY_SIDE)

    return tuple(issues)


def warp_to_rectangle(
    image: np.ndarray,
    corners: np.ndarray,
    width_px: int,
    height_px: int,
) -> np.ndarray:
    """Apply a perspective transformation to straighten the quadrilateral.

    Args:
        image: Source image as a BGR numpy array.
        corners: Four points in `image` in order TL, TR, BR, BL.
        width_px: Width of the destination rectangle, in pixels.
        height_px: Height of the destination rectangle, in pixels.

    Returns:
        The straightened image, of shape (height_px, width_px, 3).

    Raises:
        TypeError: if `corners` is not a numpy array.
        ValueError: if `corners` does not have shape (4, 2), or if
            `width_px` or `height_px` is less than 2.
    """
    _check_corners_shape(corners)

    if width_px < 2 or height_px < 2:
        raise ValueError(
            f"width_px and height_px must be at least 2, "
            f"got {width_px}x{height_px}"
        )

    destination = np.array([
        [0, 0],
        [width_px - 1, 0],
        [width_px - 1, height_px - 1],
        [0, height_px - 1],
    ], dtype=np.float32)

    corners_f32 = np.asarray(corners, dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(corners_f32, destination)

    # INTER_LANCZOS4 for high-quality resampling: the perspective
    # transformation resamples pixels, and Lanczos produces sharper
    # results than the default INTER_LINEAR at the cost of being
    # slightly slower. This is an implementation detail, not part of
    # the function's contract.
    result = cv2.warpPerspective(
        image,
        matrix,
        (width_px, height_px),
        flags=cv2.INTER_LANCZOS4,
    )

    return result