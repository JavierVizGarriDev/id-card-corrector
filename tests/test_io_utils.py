"""Tests for the io_utils module."""

from pathlib import Path
import re

import pypdf
import numpy as np
import pytest
from PIL import Image

from id_card_corrector.io_utils import (
    PDF_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    _check_dpi,
    _check_extension,
    _to_rgb,
    ensure_directory,
    list_image_files,
    load_image,
    save_image,
    save_pdf,
)

# --- _to_rgb: channel conversion (the critical test) ---

def test_to_rgb_swaps_blue_and_red_channels():
    """BGR (255, 0, 0) becomes RGB (0, 0, 255), and vice versa."""
    bgr = np.zeros((1, 1, 3), dtype=np.uint8)
    bgr[0, 0] = [255, 0, 0]  # pure blue in BGR
    rgb = _to_rgb(bgr)
    assert rgb[0, 0].tolist() == [0, 0, 255]  # pure blue in RGB


def test_to_rgb_with_distinguishable_channels():
    """All three channels end up in the right position after conversion."""
    bgr = np.zeros((1, 1, 3), dtype=np.uint8)
    bgr[0, 0] = [10, 20, 30]  # B=10, G=20, R=30
    rgb = _to_rgb(bgr)
    assert rgb[0, 0].tolist() == [30, 20, 10]  # R=30, G=20, B=10


def test_to_rgb_leaves_green_channel_untouched():
    """Green does not move during BGR->RGB conversion."""
    bgr = np.zeros((1, 1, 3), dtype=np.uint8)
    bgr[0, 0] = [0, 255, 0]  # pure green in any convention
    rgb = _to_rgb(bgr)
    assert rgb[0, 0].tolist() == [0, 255, 0]


# --- _to_rgb: shape and dtype preservation ---

def test_to_rgb_preserves_shape_of_non_square_image():
    """Non-square images keep their shape through conversion."""
    bgr = np.zeros((100, 200, 3), dtype=np.uint8)
    rgb = _to_rgb(bgr)
    assert rgb.shape == (100, 200, 3)


def test_to_rgb_preserves_uint8_dtype():
    """The output dtype is uint8."""
    bgr = np.zeros((10, 10, 3), dtype=np.uint8)
    assert _to_rgb(bgr).dtype == np.uint8


def test_to_rgb_works_on_single_pixel_image():
    """A 1x1 image is a valid input."""
    bgr = np.array([[[10, 20, 30]]], dtype=np.uint8)
    rgb = _to_rgb(bgr)
    assert rgb.shape == (1, 1, 3)
    assert rgb[0, 0].tolist() == [30, 20, 10]


def test_to_rgb_does_not_mutate_input():
    """The input array is left untouched."""
    bgr = np.array([[[10, 20, 30]]], dtype=np.uint8)
    original = bgr.copy()
    _to_rgb(bgr)
    assert np.array_equal(bgr, original)


# --- _to_rgb: rejects invalid shapes ---

def test_to_rgb_rejects_2d_array_with_message():
    """A 2D array is rejected with a clear message (not IndexError)."""
    gray = np.zeros((100, 100), dtype=np.uint8)
    with pytest.raises(ValueError, match=r"3-channel image.*shape"):
        _to_rgb(gray)


@pytest.mark.parametrize("shape", [
    (10, 10, 4),     # RGBA
    (10, 10, 1),     # grayscale with trailing axis
    (10, 10, 3, 1),  # extra dimension
    (10,),           # 1D
    (),              # scalar
])
def test_to_rgb_rejects_invalid_shapes(shape):
    """Any shape other than (H, W, 3) is rejected."""
    image = np.zeros(shape, dtype=np.uint8)
    with pytest.raises(ValueError):
        _to_rgb(image)


# --- _to_rgb: rejects invalid dtypes ---

def test_to_rgb_rejects_wrong_dtype_with_message():
    """Non-uint8 input is rejected with a message naming the dtype."""
    image = np.zeros((10, 10, 3), dtype=np.float32)
    with pytest.raises(ValueError, match=r"uint8.*float32"):
        _to_rgb(image)


@pytest.mark.parametrize("dtype", [
    np.float32,
    np.float64,
    np.int32,
    np.int16,
    np.uint16,
])
def test_to_rgb_rejects_all_non_uint8_dtypes(dtype):
    """Every non-uint8 numeric dtype is rejected."""
    image = np.zeros((10, 10, 3), dtype=dtype)
    with pytest.raises(ValueError):
        _to_rgb(image)


# --- _to_rgb: order of validation ---

def test_to_rgb_reports_shape_error_before_dtype_error():
    """Shape is validated first; its error is reported when both are wrong."""
    bad = np.zeros((10, 10), dtype=np.float32)  # 2D and wrong dtype
    with pytest.raises(ValueError, match=r"3-channel image"):
        _to_rgb(bad)

# --- _check_dpi: valid inputs ---

@pytest.mark.parametrize("dpi", [1, 72, 300, 1200])
def test_check_dpi_accepts_positive_int(dpi):
    """Positive integers are accepted."""
    _check_dpi(dpi)  # should not raise


@pytest.mark.parametrize("dpi", [0.5, 72.0, 300.5, 0.1])
def test_check_dpi_accepts_positive_float(dpi):
    """Positive floats are accepted (documented as useful)."""
    _check_dpi(dpi)  # should not raise


def test_check_dpi_accepts_huge_int():
    """An integer too large for float is still a valid Python int."""
    # Without the isinstance(dpi, float) guard, math.isfinite would
    # raise OverflowError here.
    _check_dpi(10**400)  # should not raise


# --- _check_dpi: TypeError for non-numbers ---

@pytest.mark.parametrize("dpi", [True, False])
def test_check_dpi_rejects_bool(dpi):
    """bool is rejected even though it is a subclass of int."""
    with pytest.raises(TypeError, match="bool"):
        _check_dpi(dpi)


@pytest.mark.parametrize("dpi", ["300", None, [300], {"dpi": 300}, object()])
def test_check_dpi_rejects_non_number_types(dpi):
    """Non-numeric values are rejected with TypeError."""
    with pytest.raises(TypeError):
        _check_dpi(dpi)


# --- _check_dpi: ValueError for non-finite floats ---

@pytest.mark.parametrize("dpi", [
    float("inf"),
    float("-inf"),
    float("nan"),
])
def test_check_dpi_rejects_non_finite(dpi):
    """inf, -inf and nan are rejected with ValueError."""
    with pytest.raises(ValueError, match="must be finite"):
        _check_dpi(dpi)


def test_check_dpi_nan_reports_not_finite_not_not_positive():
    """nan must be caught by the finite check, not slip through."""
    # Without the finite guard, nan <= 0 is False, so nan would pass
    # silently and corrupt the DPI metadata.
    with pytest.raises(ValueError, match="must be finite"):
        _check_dpi(float("nan"))


# --- _check_dpi: ValueError for non-positive values ---

@pytest.mark.parametrize("dpi", [0, 0.0, -1, -300, -0.5])
def test_check_dpi_rejects_non_positive(dpi):
    """Zero and negative values are rejected with ValueError."""
    with pytest.raises(ValueError, match="must be positive"):
        _check_dpi(dpi)


# --- _check_dpi: return value ---

def test_check_dpi_returns_none():
    """The validator returns None on success (it is a check, not a transform)."""
    assert _check_dpi(300) is None


# --- _check_extension: valid extensions ---

@pytest.mark.parametrize("ext", [".jpg", ".jpeg", ".png"])
def test_check_extension_accepts_supported_extensions(ext):
    """All extensions in SUPPORTED_EXTENSIONS are accepted."""
    _check_extension(Path(f"file{ext}"), SUPPORTED_EXTENSIONS)


@pytest.mark.parametrize("ext", [".JPG", ".Jpeg", ".PNG"])
def test_check_extension_is_case_insensitive(ext):
    """Uppercase and mixed-case extensions are normalized and accepted."""
    _check_extension(Path(f"file{ext}"), SUPPORTED_EXTENSIONS)


def test_check_extension_accepts_pdf():
    """The PDF extension is accepted when PDF_EXTENSIONS is passed."""
    _check_extension(Path("output.pdf"), PDF_EXTENSIONS)


def test_check_extension_accepts_uppercase_pdf():
    """.PDF is accepted for PDF_EXTENSIONS (case-insensitive)."""
    _check_extension(Path("output.PDF"), PDF_EXTENSIONS)


def test_check_extension_uses_only_last_suffix():
    """Path.suffix returns only the last component: a.tar.jpg -> .jpg."""
    _check_extension(Path("archive.tar.jpg"), SUPPORTED_EXTENSIONS)


def test_check_extension_ignores_directories_in_path():
    """Directories before the filename are irrelevant to the check."""
    _check_extension(Path("some/dir/subdir/photo.png"), SUPPORTED_EXTENSIONS)


# --- _check_extension: rejected extensions ---

def test_check_extension_rejects_unsupported_extension_with_message():
    """An unsupported extension is rejected with a message naming it."""
    with pytest.raises(ValueError, match=r"Unsupported extension.*\.gif"):
        _check_extension(Path("file.gif"), SUPPORTED_EXTENSIONS)


def test_check_extension_rejects_pdf_when_image_extensions_expected():
    """.pdf is not in SUPPORTED_EXTENSIONS."""
    with pytest.raises(ValueError):
        _check_extension(Path("file.pdf"), SUPPORTED_EXTENSIONS)


def test_check_extension_rejects_image_extension_when_pdf_expected():
    """.png is not in PDF_EXTENSIONS."""
    with pytest.raises(ValueError):
        _check_extension(Path("file.png"), PDF_EXTENSIONS)


def test_check_extension_rejects_path_without_extension():
    """A path with no extension has suffix '' and is rejected."""
    with pytest.raises(ValueError, match=r"Unsupported extension: ''"):
        _check_extension(Path("README"), SUPPORTED_EXTENSIONS)


def test_check_extension_error_message_lists_supported_extensions():
    """The error message enumerates the supported extensions, sorted."""
    with pytest.raises(ValueError, match=r"\['\.jpeg', '\.jpg', '\.png'\]"):
        _check_extension(Path("file.gif"), SUPPORTED_EXTENSIONS)


# --- ensure_directory: creation ---

def test_ensure_directory_creates_new_directory(tmp_path):
    """A non-existent directory is created."""
    new_dir = tmp_path / "newdir"
    assert not new_dir.exists()
    ensure_directory(new_dir)
    assert new_dir.is_dir()


def test_ensure_directory_creates_parent_directories(tmp_path):
    """Missing intermediate directories are created (parents=True)."""
    nested = tmp_path / "a" / "b" / "c"
    assert not nested.exists()
    ensure_directory(nested)
    assert nested.is_dir()
    assert (tmp_path / "a").is_dir()
    assert (tmp_path / "a" / "b").is_dir()


# --- ensure_directory: idempotency ---

def test_ensure_directory_does_nothing_on_existing_directory(tmp_path):
    """An existing directory does not raise (exist_ok=True)."""
    existing = tmp_path / "existing"
    existing.mkdir()
    ensure_directory(existing)  # should not raise
    assert existing.is_dir()


def test_ensure_directory_is_safe_to_call_twice(tmp_path):
    """Calling twice in a row on a fresh path works (real usage pattern)."""
    target = tmp_path / "fresh"
    ensure_directory(target)
    ensure_directory(target)  # second call must not raise
    assert target.is_dir()


# --- ensure_directory: FileExistsError ---

def test_ensure_directory_raises_when_path_is_a_file(tmp_path):
    """A path that exists as a file raises FileExistsError, not silently passes."""
    file_path = tmp_path / "existing.txt"
    file_path.write_text("content")
    with pytest.raises(FileExistsError):
        ensure_directory(file_path)


# --- ensure_directory: return value ---

def test_ensure_directory_returns_none(tmp_path):
    """The function is a side-effect-only helper; it returns None."""
    assert ensure_directory(tmp_path / "anydir") is None


# --- list_image_files: basic listing ---

def test_list_image_files_returns_empty_for_empty_directory(tmp_path):
    """An empty directory returns an empty list."""
    assert list_image_files(tmp_path) == []


def test_list_image_files_returns_single_image(tmp_path):
    """A single image file is returned."""
    (tmp_path / "photo.jpg").write_bytes(b"")
    assert list_image_files(tmp_path) == [tmp_path / "photo.jpg"]


def test_list_image_files_returns_all_supported_extensions(tmp_path):
    """Files with .jpg, .jpeg, .png are all returned."""
    for name in ("a.jpg", "b.jpeg", "c.png"):
        (tmp_path / name).write_bytes(b"")
    assert len(list_image_files(tmp_path)) == 3


def test_list_image_files_returns_path_objects(tmp_path):
    """Every returned item is a Path instance."""
    (tmp_path / "photo.jpg").write_bytes(b"")
    result = list_image_files(tmp_path)
    assert all(isinstance(p, Path) for p in result)


# --- list_image_files: filtering ---

def test_list_image_files_excludes_non_image_files(tmp_path):
    """Files with unsupported extensions are excluded."""
    (tmp_path / "photo.jpg").write_bytes(b"")
    (tmp_path / "document.txt").write_bytes(b"")
    (tmp_path / "archive.zip").write_bytes(b"")
    assert list_image_files(tmp_path) == [tmp_path / "photo.jpg"]


def test_list_image_files_is_case_insensitive(tmp_path):
    """Uppercase and mixed-case extensions are accepted."""
    (tmp_path / "a.JPG").write_bytes(b"")
    (tmp_path / "b.Png").write_bytes(b"")
    assert len(list_image_files(tmp_path)) == 2


def test_list_image_files_excludes_files_without_extension(tmp_path):
    """A file with no extension is excluded."""
    (tmp_path / "README").write_bytes(b"")
    (tmp_path / "photo.png").write_bytes(b"")
    assert list_image_files(tmp_path) == [tmp_path / "photo.png"]


def test_list_image_files_excludes_subdirectories(tmp_path):
    """Subdirectories are excluded, even if their name ends in .png."""
    (tmp_path / "subdir.png").mkdir()
    (tmp_path / "real.png").write_bytes(b"")
    assert list_image_files(tmp_path) == [tmp_path / "real.png"]


def test_list_image_files_uses_only_last_suffix(tmp_path):
    """A file like archive.tar.jpg is included (suffix is .jpg)."""
    (tmp_path / "archive.tar.jpg").write_bytes(b"")
    assert list_image_files(tmp_path) == [tmp_path / "archive.tar.jpg"]


# --- list_image_files: sorting ---

def test_list_image_files_sorts_by_filename(tmp_path):
    """Files come back sorted alphabetically by name."""
    for name in ("03.png", "01.jpg", "02.jpeg"):
        (tmp_path / name).write_bytes(b"")
    names = [p.name for p in list_image_files(tmp_path)]
    assert names == ["01.jpg", "02.jpeg", "03.png"]


# --- list_image_files: errors ---

def test_list_image_files_raises_on_missing_directory(tmp_path):
    """A non-existent directory raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        list_image_files(tmp_path / "does_not_exist")


def test_list_image_files_raises_on_file_path(tmp_path):
    """A path pointing to a file raises NotADirectoryError."""
    file_path = tmp_path / "not_a_dir.txt"
    file_path.write_bytes(b"")
    with pytest.raises(NotADirectoryError):
        list_image_files(file_path)


# --- load_image: happy path ---

def test_load_image_returns_ndarray(tmp_path):
    """The result is a numpy array."""
    Image.new("RGB", (10, 10), (255, 0, 0)).save(tmp_path / "photo.png")
    result = load_image(tmp_path / "photo.png")
    assert isinstance(result, np.ndarray)


def test_load_image_preserves_non_square_shape(tmp_path):
    """Height and width are not swapped for non-square images."""
    Image.new("RGB", (200, 100), (0, 0, 0)).save(tmp_path / "wide.png")
    result = load_image(tmp_path / "wide.png")
    assert result.shape == (100, 200, 3)  # (H, W, C)


def test_load_image_returns_uint8(tmp_path):
    """Loaded images are always uint8 (IMREAD_COLOR behavior)."""
    Image.new("RGB", (10, 10), (0, 0, 0)).save(tmp_path / "photo.png")
    result = load_image(tmp_path / "photo.png")
    assert result.dtype == np.uint8


def test_load_image_handles_single_pixel_image(tmp_path):
    """A 1x1 image is a valid input."""
    Image.new("RGB", (1, 1), (255, 0, 0)).save(tmp_path / "pixel.png")
    result = load_image(tmp_path / "pixel.png")
    assert result.shape == (1, 1, 3)


# --- load_image: BGR convention (critical test) ---

def test_load_image_returns_bgr_order(tmp_path):
    """A red RGB image (255, 0, 0) is loaded as BGR (0, 0, 255)."""
    Image.new("RGB", (10, 10), (255, 0, 0)).save(tmp_path / "red.png")
    result = load_image(tmp_path / "red.png")
    assert result[0, 0].tolist() == [0, 0, 255]  # BGR red


def test_load_image_bgr_order_for_distinguishable_channels(tmp_path):
    """Every channel lands in the expected BGR position."""
    # RGB (10, 20, 30) should become BGR (30, 20, 10)
    Image.new("RGB", (10, 10), (10, 20, 30)).save(tmp_path / "mixed.png")
    result = load_image(tmp_path / "mixed.png")
    assert result[0, 0].tolist() == [30, 20, 10]


# --- load_image: IMREAD_COLOR forces 3 channels ---

def test_load_image_converts_grayscale_to_three_channels(tmp_path):
    """A grayscale PNG is loaded with 3 channels."""
    Image.new("L", (10, 10), 128).save(tmp_path / "gray.png")
    result = load_image(tmp_path / "gray.png")
    assert result.shape == (10, 10, 3)


def test_load_image_drops_alpha_channel(tmp_path):
    """An RGBA PNG is loaded as 3 channels (alpha discarded)."""
    Image.new("RGBA", (10, 10), (255, 0, 0, 128)).save(tmp_path / "rgba.png")
    result = load_image(tmp_path / "rgba.png")
    assert result.shape == (10, 10, 3)


# --- load_image: extension is not validated ---

def test_load_image_accepts_formats_outside_supported_extensions(tmp_path):
    """A .bmp file (not in SUPPORTED_EXTENSIONS) loads successfully."""
    assert ".bmp" not in SUPPORTED_EXTENSIONS  # sanity: contract is 'no check'
    Image.new("RGB", (10, 10), (255, 0, 0)).save(tmp_path / "photo.bmp", format="BMP")
    result = load_image(tmp_path / "photo.bmp")
    assert result.shape == (10, 10, 3)


# --- load_image: FileNotFoundError ---

def test_load_image_raises_on_missing_file(tmp_path):
    """A non-existent path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_image(tmp_path / "does_not_exist.png")


def test_load_image_error_message_mentions_path(tmp_path):
    """The FileNotFoundError message includes the requested path."""
    missing = tmp_path / "missing.png"
    with pytest.raises(FileNotFoundError, match=re.escape(str(missing))):
        load_image(missing)


# --- load_image: ValueError for unreadable files ---

def test_load_image_raises_on_corrupt_file(tmp_path):
    """A file with garbage bytes raises ValueError."""
    bad = tmp_path / "corrupt.png"
    bad.write_bytes(b"this is not an image, just some text that looks like one")
    with pytest.raises(ValueError, match="Could not read image"):
        load_image(bad)


def test_load_image_raises_on_text_file(tmp_path):
    """A plain text file with a non-image extension raises ValueError."""
    txt = tmp_path / "notes.txt"
    txt.write_text("hello world")
    with pytest.raises(ValueError):
        load_image(txt)


def test_load_image_error_message_mentions_path_and_reason(tmp_path):
    """The ValueError message is informative (path plus a hint)."""
    bad = tmp_path / "corrupt.png"
    bad.write_bytes(b"garbage")
    with pytest.raises(ValueError, match=r"corrupt\.png.*corrupt|corrupt\.png.*not supported"):
        load_image(bad)


# --- save_image: happy path ---

def test_save_image_creates_png_file(tmp_path):
    """Saving a PNG produces a file at the expected path."""
    target = tmp_path / "out.png"
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    save_image(target, image, 300)
    assert target.exists()


def test_save_image_creates_jpeg_file(tmp_path):
    """Saving a JPG produces a file at the expected path."""
    target = tmp_path / "out.jpg"
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    save_image(target, image, 300)
    assert target.exists()


def test_save_image_returns_none(tmp_path):
    """The function is a side-effect-only helper; it returns None."""
    target = tmp_path / "out.png"
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    assert save_image(target, image, 300) is None


# --- save_image: format is determined by extension ---

def test_save_image_png_extension_produces_png_format(tmp_path):
    """A .png extension produces a PNG file."""
    target = tmp_path / "out.png"
    save_image(target, np.zeros((10, 10, 3), dtype=np.uint8), 300)
    assert Image.open(target).format == "PNG"


def test_save_image_jpg_extension_produces_jpeg_format(tmp_path):
    """A .jpg extension produces a JPEG file."""
    target = tmp_path / "out.jpg"
    save_image(target, np.zeros((10, 10, 3), dtype=np.uint8), 300)
    assert Image.open(target).format == "JPEG"


def test_save_image_accepts_uppercase_extension(tmp_path):
    """The extension comparison is case-insensitive."""
    target = tmp_path / "OUT.PNG"
    save_image(target, np.zeros((10, 10, 3), dtype=np.uint8), 300)
    assert target.exists()
    assert Image.open(target).format == "PNG"


# --- save_image: BGR->RGB conversion (critical) ---

def test_save_image_saves_bgr_red_as_rgb_red(tmp_path):
    """A pure red BGR pixel is saved as a pure red RGB pixel."""
    target = tmp_path / "red.png"
    bgr_red = np.zeros((10, 10, 3), dtype=np.uint8)
    bgr_red[:, :] = [0, 0, 255]  # B=0, G=0, R=255 (red in BGR)
    save_image(target, bgr_red, 300)
    rgb = Image.open(target).convert("RGB")
    assert rgb.getpixel((0, 0)) == (255, 0, 0)


def test_save_image_preserves_distinguishable_channels(tmp_path):
    """All three channels land in the expected RGB position after saving."""
    target = tmp_path / "mixed.png"
    bgr = np.zeros((10, 10, 3), dtype=np.uint8)
    bgr[:, :] = [10, 20, 30]  # B=10, G=20, R=30
    save_image(target, bgr, 300)
    rgb = Image.open(target).convert("RGB")
    assert rgb.getpixel((0, 0)) == (30, 20, 10)  # R=30, G=20, B=10


def test_save_image_roundtrip_through_load_image(tmp_path):
    """BGR -> save -> load returns the original BGR values (PNG, lossless)."""
    target = tmp_path / "roundtrip.png"
    bgr = np.zeros((10, 10, 3), dtype=np.uint8)
    bgr[:, :] = [10, 20, 30]
    save_image(target, bgr, 300)
    loaded = load_image(target)
    assert loaded.shape == (10, 10, 3)
    assert loaded[0, 0].tolist() == [10, 20, 30]


# --- save_image: parent directory creation ---

def test_save_image_creates_missing_parent_directories(tmp_path):
    """Saving to a nested non-existent path creates parents automatically."""
    target = tmp_path / "a" / "b" / "c" / "out.png"
    save_image(target, np.zeros((10, 10, 3), dtype=np.uint8), 300)
    assert target.exists()
    assert target.parent.is_dir()


def test_save_image_works_when_parent_already_exists(tmp_path):
    """Saving to a path whose parent exists does not raise."""
    target = tmp_path / "out.png"
    save_image(target, np.zeros((10, 10, 3), dtype=np.uint8), 300)
    assert target.exists()


# --- save_image: DPI metadata ---

@pytest.mark.parametrize("dpi", [72, 150, 300, 600])
def test_save_image_embeds_dpi_in_png(tmp_path, dpi):
    """The requested DPI is embedded in PNG metadata."""
    target = tmp_path / "out.png"
    save_image(target, np.zeros((10, 10, 3), dtype=np.uint8), dpi)
    metadata_dpi = Image.open(target).info["dpi"]
    # PNG stores DPI as pixels per meter (integer); small rounding
    assert metadata_dpi[0] == pytest.approx(dpi, abs=1.0)
    assert metadata_dpi[1] == pytest.approx(dpi, abs=1.0)


@pytest.mark.parametrize("dpi", [72, 150, 300, 600])
def test_save_image_embeds_dpi_in_jpeg(tmp_path, dpi):
    """The requested DPI is embedded in JPEG metadata."""
    target = tmp_path / "out.jpg"
    save_image(target, np.zeros((10, 10, 3), dtype=np.uint8), dpi)
    metadata_dpi = Image.open(target).info["dpi"]
    assert metadata_dpi[0] == pytest.approx(dpi, abs=1.0)


def test_save_image_accepts_float_dpi(tmp_path):
    """A fractional DPI is accepted and embedded (rounded by the format)."""
    target = tmp_path / "out.png"
    save_image(target, np.zeros((10, 10, 3), dtype=np.uint8), 300.5)
    metadata_dpi = Image.open(target).info["dpi"]
    assert metadata_dpi[0] == pytest.approx(300.5, abs=1.0)


# --- save_image: validation is delegated ---

def test_save_image_rejects_invalid_dpi_type(tmp_path):
    """A non-numeric dpi raises TypeError before touching the filesystem."""
    with pytest.raises(TypeError):
        save_image(
            tmp_path / "out.png", np.zeros((10, 10, 3), dtype=np.uint8), "300"
        )


@pytest.mark.parametrize("dpi", [0, -1, float("nan")])
def test_save_image_rejects_invalid_dpi(tmp_path, dpi):
    """Non-positive or non-finite dpi raises ValueError."""
    with pytest.raises(ValueError):
        save_image(tmp_path / "out.png", np.zeros((10, 10, 3), dtype=np.uint8), dpi)


def test_save_image_rejects_unsupported_extension(tmp_path):
    """An extension outside SUPPORTED_EXTENSIONS raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported extension"):
        save_image(
            tmp_path / "out.txt", np.zeros((10, 10, 3), dtype=np.uint8), 300
        )


def test_save_image_rejects_2d_image(tmp_path):
    """A 2D (grayscale) image is rejected with a shape error."""
    with pytest.raises(ValueError, match="3-channel"):
        save_image(tmp_path / "out.png", np.zeros((10, 10), dtype=np.uint8), 300)


def test_save_image_rejects_non_uint8_image(tmp_path):
    """A float image is rejected with a dtype error."""
    with pytest.raises(ValueError, match="uint8"):
        save_image(
            tmp_path / "out.png", np.zeros((10, 10, 3), dtype=np.float32), 300
        )


# --- save_image: validation order (explicit contract) ---

def test_save_image_reports_dpi_error_before_extension_error(tmp_path):
    """When dpi and extension are both invalid, dpi error is reported first."""
    with pytest.raises(TypeError, match="dpi"):
        save_image(
            tmp_path / "out.txt",
            np.zeros((10, 10, 3), dtype=np.uint8),
            "not a number",
        )


def test_save_image_reports_extension_error_before_image_error(tmp_path):
    """When extension and image are both invalid, extension error comes first."""
    with pytest.raises(ValueError, match="Unsupported extension"):
        save_image(tmp_path / "out.txt", np.zeros((10, 10), dtype=np.uint8), 300)


# --- save_image: no filesystem side effects before validation ---

def test_save_image_does_not_create_directory_on_dpi_error(tmp_path):
    """An invalid dpi must not leave a directory behind."""
    target = tmp_path / "newdir" / "out.png"
    with pytest.raises(ValueError):
        save_image(target, np.zeros((10, 10, 3), dtype=np.uint8), -1)
    assert not (tmp_path / "newdir").exists()


def test_save_image_does_not_create_directory_on_extension_error(tmp_path):
    """An invalid extension must not leave a directory behind."""
    target = tmp_path / "newdir" / "out.txt"
    with pytest.raises(ValueError):
        save_image(target, np.zeros((10, 10, 3), dtype=np.uint8), 300)
    assert not (tmp_path / "newdir").exists()


def test_save_image_does_not_create_directory_on_image_error(tmp_path):
    """An invalid image must not leave a directory behind."""
    target = tmp_path / "newdir" / "out.png"
    with pytest.raises(ValueError):
        save_image(target, np.zeros((10, 10), dtype=np.uint8), 300)
    assert not (tmp_path / "newdir").exists()


# --- save_pdf: happy path ---

def test_save_pdf_creates_pdf_file(tmp_path):
    """Saving produces a file at the expected path with a PDF magic header."""
    target = tmp_path / "out.pdf"
    save_pdf(target, np.zeros((100, 100, 3), dtype=np.uint8), 300)
    assert target.exists()
    assert target.read_bytes().startswith(b"%PDF-")


def test_save_pdf_returns_none(tmp_path):
    """The function is a side-effect-only helper; it returns None."""
    target = tmp_path / "out.pdf"
    assert save_pdf(target, np.zeros((10, 10, 3), dtype=np.uint8), 300) is None


def test_save_pdf_produces_single_page(tmp_path):
    """The resulting PDF has exactly one page."""
    target = tmp_path / "out.pdf"
    save_pdf(target, np.zeros((100, 100, 3), dtype=np.uint8), 300)
    assert len(pypdf.PdfReader(target).pages) == 1


def test_save_pdf_accepts_uppercase_extension(tmp_path):
    """A .PDF extension (uppercase) is accepted."""
    target = tmp_path / "OUT.PDF"
    save_pdf(target, np.zeros((100, 100, 3), dtype=np.uint8), 300)
    assert target.exists()
    assert target.read_bytes().startswith(b"%PDF-")


# --- save_pdf: physical page size (the core logic) ---

def test_save_pdf_page_size_matches_us_letter_at_300_dpi(tmp_path):
    """The docstring example: 2550x3300 at 300 DPI produces 8.5" x 11" (612 x 792 pts)."""
    target = tmp_path / "letter.pdf"
    image = np.zeros((3300, 2550, 3), dtype=np.uint8)  # (H, W, C)
    save_pdf(target, image, 300)
    page = pypdf.PdfReader(target).pages[0]
    assert float(page.mediabox.width) == pytest.approx(612.0, abs=1.0)
    assert float(page.mediabox.height) == pytest.approx(792.0, abs=1.0)


def test_save_pdf_page_size_at_72_dpi_equals_pixels(tmp_path):
    """At 72 DPI, 1 pixel = 1 point, so the page size in points equals the pixel size."""
    target = tmp_path / "72dpi.pdf"
    image = np.zeros((200, 100, 3), dtype=np.uint8)  # H=200, W=100
    save_pdf(target, image, 72)
    page = pypdf.PdfReader(target).pages[0]
    assert float(page.mediabox.width) == pytest.approx(100.0, abs=1.0)
    assert float(page.mediabox.height) == pytest.approx(200.0, abs=1.0)


def test_save_pdf_page_size_scales_inversely_with_dpi(tmp_path):
    """Halving the DPI doubles the page size (same pixel count, larger physical page)."""
    image = np.zeros((3300, 2550, 3), dtype=np.uint8)
    target_300 = tmp_path / "at300.pdf"
    target_150 = tmp_path / "at150.pdf"
    save_pdf(target_300, image, 300)
    save_pdf(target_150, image, 150)
    page_300 = pypdf.PdfReader(target_300).pages[0]
    page_150 = pypdf.PdfReader(target_150).pages[0]
    assert float(page_150.mediabox.width) == pytest.approx(
        2 * float(page_300.mediabox.width), abs=1.0
    )
    assert float(page_150.mediabox.height) == pytest.approx(
        2 * float(page_300.mediabox.height), abs=1.0
    )


def test_save_pdf_preserves_image_aspect_ratio_in_page(tmp_path):
    """A 2:1 image produces a 2:1 page (in points)."""
    target = tmp_path / "wide.pdf"
    image = np.zeros((100, 200, 3), dtype=np.uint8)  # 2:1 wide
    save_pdf(target, image, 72)
    page = pypdf.PdfReader(target).pages[0]
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    assert width / height == pytest.approx(2.0, abs=0.01)


def test_save_pdf_accepts_float_dpi(tmp_path):
    """A fractional DPI is accepted and reflected in the page size."""
    target = tmp_path / "fractional.pdf"
    image = np.zeros((300, 300, 3), dtype=np.uint8)
    save_pdf(target, image, 144.5)
    page = pypdf.PdfReader(target).pages[0]
    expected = 300 * 72 / 144.5  # ~149.48 pts
    assert float(page.mediabox.width) == pytest.approx(expected, abs=1.0)


# --- save_pdf: parent directory creation ---

def test_save_pdf_creates_missing_parent_directories(tmp_path):
    """Saving to a nested non-existent path creates parents automatically."""
    target = tmp_path / "a" / "b" / "out.pdf"
    save_pdf(target, np.zeros((10, 10, 3), dtype=np.uint8), 300)
    assert target.exists()
    assert target.parent.is_dir()


# --- save_pdf: validation ---

def test_save_pdf_rejects_non_pdf_extension(tmp_path):
    """A non-.pdf extension is rejected with ValueError."""
    with pytest.raises(ValueError, match="Unsupported extension"):
        save_pdf(
            tmp_path / "out.png", np.zeros((10, 10, 3), dtype=np.uint8), 300
        )


def test_save_pdf_rejects_path_without_extension(tmp_path):
    """A path with no extension is rejected."""
    with pytest.raises(ValueError, match="Unsupported extension"):
        save_pdf(tmp_path / "out", np.zeros((10, 10, 3), dtype=np.uint8), 300)


def test_save_pdf_rejects_invalid_dpi_type(tmp_path):
    """A non-numeric dpi raises TypeError."""
    with pytest.raises(TypeError, match="dpi"):
        save_pdf(
            tmp_path / "out.pdf", np.zeros((10, 10, 3), dtype=np.uint8), "300"
        )


@pytest.mark.parametrize("dpi", [0, -1, float("nan"), float("inf")])
def test_save_pdf_rejects_invalid_dpi(tmp_path, dpi):
    """Non-positive or non-finite dpi raises ValueError."""
    with pytest.raises(ValueError):
        save_pdf(tmp_path / "out.pdf", np.zeros((10, 10, 3), dtype=np.uint8), dpi)


def test_save_pdf_rejects_2d_image(tmp_path):
    """A 2D (grayscale) image is rejected with a shape error."""
    with pytest.raises(ValueError, match="3-channel"):
        save_pdf(tmp_path / "out.pdf", np.zeros((10, 10), dtype=np.uint8), 300)


def test_save_pdf_rejects_non_uint8_image(tmp_path):
    """A float image is rejected with a dtype error."""
    with pytest.raises(ValueError, match="uint8"):
        save_pdf(
            tmp_path / "out.pdf", np.zeros((10, 10, 3), dtype=np.float32), 300
        )


# --- save_pdf: validation order (explicit contract) ---

def test_save_pdf_reports_dpi_error_before_extension_error(tmp_path):
    """When dpi and extension are both invalid, dpi error is reported first."""
    with pytest.raises(TypeError, match="dpi"):
        save_pdf(
            tmp_path / "out.txt",
            np.zeros((10, 10, 3), dtype=np.uint8),
            "not a number",
        )


def test_save_pdf_reports_extension_error_before_image_error(tmp_path):
    """When extension and image are both invalid, extension error comes first."""
    with pytest.raises(ValueError, match="Unsupported extension"):
        save_pdf(tmp_path / "out.txt", np.zeros((10, 10), dtype=np.uint8), 300)


# --- save_pdf: no filesystem side effects before validation ---

def test_save_pdf_does_not_create_directory_on_dpi_error(tmp_path):
    """An invalid dpi must not leave a directory behind."""
    target = tmp_path / "newdir" / "out.pdf"
    with pytest.raises(ValueError):
        save_pdf(target, np.zeros((10, 10, 3), dtype=np.uint8), -1)
    assert not (tmp_path / "newdir").exists()


def test_save_pdf_does_not_create_directory_on_extension_error(tmp_path):
    """An invalid extension must not leave a directory behind."""
    target = tmp_path / "newdir" / "out.txt"
    with pytest.raises(ValueError):
        save_pdf(target, np.zeros((10, 10, 3), dtype=np.uint8), 300)
    assert not (tmp_path / "newdir").exists()


def test_save_pdf_does_not_create_directory_on_image_error(tmp_path):
    """An invalid image must not leave a directory behind."""
    target = tmp_path / "newdir" / "out.pdf"
    with pytest.raises(ValueError):
        save_pdf(target, np.zeros((10, 10), dtype=np.uint8), 300)
    assert not (tmp_path / "newdir").exists()
