"""Abstract definition of the UI contract.

This module defines the `UserInterface` Protocol: the set of methods
that the pipeline needs from *any* user interface (OpenCV, web, Tkinter,
or even a mock for testing).

By depending on this Protocol instead of concrete implementations,
the pipeline remains completely decoupled from the UI technology.
"""

from typing import Protocol

import numpy as np

from id_card_corrector.geometry import Issue


class UserInterface(Protocol):
    """The contract that every UI implementation must fulfill."""

    def select_corners(self, image: np.ndarray) -> np.ndarray:
        """Display the image and let the user select four corners.

        Args:
            image: The original BGR image.

        Returns:
            An array of shape (4, 2) with the corners in
            TL, TR, BR, BL order, in the original image's coordinates.

        Raises:
            Exception: if the user cancels. Implementations should use
                a common exception (e.g., SelectionCancelledError) so
                the pipeline can catch it uniformly.
        """
        ...

    def preview_sheet(self, sheet: np.ndarray) -> str:
        """Display the composed sheet and wait for a user action.

        Args:
            sheet: The full-resolution composed sheet.

        Returns:
            "confirm" if the user accepts the sheet.
            "swap" if the user wants to swap the front and back cards.
            "cancel" if the user aborts the process.
        """
        ...

    def show_issues(self, issues: tuple[Issue, ...]) -> str:
        """Show non-fatal issues found during validation.

        Args:
            issues: A tuple of Issue members (from geometry validation).

        Returns:
            "confirm" if the user wants to proceed anyway.
            "restart" if the user wants to go back to corner selection.
        """
        ...

    def show_error(self, message: str) -> None:
        """Show a fatal error message to the user.

        Args:
            message: The error description.
        """
        ...

    def notify(self, message: str) -> None:
        """Show a simple informational message.

        Args:
            message: The message to display.
        """
        ...

    def ask_open_pdf(self, path: str) -> bool:
        """Ask the user if they want to open the generated PDF.

        Args:
            path: The path of the generated PDF (useful for display).

        Returns:
            True if the user wants to open the file, False otherwise.
        """
        ...