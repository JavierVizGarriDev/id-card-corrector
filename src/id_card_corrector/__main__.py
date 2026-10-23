"""Allow running the package with `python -m id_card_corrector`."""

import sys
from id_card_corrector.cli import main

if __name__ == "__main__":
    sys.exit(main())