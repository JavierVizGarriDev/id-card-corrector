"""End-to-end processing pipeline for ID card correction."""

import os
from pathlib import Path

import numpy as np

from id_card_corrector.geometry import (
    DegenerateQuadrilateralError,
    Issue,
    validate_quadrilateral,
    warp_to_rectangle
)
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
from id_card_corrector.ui.opencv.preview import preview_sheet
from id_card_corrector.ui.opencv.selector import SelectionCancelledError, select_corners
from id_card_corrector.ui.interface import UserInterface


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
    ui: UserInterface,
    card_type: str = "CI",
    sheet_type: str = "CARTA",
) -> Path | list[Path]:
    """Process images in input_dir and generate the output."""
    ensure_directory(input_dir)
    ensure_directory(output_dir)

    files = list_image_files(input_dir)
    if len(files) == 0:
        ui.notify(f"No se encontraron imágenes en '{input_dir}'.")
        return []
    if len(files) > 2:
        raise ValueError(f"Se esperaban 1 o 2 imágenes, pero se encontraron {len(files)}.")

    card_spec = SPECS[card_type]
    sheet_spec = SHEETS[sheet_type]

    cards = []
    ui.notify(f"\nProcesando {len(files)} imagen(es)...")

    for i, file_path in enumerate(files):
        ui.notify(f"\n--- Imagen {i+1}: {file_path.name} ---")
        img = load_image(file_path)
        
        while True:
            corners = ui.select_corners(img)
            
            try:
                issues = validate_quadrilateral(corners)
                if issues:
                    choice = ui.show_issues(issues)
                    if choice == "restart":
                        continue
                break
            except DegenerateQuadrilateralError as e:
                ui.show_error(str(e))
                continue

        corrected = warp_to_rectangle(
            img, corners, card_spec.width_px, card_spec.height_px
        )
        cards.append(corrected)

    base_name = "salida"
    pdf_path = output_dir / f"{base_name}.pdf"
    counter = 1
    while pdf_path.exists():
        pdf_path = output_dir / f"{base_name}-{counter}.pdf"
        counter += 1

    try:
        if len(cards) == 1:
            pages = compose_sheet(cards, sheet_spec, MARGIN_MM)
        else:
            while True:
                pages = compose_sheet(cards, sheet_spec, MARGIN_MM)
                display_page = pages[0]
                choice = ui.preview_sheet(display_page)
                
                if choice == "cancel":
                    raise SelectionCancelledError("Cancelado en la vista previa.")
                elif choice == "confirm":
                    break
                elif choice == "swap":
                    cards.reverse()

        save_pdf(pdf_path, pages, dpi=sheet_spec.dpi)
        ui.notify(f"\nPDF generado exitosamente: {pdf_path}")
        
        # La UI se encarga de abrirlo, descargarlo o lo que sea.
        ui.show_pdf_success(str(pdf_path))
            
        return pdf_path

    except CardDoesNotFitError:
        ui.notify("\n[!] El carnet es demasiado grande para la hoja.")
        ui.notify("    Se guardarán las imágenes corregidas como JPG sueltos.")
        
        jpg_paths = []
        for i, card in enumerate(cards, start=1):
            jpg_path = output_dir / f"tarjeta_{i}.jpg"
            save_image(jpg_path, card, dpi=card_spec.dpi)
            jpg_paths.append(jpg_path)
            ui.notify(f"    Guardado: {jpg_path}")
            
        return jpg_paths