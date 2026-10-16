"""File I/O for images and PDFs.

This module is responsible for reading and writing files. It knows
nothing about geometry, layout, or business rules. Images are handled
in BGR order (OpenCV convention) at the API boundary, and converted
to RGB internally when Pillow is used for saving.
"""

from pathlib import Path
from typing import Final
import math

import cv2
import numpy as np
from PIL import Image


# Supported image file extensions (lowercase, with dot).
SUPPORTED_EXTENSIONS: Final[frozenset[str]] = frozenset({".jpg", ".jpeg", ".png"})

# Accepted extension for PDF output.
PDF_EXTENSIONS: Final[frozenset[str]] = frozenset({".pdf"})


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _to_rgb(image: np.ndarray) -> np.ndarray:
    """Convert a 3-channel uint8 BGR image to RGB (Pillow convention).

    OpenCV loads images in BGR order; Pillow expects RGB. If you skip
    this conversion, reds and blues will be swapped when saving.

    Args:
        image: BGR image of shape (H, W, 3) and dtype uint8.

    Returns:
        RGB image of shape (H, W, 3) and dtype uint8.

    Raises:
        ValueError: if `image` does not have shape (H, W, 3) or dtype
            uint8. Pillow's `fromarray` produces cryptic errors for
            other dtypes, so we validate here.
    """
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(
            f"Expected a 3-channel image (H, W, 3), got shape {image.shape}"
        )
    if image.dtype != np.uint8:
        raise ValueError(
            f"Expected dtype uint8, got {image.dtype}"
        )
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def _check_dpi(dpi: int | float) -> None:
    """Validate that `dpi` is a finite positive number.

    Args:
        dpi: Resolution value to check. Both int and float are
            accepted; float DPI is useful when computing resolution
            from pixel dimensions and desired page size.

    Raises:
        TypeError: if `dpi` is not a number (str, None, list, etc.).
            bool is rejected even though it is a subclass of int.
        ValueError: if `dpi` is not finite (inf, -inf, nan), or if it
            is not positive.
    """
    if isinstance(dpi, bool) or not isinstance(dpi, (int, float)):
        raise TypeError(
            f"dpi must be a number, got {type(dpi).__name__}: {dpi!r}"
        )
    if isinstance(dpi, float) and not math.isfinite(dpi):
        raise ValueError(f"dpi must be finite, got {dpi}")
    if dpi <= 0:
        raise ValueError(f"dpi must be positive, got {dpi}")


def _check_extension(path: Path, allowed: frozenset[str]) -> None:
    """Validate that the path's extension is in `allowed`.

    The comparison is case-insensitive.

    Args:
        path: Path whose extension will be checked.
        allowed: Set of accepted extensions (lowercase, with dot).

    Raises:
        ValueError: if the extension is not in `allowed`.
    """
    ext = path.suffix.lower()
    if ext not in allowed:
        raise ValueError(
            f"Unsupported extension: {ext!r}. "
            f"Supported: {sorted(allowed)}"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ensure_directory(path: Path) -> None:
    """Create the directory at `path` if it does not exist.

    Parent directories are created as needed. Does nothing if the
    directory already exists.

    Args:
        path: Directory path to ensure.

    Raises:
        FileExistsError: if `path` exists but is not a directory.
    """
    path.mkdir(parents=True, exist_ok=True)


def list_image_files(directory: Path) -> list[Path]:
    """Return a sorted list of image files in `directory`.

    Only regular files with extensions in SUPPORTED_EXTENSIONS
    (case-insensitive) are included. Subdirectories and other
    non-file entries are excluded, even if their name happens to
    end with a supported extension. The list is sorted alphabetically
    by filename, providing a deterministic order for the pipeline
    (first = front, second = back).

    Args:
        directory: Directory to scan.

    Returns:
        A list of Path objects, sorted by filename.

    Raises:
        FileNotFoundError: if `directory` does not exist.
        NotADirectoryError: if `directory` is not a directory.
    """
    return sorted(
        (
            p
            for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=lambda p: p.name,
    )


def load_image(path: Path) -> np.ndarray:
    """Load an image from disk as a BGR numpy array.

    The file extension is not validated. Any format that OpenCV can
    read is accepted. Use `list_image_files` if you need to filter
    by extension.

    Args:
        path: Path to the image file.

    Returns:
        The image as a numpy array of shape (H, W, 3), dtype uint8.

    Raises:
        FileNotFoundError: if `path` does not exist.
        ValueError: if the file exists but cannot be read as an image
            (corrupt file, unsupported format by OpenCV, etc.).
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(
            f"Could not read image from {path}. "
            f"The file may be corrupt, or its format may not be "
            f"supported by OpenCV."
        )
    return image


def save_image(path: Path, image: np.ndarray, dpi: int | float) -> None:
    """Save an image (BGR) to disk as JPG or PNG, embedding the DPI.

    Args:
        path: Destination file path. The extension (case-insensitive)
            must be one of SUPPORTED_EXTENSIONS.
        image: BGR image of shape (H, W, 3) and dtype uint8 to save.
        dpi: Resolution to embed in the file metadata. Must be a
            positive number.

    Raises:
        TypeError: if `dpi` is not a number.
        ValueError: if the file extension is not supported, if `dpi`
            is not positive, or if `image` is not a 3-channel uint8
            array.

    Note:
        Arguments are validated in this order: dpi, extension, image.
        If multiple arguments are invalid, the first invalid one in
        that order is the one reported. All validations happen before
        any filesystem side effect.

        Uses Pillow instead of cv2.imwrite because Pillow reliably
        embeds the DPI metadata, which OpenCV does not.
    """
    _check_dpi(dpi)
    _check_extension(path, SUPPORTED_EXTENSIONS)
    rgb = _to_rgb(image)
    ensure_directory(path.parent)
    Image.fromarray(rgb).save(path, dpi=(dpi, dpi))


def save_pdf(path: Path, image: np.ndarray, dpi: int | float) -> None:
    """Save a single image as a one-page PDF, embedding the DPI.

    The physical page size is derived from the image dimensions and
    the DPI: width_px / dpi inches by height_px / dpi inches. For
    example, a 2550x3300 image at 300 DPI produces a page of exactly
    8.5" x 11" (US Letter).

    Args:
        path: Destination PDF file path. Must end in ".pdf"
            (case-insensitive).
        image: BGR image of shape (H, W, 3) and dtype uint8.
        dpi: Resolution to embed in the PDF metadata. Must be a
            positive number.

    Raises:
        TypeError: if `dpi` is not a number.
        ValueError: if the path does not end in ".pdf", if `dpi` is
            not positive, or if `image` is not a 3-channel uint8 array.

    Note:
        Arguments are validated in this order: dpi, extension, image.
        If multiple arguments are invalid, the first invalid one in
        that order is the one reported. All validations happen before
        any filesystem side effect.

        Pillow also accepts a `dpi` tuple since version 9.5.0. We use
        `resolution` because it is the historical parameter and takes
        a scalar, keeping it consistent with `save_image`.
    """
    _check_dpi(dpi)
    _check_extension(path, PDF_EXTENSIONS)
    rgb = _to_rgb(image)
    ensure_directory(path.parent)
    Image.fromarray(rgb).save(path, format="PDF", resolution=dpi)