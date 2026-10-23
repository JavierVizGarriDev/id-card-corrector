"""Command-line interface for id-card-corrector."""

import argparse
import sys
from pathlib import Path

from id_card_corrector.pipeline import process_directory
from id_card_corrector.selector import SelectionCancelledError


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CLI.
    
    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).
        
    Returns:
        Exit code: 0 for success, 1 for error, 130 for user cancellation.
    """
    parser = argparse.ArgumentParser(
        description="Corrige fotos de carnets y genera un PDF listo para imprimir."
    )
    parser.add_argument(
        "-i", "--input", 
        type=Path, 
        default=Path("entrada"),
        help="Carpeta de entrada con las fotos (default: entrada/)"
    )
    parser.add_argument(
        "-o", "--output", 
        type=Path, 
        default=Path("salida"),
        help="Carpeta de salida para el PDF (default: salida/)"
    )
    parser.add_argument(
        "-c", "--card", 
        type=str, 
        default="CI",
        help="Tipo de carnet (default: CI)"
    )
    parser.add_argument(
        "-s", "--sheet", 
        type=str, 
        default="CARTA",
        help="Tipo de hoja (default: CARTA)"
    )
    
    args = parser.parse_args(argv)

    try:
        result = process_directory(
            input_dir=args.input,
            output_dir=args.output,
            card_type=args.card,
            sheet_type=args.sheet,
        )
        
        # Si process_directory devuelve una lista vacía, fue una salida limpia
        # (por ejemplo, carpeta vacía). Exit 0.
        if result == []:
            return 0
            
        return 0
        
    except SelectionCancelledError:
        print("\nOperación cancelada por el usuario.")
        return 130  # Convención POSIX para "cancelado por Ctrl+C o equivalente"
        
    except KeyboardInterrupt:
        print("\nOperación interrumpida.")
        return 130
        
    except Exception as e:
        print(f"\nError inesperado: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())