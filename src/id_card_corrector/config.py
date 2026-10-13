"""Physical specifications and layout constants."""

from dataclasses import dataclass

# Conversion factor. Never changes.
MM_PER_INCH = 25.4

# Master margin for layout. Provisional value, to be adjusted
# visually once the first PDF is generated.
MARGIN = 100 # pixels


@dataclass(frozen=True)
class CardSpec:
    """Physical dimensions and output resolution for an ID card."""

    width_mm: float
    height_mm: float
    dpi: int

    @property
    def width_px(self) -> int:
        """Card width in pixels, derived from mm and DPI."""
        return round(self.width_mm / MM_PER_INCH * self.dpi)

    @property
    def height_px(self) -> int:
        """Card height in pixels, derived from mm and DPI."""
        return round(self.height_mm / MM_PER_INCH * self.dpi)


@dataclass(frozen=True)
class SheetSpec:
    """Physical dimensions and output resolution for a sheet of paper."""

    width_mm: float
    height_mm: float
    dpi: int

    @property
    def width_px(self) -> int:
        """Sheet width in pixels, derived from mm and DPI."""
        return round(self.width_mm / MM_PER_INCH * self.dpi)

    @property
    def height_px(self) -> int:
        """Sheet height in pixels, derived from mm and DPI."""
        return round(self.height_mm / MM_PER_INCH * self.dpi)


# Catalog of supported document types.
# Currently only the Cuban ID card (CI) is defined. More types
# (ONAT card, driver's license, etc.) will be added later.
SPECS: dict[str, CardSpec] = {
    "CI": CardSpec(width_mm=85.6, height_mm=53.98, dpi=300),
}

# Catalog of supported sheet types.
# Currently only US Letter (vertical) is defined.
SHEETS: dict[str, SheetSpec] = {
    "CARTA": SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300),
}