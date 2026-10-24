"""Tests for the pipeline module."""

import os
from pathlib import Path
from unittest.mock import patch

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


def write_dummy_image(path: Path):
    """Write a tiny valid image to disk."""
    img = np.zeros((50, 50, 3), dtype=np.uint8)
    cv2.imwrite(str(path), img)


# --- 1. Validation of input directory and files ---

def test_empty_input_directory(setup_dirs):
    """No images in the input folder returns an empty list."""
    input_dir, output_dir = setup_dirs
    with patch("builtins.input", return_value=""):
        result = process_directory(input_dir, output_dir)
    assert result == []


def test_too_many_images(setup_dirs):
    """More than 2 images raises ValueError."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    for i in range(3):
        write_dummy_image(input_dir / f"img_{i}.jpg")
        
    with pytest.raises(ValueError, match="Se esperaban 1 o 2 imágenes"):
        process_directory(input_dir, output_dir)


# --- 2. Happy paths (with mocks) ---

@patch("id_card_corrector.pipeline.select_corners")
@patch("id_card_corrector.pipeline.os.startfile")
@patch("builtins.input", return_value="n")  # Don't open PDF
def test_single_image_success(mock_input, mock_startfile, mock_select, setup_dirs, dummy_corners):
    """A single image generates a single-page PDF without preview."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    write_dummy_image(input_dir / "img.jpg")
    
    mock_select.return_value = dummy_corners
    
    result = process_directory(input_dir, output_dir)
    
    assert isinstance(result, Path)
    assert result.name == "salida.pdf"
    assert result.exists()
    
    # select_corners called exactly once
    mock_select.assert_called_once()
    # os.startfile not called (user said 'n')
    mock_startfile.assert_not_called()


@patch("id_card_corrector.pipeline.preview_sheet")
@patch("id_card_corrector.pipeline.select_corners")
@patch("id_card_corrector.pipeline.os.startfile")
@patch("builtins.input", return_value="n")
def test_two_images_confirm_preview(mock_input, mock_startfile, mock_select, mock_preview, setup_dirs, dummy_corners):
    """Two images trigger the preview loop, and ENTER confirms it."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    write_dummy_image(input_dir / "front.jpg")
    write_dummy_image(input_dir / "back.jpg")
    
    mock_select.return_value = dummy_corners
    mock_preview.return_value = "confirm"
    
    result = process_directory(input_dir, output_dir)
    
    assert isinstance(result, Path)
    assert result.name == "salida.pdf"
    assert result.exists()
    
    # select_corners called twice (once per image)
    assert mock_select.call_count == 2
    # preview_sheet called once (user confirmed immediately)
    mock_preview.assert_called_once()


@patch("id_card_corrector.pipeline.preview_sheet")
@patch("id_card_corrector.pipeline.select_corners")
@patch("id_card_corrector.pipeline.os.startfile")
@patch("builtins.input", return_value="n")
def test_two_images_swap_then_confirm(mock_input, mock_startfile, mock_select, mock_preview, setup_dirs, dummy_corners):
    """Pressing 'swap' loops back to preview, then confirm exits."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    write_dummy_image(input_dir / "front.jpg")
    write_dummy_image(input_dir / "back.jpg")
    
    mock_select.return_value = dummy_corners
    # First call returns 'swap', second returns 'confirm'
    mock_preview.side_effect = ["swap", "confirm"]
    
    result = process_directory(input_dir, output_dir)
    assert result.exists()
    # preview_sheet called twice
    assert mock_preview.call_count == 2


@patch("id_card_corrector.pipeline.preview_sheet")
@patch("id_card_corrector.pipeline.select_corners")
def test_two_images_cancel_preview(mock_select, mock_preview, setup_dirs, dummy_corners):
    """Pressing ESC in the preview raises SelectionCancelledError."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    write_dummy_image(input_dir / "front.jpg")
    write_dummy_image(input_dir / "back.jpg")
    
    mock_select.return_value = dummy_corners
    mock_preview.return_value = "cancel"
    
    with pytest.raises(SelectionCancelledError, match="Cancelado en la vista previa"):
        process_directory(input_dir, output_dir)


# --- 3. Edge Cases ---

@patch("id_card_corrector.pipeline.compose_sheet")
@patch("id_card_corrector.pipeline.select_corners")
@patch("builtins.input", return_value="n")
def test_fallback_to_jpgs_when_card_does_not_fit(mock_input, mock_select, mock_compose, setup_dirs, dummy_corners):
    """Caso Límite 1: compose_sheet raises CardDoesNotFitError, pipeline saves JPGs."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    write_dummy_image(input_dir / "front.jpg")
    
    mock_select.return_value = dummy_corners
    mock_compose.side_effect = CardDoesNotFitError("Too big")
    
    result = process_directory(input_dir, output_dir)
    
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].name == "tarjeta_1.jpg"
    assert result[0].exists()


@patch("id_card_corrector.pipeline.select_corners")
@patch("id_card_corrector.pipeline.os.startfile")
@patch("builtins.input", return_value="s")  # Yes, open PDF
def test_prompt_open_pdf(mock_input, mock_startfile, mock_select, setup_dirs, dummy_corners):
    """If the user answers 's', os.startfile is called."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    write_dummy_image(input_dir / "img.jpg")
    mock_select.return_value = dummy_corners
    
    result = process_directory(input_dir, output_dir)
    
    mock_startfile.assert_called_once_with(result)


def test_pdf_name_collision_handling(setup_dirs, dummy_corners):
    """If salida.pdf exists, it generates salida-1.pdf."""
    input_dir, output_dir = setup_dirs
    input_dir.mkdir()
    output_dir.mkdir()
    write_dummy_image(input_dir / "img.jpg")
    
    # Pre-create a fake PDF
    (output_dir / "salida.pdf").write_text("fake existing pdf")
    
    with patch("id_card_corrector.pipeline.select_corners", return_value=dummy_corners), \
         patch("builtins.input", return_value="n"):
        result = process_directory(input_dir, output_dir)
        
    assert isinstance(result, Path)
    assert result.name == "salida-1.pdf"
    assert result.exists()