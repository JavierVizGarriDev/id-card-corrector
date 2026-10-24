"""Tests for the CLI module."""

import sys
from pathlib import Path
from unittest.mock import ANY, patch

import pytest

from id_card_corrector.cli import main
from id_card_corrector.ui.opencv.selector import SelectionCancelledError


@patch("id_card_corrector.cli.process_directory")
def test_cli_defaults(mock_process):
    """With no arguments, it uses default paths and card/sheet types."""
    mock_process.return_value = Path("salida.pdf")
    
    # Simulate running `python -m id_card_corrector`
    exit_code = main([])
    
    assert exit_code == 0
    # Check that defaults were passed to the pipeline
    mock_process.assert_called_once_with(
        input_dir=Path("entrada"),
        output_dir=Path("salida"),
        ui=ANY,  # <--- Añadido: ignoramos el objeto UI concreto
        card_type="CI",
        sheet_type="CARTA"
    )


@patch("id_card_corrector.cli.process_directory")
def test_cli_custom_arguments(mock_process):
    """Flags override the defaults and are passed to the pipeline."""
    mock_process.return_value = Path("out.pdf")
    
    args = ["-i", "my_input", "-o", "my_output", "-c", "ONAT", "-s", "A4"]
    exit_code = main(args)
    
    assert exit_code == 0
    mock_process.assert_called_once_with(
        input_dir=Path("my_input"),
        output_dir=Path("my_output"),
        ui=ANY,  # <--- Añadido
        card_type="ONAT",
        sheet_type="A4"
    )


@patch("id_card_corrector.cli.process_directory")
def test_cli_handles_empty_result(mock_process):
    """An empty list (e.g., empty input folder) is a clean exit (0)."""
    mock_process.return_value = []
    assert main([]) == 0


@patch("id_card_corrector.cli.process_directory")
def test_cli_handles_selection_cancelled(mock_process, capsys):
    """SelectionCancelledError returns exit code 130 and prints a message."""
    mock_process.side_effect = SelectionCancelledError("Cancelled")
    
    exit_code = main([])
    
    assert exit_code == 130
    captured = capsys.readouterr()
    assert "Operación cancelada por el usuario" in captured.out


@patch("id_card_corrector.cli.process_directory")
def test_cli_handles_keyboard_interrupt(mock_process, capsys):
    """KeyboardInterrupt returns exit code 130."""
    mock_process.side_effect = KeyboardInterrupt()
    
    exit_code = main([])
    
    assert exit_code == 130
    captured = capsys.readouterr()
    assert "Operación interrumpida" in captured.out


@patch("id_card_corrector.cli.process_directory")
def test_cli_handles_unexpected_exception(mock_process, capsys):
    """Any other exception returns exit code 1."""
    mock_process.side_effect = Exception("Something broke")
    
    exit_code = main([])
    
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error inesperado: Something broke" in captured.out