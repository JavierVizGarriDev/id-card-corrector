import numpy as np
import pytest
from id_card_corrector.geometry import (
    warp_to_rectangle,
    DegenerateQuadrilateralError,
)


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


def test_warp_does_not_mutate_inputs():
    """warp_to_rectangle must be a pure function (no side effects).
    
    It should not modify the original image or the corners array,
    regardless of the dtype of the corners (which might trigger
    a view instead of a copy internally).
    
    Note: We use a deterministic random image (seeded) instead of an
    array of zeros. With zeros, mutations like image[:] = 0 would be
    invisible and the test would pass vacuously.
    """
    rng = np.random.default_rng(seed=42)
    image = rng.integers(0, 256, size=(100, 100, 3), dtype=np.uint8)
    
    corners = np.array([[0, 0], [99, 0], [99, 99], [0, 99]], dtype=np.float32)
    
    # Guardamos copias del estado original
    original_image = image.copy()
    original_corners = corners.copy()
    
    warp_to_rectangle(image, corners, 50, 50)
    
    # Verificamos que los originales no han cambiado
    np.testing.assert_array_equal(image, original_image)
    np.testing.assert_array_equal(corners, original_corners)


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

@pytest.mark.parametrize("corners, description", [
    pytest.param(
        np.array([[10, 50], [30, 50], [50, 50], [70, 50]], dtype=np.float32),
        "colineal (área ~0)",
        id="colinear",
    ),
    pytest.param(
        np.array([[10, 10], [90, 90], [90, 10], [10, 90]], dtype=np.float32),
        "bowtie (auto-intersección)",
        id="bowtie",
    ),
])
def test_warp_does_not_raise_degenerate_error(corners, description):
    """Atomic contract: warp_to_rectangle never raises DegenerateQuadrilateralError.

    Whether OpenCV throws is a separate concern (see
    test_warp_handles_bowtie_without_opencv_error).
    """
    image = np.zeros((100, 100, 3), dtype=np.uint8)

    try:
        warp_to_rectangle(image, corners, 50, 50)
    except DegenerateQuadrilateralError:
        pytest.fail(
            f"warp_to_rectangle should not validate geometry ({description}); "
            "that is validate_quadrilateral's responsibility."
        )
    except Exception:
        pass  # Different contract — not this test's concern.


def test_warp_is_deterministic():
    """warp_to_rectangle must be deterministic.
    
    Given the same image and corners, two consecutive calls must
    produce exactly the same output. This protects against hidden
    state, caches, or accidental non-determinism (e.g., threading issues).
    """
    rng = np.random.default_rng(seed=123)
    image = rng.integers(0, 256, size=(100, 100, 3), dtype=np.uint8)
    corners = np.array([[10, 10], [90, 10], [90, 90], [10, 90]], dtype=np.float32)
    
    result1 = warp_to_rectangle(image, corners, 50, 50)
    result2 = warp_to_rectangle(image, corners, 50, 50)
    
    np.testing.assert_array_equal(result1, result2)


def test_warp_handles_bowtie_without_opencv_error():
    """Separate contract: OpenCV accepts well-defined degenerate geometry (bowtie).

    The colinear case is intentionally excluded: OpenCV's behavior on a
    singular matrix is undefined and not part of warp_to_rectangle's contract.
    """
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    bowtie = np.array([[10, 10], [90, 90], [90, 10], [10, 90]], dtype=np.float32)

    result = warp_to_rectangle(image, bowtie, 50, 50)
    assert result.shape == (50, 50, 3)


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
    """Markers at the four source corners land at the four destination corners.

    Uses distinct colors for each corner to detect permutation bugs
    (e.g., TL mapped to TR). A single white marker would hide such bugs
    because all corners would look the same.

    Note: We use a large marker (31x31) so that, after downscaling to
    the 100x100 destination, the marker region is large enough to avoid
    Lanczos interpolation bleeding from the black background.
    """
    image = np.zeros((200, 200, 3), dtype=np.uint8)
    marker_half = 15  # 31x31 markers for robust sampling after warp
    source_corners = [(20, 20), (179, 20), (179, 179), (20, 179)]
    colors = [
        (255, 0, 0),    # TL: Azul (BGR)
        (0, 255, 0),    # TR: Verde
        (0, 0, 255),    # BR: Rojo
        (255, 255, 0),  # BL: Cian (azul + verde)
    ]
    for (cx, cy), color in zip(source_corners, colors):
        image[cy - marker_half:cy + marker_half + 1,
              cx - marker_half:cx + marker_half + 1] = color

    corners = np.array(source_corners, dtype=np.float32)
    result = warp_to_rectangle(image, corners, 100, 100)

    # Verificamos una región de 5x5 desde la esquina.
    # Como el marcador en destino mide ~10x10, esta región es interior y segura.
    tl_region = result[0:5, 0:5]
    assert tl_region[:, :, 0].max() > 200  # B
    assert tl_region[:, :, 1].max() < 50   # G
    assert tl_region[:, :, 2].max() < 50   # R

    tr_region = result[0:5, -5:]
    assert tr_region[:, :, 1].max() > 200  # G
    assert tr_region[:, :, 0].max() < 50   # B
    assert tr_region[:, :, 2].max() < 50   # R

    br_region = result[-5:, -5:]
    assert br_region[:, :, 2].max() > 200  # R
    assert br_region[:, :, 0].max() < 50   # B
    assert br_region[:, :, 1].max() < 50   # G

    bl_region = result[-5:, 0:5]
    assert bl_region[:, :, 0].max() > 200  # B
    assert bl_region[:, :, 1].max() > 200  # G
    assert bl_region[:, :, 2].max() < 50   # R