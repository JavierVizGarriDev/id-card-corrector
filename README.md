# id-card-corrector

A modular tool to correct perspective from ID card photos and generate print-ready PDFs.

> English · [Versión en español](README.es.md)

---

## Overview

At the print shop where I work, customers often send photos of their ID cards to be copied or printed. These photos are almost always taken at an angle, poorly framed, and need to be resized to their real physical dimensions. The manual process in Photoshop (correcting perspective, resizing, repeating for the back side, and arranging both on a Letter sheet) took about 5 minutes per document.

**id-card-corrector** automates this workflow. It opens a window where you click the four corners of the card, applies a perspective transformation, resizes the result to the exact ID-1 standard (85.6 × 53.98 mm at 300 DPI), and composes both sides (front and back) onto a single Letter-size sheet. The final output is a print-ready PDF.

Built as the first tool in a long-term vision of modular print-shop utilities that will eventually integrate into a central Hub (CLI or FastAPI).

---

## ✨ Features

- **Manual perspective correction** — Click the four corners of the card using an OpenCV window. The transformation straightens the image.
- **Real-world sizing** — Output is resized to the exact ID-1 dimensions (1011 × 638 px at 300 DPI).
- **Smart sheet composition** — Places the front and back side-by-side (or stacked) on a US Letter sheet, with equal margins.
- **Preview with swap** — Before generating the PDF, you can press `S` to swap the front and back cards if they are in the wrong order.
- **Edge-case handling** — If a card is too large for the sheet (even when rotated), the tool saves the corrected images as standalone JPGs instead of failing.
- **Responsive UI** *(currently OpenCV-based, see limitations)* — The window scales to fit the screen, but the UI elements are not fully responsive.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Core logic | Python 3.11+ |
| Image processing | OpenCV, NumPy |
| PDF generation | Pillow |
| UI (MVP) | OpenCV HighGUI |
| Testing | pytest (500+ tests) |
| Packaging | PyInstaller |

No frontend frameworks, no build step. The entire application runs from the terminal.

---

## 🚀 How to Run (From Source)

1. Clone the repository and navigate to the folder:
   ```bash
   git clone https://github.com/JavierVizGarriDev/id-card-corrector.git
   cd id-card-corrector
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1  # Windows
   ```

3. Install the package in editable mode (including dev dependencies):
   ```bash
   pip install -e ".[dev]"
   ```

4. Prepare your input:
   Create a folder named `entrada/` in the root of the project and place 1 or 2 ID card photos (`.jpg`, `.jpeg`, `.png`) inside it. The program will create the `salida/` folder automatically.

5. Run the application:
   ```bash
   python -m id_card_corrector
   ```

6. Follow the on-screen instructions:
   - Click the four corners of the card in order (top-left, top-right, bottom-right, bottom-left).
   - Press `ENTER` to confirm.
   - If there are two images, press `S` in the preview to swap them, or `ENTER` to confirm.
   - The PDF will be saved to `salida/`.

---

## 📂 Project Structure

```text
id-card-corrector/
├── src/
│   └── id_card_corrector/
│       ├── config.py          # Physical specs (card, sheet, margins)
│       ├── geometry.py        # Perspective warp and quadrilateral validation
│       ├── io_utils.py        # Image and PDF I/O
│       ├── composer.py        # Layout logic and sheet rendering
│       ├── selector.py        # Interactive corner selection (UI)
│       ├── preview.py         # Preview with swap (UI)
│       ├── pipeline.py        # Orchestrator
│       └── cli.py             # Command-line entry point
├── tests/
├── entrada/                   # Input photos (gitignored)
├── salida/                    # Output PDFs (gitignored)
├── pyproject.toml
└── README.md
```

---

## 🧠 Design Notes

The project follows a modular, layered architecture:

- **Pure logic modules** (`geometry`, `composer`) are independent of the UI and filesystem, and are covered by unit tests.
- **I/O and orchestration** (`io_utils`, `pipeline`) connect the pure logic to the real world.
- **UI modules** (`selector`, `preview`) are isolated and will be replaced in a future refactor.

This separation makes the core testable (500+ tests) and allows the UI to be swapped without rewriting the business logic.

---

## ⚠️ Current Limitations

- **OpenCV UI is not responsive** — Text sizes, banner heights, and point radii are fixed. On a 4K monitor, elements may look small; on a small screen, they may be too large. The window scales the image, but the UI elements do not scale dynamically.
- **No automated tests for the UI layer** — Mocking `cv2.imshow` and `cv2.waitKey` is fragile. The state machine (`selector.process_event`) is fully tested, but the OpenCV rendering loop is validated manually.
- **No drag-and-drop** — Corner selection requires clicking the four points. There is no way to adjust a point after placing it (you must press `R` to restart).
- **Single-card flow has no preview** — With one image, the PDF is generated directly, without the swap/confirm screen.
- **Margins are not user-configurable** — The master margin is a constant (`MARGIN_MM`), adjusted in code. A future UI could expose it.

---

## 🗺️ Roadmap

- **UI refactor (next milestone)** — Isolate the UI behind a `Protocol` interface. Build a web-based UI (FastAPI + HTML/JS) that is fully responsive, modern, and easy to extend. Keep the OpenCV UI as a fallback for terminal use.
- **Automatic corner detection** — Use computer vision (homography, edge detection) to suggest the card boundaries without manual clicks.
- **Support for multiple card types** — Add ONAT cards, driver's licenses, and custom sizes to the `SPECS` dictionary.
- **Batch processing** — Process multiple cards in one run (currently limited to 1 or 2 images).
- **User-configurable margins** — Expose `MARGIN_MM` in the UI.
- **Integration with a central Hub** — Connect `id-card-corrector` with other print-shop tools (e.g., `printable-photo-grid`) through a shared CLI or API.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Javier A. Vizcaino Garriga**
- GitHub: [@JavierVizGarriDev](https://github.com/JavierVizGarriDev)
- Email: [javieralejandrovizcainogarriga@gmail.com](mailto:javieralejandrovizcainogarriga@gmail.com)

---

*My fourth project. Built to automate a real workflow at a print shop.*
