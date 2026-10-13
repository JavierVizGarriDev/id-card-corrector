"""Physical specifications and layout constants."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

# Conversion factor. Never changes.
MM_PER_INCH: Final[float] = 25.4

# Master margin for layout, expressed in millimeters.
# Provisional value, to be adjusted visually once the first PDF is generated.
MARGIN_MM: Final[float] = 8.47


@dataclass(frozen=True)
class PhysicalSpec:
    """Physical dimensions and output resolution of a printable item."""

    width_mm: float
    height_mm: float
    dpi: int

    def __post_init__(self) -> None:
        if self.width_mm <= 0 or self.height_mm <= 0:
            raise ValueError("width_mm and height_mm must be positive")
        if self.dpi <= 0:
            raise ValueError("dpi must be positive")

    @property
    def width_px(self) -> int:
        """Width in pixels, derived from mm and DPI."""
        return round(self.width_mm / MM_PER_INCH * self.dpi)

    @property
    def height_px(self) -> int:
        """Height in pixels, derived from mm and DPI."""
        return round(self.height_mm / MM_PER_INCH * self.dpi)


@dataclass(frozen=True)
class CardSpec(PhysicalSpec):
    """Physical dimensions and output resolution for an ID card."""


@dataclass(frozen=True)
class SheetSpec(PhysicalSpec):
    """Physical dimensions and output resolution for a sheet of paper."""


# Catalog of supported document types.
# Currently only the Cuban ID card (CI) is defined. More types
# (ONAT card, driver's license, etc.) will be added later.
SPECS: Final[Mapping[str, CardSpec]] = MappingProxyType({
    "CI": CardSpec(width_mm=85.6, height_mm=53.98, dpi=300),
})

# Catalog of supported sheet types.
# Currently only US Letter (vertical) is defined.
SHEETS: Final[Mapping[str, SheetSpec]] = MappingProxyType({
    "CARTA": SheetSpec(width_mm=215.9, height_mm=279.4, dpi=300),
})