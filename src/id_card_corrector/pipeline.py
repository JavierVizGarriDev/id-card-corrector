"""End-to-end processing pipeline for ID card correction."""

import os
from pathlib import Path

import numpy as np

from id_card_corrector.composer import CardDoesNotFitError, compose_sheet
from id_card_corrector.config import MARGIN_MM, SHEETS, SPECS
from id_card_corrector.geometry import warp_to_rectangle
from id_card_corrector.io_utils import (
    ensure_directory,
    list_image_files,
    load_image,
    save_image,
    save_pdf,
)
from id_card_corrector.preview import preview_sheet
from id_card_corrector.selector import SelectionCancelledError, select_corners


def _prompt_open_pdf(pdf_path: Path) -> None:
    """Ask the user if they want to open the generated PDF."""
    try:
        answer = input("\n¿Abrir el PDF generado ahora? (S/n): ").strip().lower()
        if answer in ("", "s", "si", "y", "yes"):
            os.startfile(pdf_path)
    except Exception as e:
        print(f"No se pudo abrir el PDF automáticamente: {e}")


def process_directory(
    input_dir: Path,
    output_dir: Path,
    card_type: str = "CI",
    sheet_type: str = "CARTA",
) -> Path | list[Path]:
    """Process images in input_dir and generate the output.
    
    Args:
        input_dir: Folder with the original photos.
        output_dir: Folder where the PDF or JPGs will be saved.
        card_type: Key for the card dimensions in SPECS (e.g., "CI").
        sheet_type: Key for the sheet dimensions in SHEETS (e.g., "CARTA").
        
    Returns:
        The path of the generated PDF, or a list of JPG paths if
        the cards do not fit on the sheet (Caso Límite 1).
        
    Raises:
        ValueError: for invalid input (empty dir, too many files).
        SelectionCancelledError: if the user cancels during selection.
    """
    ensure_directory(input_dir)
    ensure_directory(output_dir)

    files = list_image_files(input_dir)
    if len(files) == 0:
        print(f"\nNo se encontraron imágenes en '{input_dir}'.")
        input("Pulsa ENTER para salir...")
        return []
    if len(files) > 2:
        raise ValueError(f"Se esperaban 1 o 2 imágenes, pero se encontraron {len(files)}.")

    card_spec = SPECS[card_type]
    sheet_spec = SHEETS[sheet_type]

    cards = []
    print(f"\nProcesando {len(files)} imagen(es)...")

    for i, file_path in enumerate(files):
        print(f"\n--- Imagen {i+1}: {file_path.name} ---")
        img = load_image(file_path)
        
        # select_corners will raise SelectionCancelledError if aborted
        corners = select_corners(img)
        
        corrected = warp_to_rectangle(
            img, corners, card_spec.width_px, card_spec.height_px
        )
        cards.append(corrected)

    # Generate output filename (salida.pdf, salida-1.pdf, etc.)
    base_name = "salida"
    pdf_path = output_dir / f"{base_name}.pdf"
    counter = 1
    while pdf_path.exists():
        pdf_path = output_dir / f"{base_name}-{counter}.pdf"
        counter += 1

    # Try composing and previewing
    try:
        # If only 1 card, no preview loop needed (as per design).
        if len(cards) == 1:
            pages = compose_sheet(cards, sheet_spec, MARGIN_MM)
        else:
            # 2 cards: preview loop with swap
            while True:
                pages = compose_sheet(cards, sheet_spec, MARGIN_MM)
                
                # If L2 happened (2 pages), swap doesn't make sense. 
                # Show first page just to confirm.
                display_page = pages[0]
                choice = preview_sheet(display_page)
                
                if choice == "cancel":
                    raise SelectionCancelledError("Cancelado en la vista previa.")
                elif choice == "confirm":
                    break
                elif choice == "swap":
                    cards.reverse()

        # Save as PDF
        save_pdf(pdf_path, pages, dpi=sheet_spec.dpi)
        print(f"\nPDF generado exitosamente: {pdf_path}")
        _prompt_open_pdf(pdf_path)
        return pdf_path

    except CardDoesNotFitError:
        # Caso Límite 1: Does not fit even rotated.
        print("\n[!] El carnet es demasiado grande para la hoja.")
        print("    Se guardarán las imágenes corregidas como JPG sueltos.")
        
        jpg_paths = []
        for i, card in enumerate(cards, start=1):
            jpg_path = output_dir / f"tarjeta_{i}.jpg"
            save_image(jpg_path, card, dpi=card_spec.dpi)
            jpg_paths.append(jpg_path)
            print(f"    Guardado: {jpg_path}")
            
        return jpg_paths