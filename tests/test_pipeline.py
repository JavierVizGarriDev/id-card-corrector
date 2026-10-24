"""Tests for the pipeline module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from id_card_corrector.composer import CardDoesNotFitError
from id_card_corrector.pipeline import process_directory
from id_card_corrector.ui.opencv.selector import SelectionCancelledError


@pytest.fixture
def dummy_corners():
    """A valid set of 4 corners."""
    return np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float32)


@pytest.fixture
def setup_dirs(tmp_path):
    """Creates entrada/ and salida/ folders."""
    input_dir = tmp_path / "entrada"
    output_dir = tmp_path / "salida"
    return input_dir, output_dir


@pytest.fixture
def ui_mock(dummy_corners):
    """A mock of the UserInterface with sensible defaults."""
    mock = MagicMock()
    mock.select_corners.return_value = dummy_corners
    mock.ask_open_pdf.return_value = False  # Don't open the PDF by default
    mock.show_issues.return_value = "confirm"
    return mock


def write_dummy_image(path: Path):
    """Write a tiny valid image to disk."""
    img = np.zeros((50, 50, 3), dtype=np.uint8)
    cv2.imwrite(str(path), img)


# --- 1. Validation of input directory and files ---

def test_empty_input_directory(setup_dirs, ui_mock):
    """No images in the input folder returns an empty list."""
    input_dir, output_dir = setup_dirs
    result = process_directory(input_dir, output_dir, ui=ui_mock)
    assert result == []


def test_too_many_images(setup_dirs, ui_mock):
    """More than 2 images raises ValueError."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    for i in range(3):
        write_dummy_image(input_dir / f"img_{i}.jpg")
        
    with pytest.raises(ValueError, match="Se esperaban 1 o 2 imágenes"):
        process_directory(input_dir, output_dir, ui=ui_mock)


# --- 2. Happy paths (with UI mocks) ---

@patch("id_card_corrector.pipeline.os.startfile")
def test_single_image_success(mock_startfile, setup_dirs, ui_mock):
    """A single image generates a single-page PDF without preview."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    write_dummy_image(input_dir / "img.jpg")
    
    result = process_directory(input_dir, output_dir, ui=ui_mock)
    
    assert isinstance(result, Path)
    assert result.name == "salida.pdf"
    assert result.exists()
    
    ui_mock.select_corners.assert_called_once()
    ui_mock.preview_sheet.assert_not_called()  # 1 image = no preview
    mock_startfile.assert_not_called()  # ask_open_pdf returned False


def test_two_images_confirm_preview(setup_dirs, ui_mock):
    """Two images trigger the preview loop, and 'confirm' accepts it."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    write_dummy_image(input_dir / "front.jpg")
    write_dummy_image(input_dir / "back.jpg")
    
    ui_mock.preview_sheet.return_value = "confirm"
    
    result = process_directory(input_dir, output_dir, ui=ui_mock)
    
    assert isinstance(result, Path)
    assert result.name == "salida.pdf"
    assert result.exists()
    
    assert ui_mock.select_corners.call_count == 2
    ui_mock.preview_sheet.assert_called_once()


def test_two_images_swap_then_confirm(setup_dirs, ui_mock):
    """Pressing 'swap' loops back to preview, then 'confirm' exits."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    write_dummy_image(input_dir / "front.jpg")
    write_dummy_image(input_dir / "back.jpg")
    
    # First call returns 'swap', second returns 'confirm'
    ui_mock.preview_sheet.side_effect = ["swap", "confirm"]
    
    result = process_directory(input_dir, output_dir, ui=ui_mock)
    assert result.exists()
    assert ui_mock.preview_sheet.call_count == 2


def test_two_images_cancel_preview(setup_dirs, ui_mock):
    """Pressing ESC in the preview raises SelectionCancelledError."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    write_dummy_image(input_dir / "front.jpg")
    write_dummy_image(input_dir / "back.jpg")
    
    ui_mock.preview_sheet.return_value = "cancel"
    
    with pytest.raises(SelectionCancelledError, match="Cancelado en la vista previa"):
        process_directory(input_dir, output_dir, ui=ui_mock)


# --- 3. Edge Cases ---

@patch("id_card_corrector.pipeline.compose_sheet")
def test_fallback_to_jpgs_when_card_does_not_fit(mock_compose, setup_dirs, ui_mock):
    """Caso Límite 1: compose_sheet raises CardDoesNotFitError, pipeline saves JPGs."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    write_dummy_image(input_dir / "front.jpg")
    
    mock_compose.side_effect = CardDoesNotFitError("Too big")
    
    result = process_directory(input_dir, output_dir, ui=ui_mock)
    
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].name == "tarjeta_1.jpg"
    assert result[0].exists()


@patch("id_card_corrector.pipeline.os.startfile")
def test_prompt_open_pdf(mock_startfile, setup_dirs, ui_mock):
    """If ui.ask_open_pdf returns True, os.startfile is called."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    write_dummy_image(input_dir / "img.jpg")
    
    # Tell the mock to say "Yes, open it"
    ui_mock.ask_open_pdf.return_value = True
    
    result = process_directory(input_dir, output_dir, ui=ui_mock)
    
    mock_startfile.assert_called_once_with(result)


def test_pdf_name_collision_handling(setup_dirs, ui_mock):
    """If salida.pdf exists, it generates salida-1.pdf."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    output_dir.mkdir()
    write_dummy_image(input_dir / "img.jpg")
    
    # Pre-create a fake PDF to force the collision
    (output_dir / "salida.pdf").write_text("fake existing pdf")
    
    result = process_directory(input_dir, output_dir, ui=ui_mock)
        
    assert isinstance(result, Path)
    assert result.name == "salida-1.pdf"
    assert result.exists()