"""Tests for the config module."""

from dataclasses import FrozenInstanceError

import pytest

from id_card_corrector.config import (
    SHEETS,
    SPECS,
    PhysicalSpec,
)


# --- PhysicalSpec: formula ---

@pytest.mark.parametrize(
    "width_mm, height_mm, dpi, expected_width_px, expected_height_px",
    [
        (85.6, 53.98, 300, 1011, 638),         # Cuban ID card
        (25.4, 50.8, 100, 100, 200),           # 1 inch x 2 inches, exact
        (10.0, 20.0, 100, 39, 79),             # fractional pixels, tests rounding
        (0.1, 0.1, 300, 1, 1),                 # very small, no collapse to 0
        (1000.0, 2000.0, 600, 23622, 47244),   # large values
    ],
)
def test_physical_spec_computes_pixels(
    width_mm, height_mm, dpi, expected_width_px, expected_height_px
):
    """PhysicalSpec derives pixel dimensions correctly from mm and DPI."""
    spec = PhysicalSpec(width_mm=width_mm, height_mm=height_mm, dpi=dpi)
    assert spec.width_px == expected_width_px
    assert spec.height_px == expected_height_px


def test_physical_spec_px_properties_return_int():
    """Pixel properties are integers, not floats."""
    spec = PhysicalSpec(width_mm=85.6, height_mm=53.98, dpi=300)
    assert isinstance(spec.width_px, int)
    assert isinstance(spec.height_px, int)


# --- PhysicalSpec: validation ---

def test_physical_spec_rejects_non_positive_dimensions_with_message():
    """Non-positive width or height is rejected with a clear message."""
    with pytest.raises(ValueError, match="width_mm and height_mm must be positive"):
        PhysicalSpec(width_mm=0, height_mm=50.0, dpi=300)


@pytest.mark.parametrize(
    "width_mm, height_mm",
    [(-1, 10), (10, 0), (10, -1), (0, 0), (-1, -1)],
)
def test_physical_spec_rejects_non_positive_dimensions(width_mm, height_mm):
    """Non-positive width or height is rejected."""
    with pytest.raises(ValueError):
        PhysicalSpec(width_mm=width_mm, height_mm=height_mm, dpi=300)


def test_physical_spec_rejects_non_positive_dpi_with_message():
    """Non-positive DPI is rejected with a clear message."""
    with pytest.raises(ValueError, match="dpi must be positive"):
        PhysicalSpec(width_mm=100.0, height_mm=50.0, dpi=0)


@pytest.mark.parametrize("dpi", [-1, -100])
def test_physical_spec_rejects_non_positive_dpi(dpi):
    """Non-positive DPI is rejected."""
    with pytest.raises(ValueError):
        PhysicalSpec(width_mm=100.0, height_mm=50.0, dpi=dpi)


# --- Public contract: catalogs match declared standards ---

# Reference: ISO/IEC 7810 (ID-1 format) and ANSI/ASME Y14.1 (US Letter).
EXPECTED_CARD_STANDARDS = {
    "CI": (85.6, 53.98),
}

EXPECTED_SHEET_STANDARDS = {
    "CARTA": (215.9, 279.4),
}


@pytest.mark.parametrize("key, expected_mm", list(EXPECTED_CARD_STANDARDS.items()))
def test_card_specs_match_declared_standards(key, expected_mm):
    """Card catalog entries match their declared physical standards."""
    spec = SPECS[key]
    assert (spec.width_mm, spec.height_mm) == expected_mm


@pytest.mark.parametrize("key, expected_mm", list(EXPECTED_SHEET_STANDARDS.items()))
def test_sheet_specs_match_declared_standards(key, expected_mm):
    """Sheet catalog entries match their declared physical standards."""
    spec = SHEETS[key]
    assert (spec.width_mm, spec.height_mm) == expected_mm


def test_all_card_specs_are_covered_by_standards():
    """Every entry in SPECS has a corresponding standard test."""
    assert set(SPECS.keys()) == set(EXPECTED_CARD_STANDARDS.keys())


def test_all_sheet_specs_are_covered_by_standards():
    """Every entry in SHEETS has a corresponding standard test."""
    assert set(SHEETS.keys()) == set(EXPECTED_SHEET_STANDARDS.keys())


# --- Public contract: immutability of CardSpec ---

def test_card_spec_is_frozen():
    """CardSpec is declared frozen: instances are immutable."""
    spec = SPECS["CI"]
    with pytest.raises(FrozenInstanceError):
        spec.width_mm = 100
        