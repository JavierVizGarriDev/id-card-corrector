# id-card-corrector

A modular tool to correct perspective from ID card photos and generate print-ready PDFs, featuring a modern Web UI and a Standalone Executable.

> English · [Versión en español](README.es.md)

---

## Overview

At the print shop where I work, customers often send photos of their ID cards to be printed. These photos are almost always taken at an angle, poorly framed, and need to be resized to their real physical dimensions. The manual process in Photoshop (correcting perspective, resizing, repeating for the back side, and arranging both on a Letter sheet) took about 5 minutes per document.

**id-card-corrector** automates this workflow. It provides a sleek, responsive Web UI where you click the four corners of the card. The backend applies a perspective transformation, resizes the result to the exact ID-1 standard (85.6 × 53.98 mm at 300 DPI), and composes both sides (front and back) onto a single Letter-size sheet. The final output is a print-ready PDF.

Built with a heavily tested Python core and a decoupled architecture, this is the first tool in a long-term vision of modular print-shop utilities that will eventually integrate into a central Hub.

---

## ✨ Features

- **Modern Web UI** — Built with Vue 3 and TypeScript. Fully responsive, zero-scroll layout, and blazing fast.
- **Manual perspective correction** — Intuitive corner selection with real-time visual feedback (green points).
- **Real-world sizing** — Output is resized to the exact ID-1 dimensions (1011 × 638 px at 300 DPI).
- **Smart sheet composition** — Places the front and back side-by-side (or stacked) on a US Letter sheet, with equal margins.
- **Preview with swap** — Before generating the PDF, you can press `S` or click a button to swap the front and back cards if they are in the wrong order.
- **Keyboard Shortcuts** — Full keyboard support (`ENTER`, `ESC`, `R`, `S`) for a faster workflow.
- **Standalone Launcher** — Includes a PyInstaller executable that boots the server and opens your browser with a simple double-click (no Python or Node.js required).
- **Edge-case handling** — If a card is too large for the sheet, the tool saves the corrected images as standalone JPGs instead of failing.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Core logic | Python 3.11+ |
| Image processing | OpenCV, NumPy |
| PDF generation | Pillow |
| Backend API | FastAPI, Uvicorn |
| Frontend UI | Vue 3, Vite, TypeScript |
| Architecture | Hexagonal (Ports and Adapters) |
| Testing | pytest (520+ tests for the core logic) |
| Packaging | PyInstaller |

---

## 🚀 How to Run

### Option 1: Standalone Executable (Windows)
1. Go to the [Releases](https://github.com/JavierVizGarriDev/id-card-corrector/releases) page and download `IDCardCorrector.exe`.
2. Create a folder named `entrada/` next to the `.exe` and place your photos inside (1 or 2 images per ID card).
3. Double-click the `.exe`. The server will start, and your default browser will open automatically.
4. The output PDF will be saved in the `salida/` folder.

### Option 2: From Source (Development)
1. Clone the repository and navigate to the folder:
   ```bash
   git clone https://github.com/JavierVizGarriDev/id-card-corrector.git
   cd id-card-corrector
   ```
2. Set up the Python backend:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1  # Windows
   pip install -e ".[dev]"
   ```
3. Set up the Vue frontend:
   ```bash
   cd frontend
   npm install
   cd ..
   ```
4. Prepare your input: Create a folder named `entrada/` in the root and place your ID photos there.
5. Run the application (this automatically starts the backend and Vite):
   ```bash
   python -m id_card_corrector --ui web
   ```

*(Note: You can still use the legacy OpenCV UI by running `python -m id_card_corrector --ui opencv`)*

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
│       ├── pipeline.py        # Orchestrator
│       ├── cli.py             # Command-line entry point
│       └── ui/                # UI Adapters
│           ├── interface.py   # Protocol definition (UserInterface)
│           ├── opencv/        # Legacy OpenCV UI
│           └── web/           # FastAPI Web Server & Adapter
├── frontend/                  # Vue 3 + TypeScript application
├── tests/                     # 520+ unit tests
├── launcher.py                # Entry point for PyInstaller
├── entrada/                   # Input photos (gitignored)
├── salida/                    # Output PDFs (gitignored)
└── pyproject.toml
```

---

## 🧠 Design Notes

The project follows a **Hexagonal Architecture (Ports and Adapters)**:
- **Pure logic modules** (`geometry`, `composer`) are completely independent of the UI and filesystem.
- **The Pipeline** (`pipeline.py`) orchestrates the process and communicates exclusively through the `UserInterface` protocol.
- **UI Adapters** (`opencv` and `web`) implement this protocol. The core logic doesn't know (or care) if the user is clicking on an OpenCV window or a Vue.js component in a browser. This is the **"Dumb UI" principle**: all heavy lifting happens in Python.

This separation makes the core highly testable (520+ passing tests) and allows swapping UIs without rewriting business logic.

---

## ⚠️ Current Limitations

- **No drag-and-drop for corners** — Corner selection requires clicking the four points. There is no way to adjust a point after placing it (you must press `R` to restart).
- **Single-card flow has no preview** — With one image, the PDF is generated directly, without the swap/confirm screen.
- **Margins are not user-configurable** — The master margin is a constant (`MARGIN_MM`), adjusted in code.

---

## 🗺️ Roadmap

- **Visual PDF Editor** — Allow users to manually adjust the composed PDF before printing.
- **Automatic corner detection** — Use computer vision to suggest the card boundaries without manual clicks.
- **Support for multiple card types** — Add ONAT cards, driver's licenses, and custom sizes.
- **Batch processing** — Process multiple cards in one run.
- **Integration with a central Hub** — Connect with other print-shop tools through a shared CLI or API.

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