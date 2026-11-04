import sys
import os
from src.id_card_corrector.cli import main

# Redirigir salidas si estamos en modo --windowed (sin consola)
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

if __name__ == "__main__":
    # Ejecutamos tu CLI pasándole el argumento para usar la UI web
    # Esto iniciará el pipeline y el servidor automáticamente
    sys.exit(main(["--ui", "web"]))