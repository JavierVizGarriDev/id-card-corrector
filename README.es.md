# id-card-corrector

Una herramienta modular para corregir la perspectiva de fotos de carnets de identidad y generar PDFs listos para imprimir, con una moderna interfaz web (Web UI) y un ejecutable autónomo (Standalone Executable).

> [English](README.md) · Versión en español

---

## Resumen

En la imprenta donde trabajo, los clientes suelen enviar fotos de sus carnets de identidad para imprimirlos. Estas fotos casi siempre están tomadas en ángulo, mal encuadradas y necesitan ser redimensionadas a sus dimensiones físicas reales. El proceso manual en Photoshop (corregir la perspectiva, redimensionar, repetir para el reverso y montar ambos en una hoja Carta) tomaba unos 5 minutos por documento.

**id-card-corrector** automatiza este flujo de trabajo. Proporciona una interfaz web ágil y responsiva donde haces clic en las cuatro esquinas del carnet. El backend aplica una transformación de perspectiva, redimensiona el resultado al estándar exacto ID-1 (85.6 × 53.98 mm a 300 DPI) y compone ambos lados (anverso y reverso) en una sola hoja tamaño Carta. El resultado final es un PDF listo para imprimir.

Construido con un núcleo en Python fuertemente testeado y una arquitectura desacoplada, esta es la primera herramienta de una visión a largo plazo de utilidades modulares para imprentas que eventualmente se integrarán en un Hub central.

---

## ✨ Características

- **Interfaz Web Moderna** — Construida con Vue 3 y TypeScript. Totalmente responsiva, con diseño de cero scroll (sin barras de desplazamiento) y muy rápida.
- **Corrección manual de perspectiva** — Selección intuitiva de esquinas con retroalimentación visual en tiempo real (puntos verdes).
- **Dimensiones reales** — La salida se redimensiona a las dimensiones exactas ID-1 (1011 × 638 px a 300 DPI).
- **Composición inteligente de la hoja** — Coloca el anverso y el reverso lado a lado (o apilados) en una hoja Carta, con márgenes iguales.
- **Previsualización con intercambio** — Antes de generar el PDF, puedes presionar `S` o hacer clic en un botón para intercambiar las caras frontal y trasera si están en el orden incorrecto.
- **Atajos de teclado** — Soporte completo de teclado (`ENTER`, `ESC`, `R`, `S`) para un flujo de trabajo más rápido.
- **Lanzador autónomo** — Incluye un ejecutable de PyInstaller que inicia el servidor y abre tu navegador con un simple doble clic (no requiere Python ni Node.js).
- **Manejo de casos límite** — Si un carnet es demasiado grande para la hoja, la herramienta guarda las imágenes corregidas como JPGs independientes en lugar de fallar.

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Lógica central (Core) | Python 3.11+ |
| Procesamiento de imágenes | OpenCV, NumPy |
| Generación de PDF | Pillow |
| API del Backend | FastAPI, Uvicorn |
| Interfaz Frontend | Vue 3, Vite, TypeScript |
| Arquitectura | Hexagonal (Puertos y Adaptadores) |
| Testing | pytest (más de 520 tests para la lógica central) |
| Empaquetado | PyInstaller |

---

## 🚀 Cómo ejecutar

### Opción 1: Ejecutable Autónomo (Windows)
1. Ve a la página de [Releases](https://github.com/JavierVizGarriDev/id-card-corrector/releases) y descarga `IDCardCorrector.exe`.
2. Crea una carpeta llamada `entrada/` junto al `.exe` y coloca tus fotos dentro (1 o 2 imágenes por carnet).
3. Haz doble clic en el `.exe`. El servidor se iniciará y tu navegador predeterminado se abrirá automáticamente.
4. El PDF de salida se guardará en la carpeta `salida/`.

### Opción 2: Desde el Código Fuente (Desarrollo)
1. Clona el repositorio y navega a la carpeta:
   ```bash
   git clone https://github.com/JavierVizGarriDev/id-card-corrector.git
   cd id-card-corrector
   ```
2. Configura el backend de Python:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1  # Windows
   pip install -e ".[dev]"
   ```
3. Configura el frontend de Vue:
   ```bash
   cd frontend
   npm install
   cd ..
   ```
4. Prepara tu entrada: Crea una carpeta llamada `entrada/` en la raíz y coloca tus fotos de carnet allí.
5. Ejecuta la aplicación (esto inicia automáticamente el backend y Vite):
   ```bash
   python -m id_card_corrector --ui web
   ```

*(Nota: Aún puedes usar la antigua interfaz de OpenCV ejecutando `python -m id_card_corrector --ui opencv`)*

---

## 📂 Estructura del proyecto

```text
id-card-corrector/
├── src/
│   └── id_card_corrector/
│       ├── config.py          # Especificaciones físicas (carnet, hoja, márgenes)
│       ├── geometry.py        # Transformación de perspectiva y validación
│       ├── io_utils.py        # Entrada/Salida de imágenes y PDFs
│       ├── composer.py        # Lógica de diseño y renderizado de la hoja
│       ├── pipeline.py        # Orquestador
│       ├── cli.py             # Punto de entrada de línea de comandos
│       └── ui/                # Adaptadores de UI
│           ├── interface.py   # Definición del Protocolo (UserInterface)
│           ├── opencv/        # Interfaz antigua de OpenCV
│           └── web/           # Servidor Web y Adaptador FastAPI
├── frontend/                  # Aplicación en Vue 3 + TypeScript
├── tests/                     # Más de 520 tests unitarios
├── launcher.py                # Punto de entrada para PyInstaller
├── entrada/                   # Fotos de entrada (ignorado en git)
├── salida/                    # PDFs de salida (ignorado en git)
└── pyproject.toml
```

---

## 🧠 Notas de diseño

El proyecto sigue una **Arquitectura Hexagonal (Puertos y Adaptadores)**:
- **Los módulos de lógica pura** (`geometry`, `composer`) son completamente independientes de la UI y del sistema de archivos.
- **El Pipeline** (`pipeline.py`) orquesta el proceso y se comunica exclusivamente a través del protocolo `UserInterface`.
- **Los Adaptadores de UI** (`opencv` y `web`) implementan este protocolo. A la lógica central no le importa si el usuario está haciendo clic en una ventana de OpenCV o en un componente de Vue.js en un navegador. Este es el principio de la **"UI Tonta"**: todo el trabajo pesado ocurre en Python.

Esta separación hace que el núcleo sea altamente testeable (más de 520 tests pasando) y permite intercambiar las interfaces sin reescribir la lógica de negocio.

---

## ⚠️ Limitaciones actuales

- **Sin arrastrar y soltar para las esquinas** — La selección de esquinas requiere hacer clic en los cuatro puntos. No hay forma de ajustar un punto después de colocarlo (debes presionar `R` para reiniciar).
- **El flujo de un solo carnet no tiene previsualización** — Con una sola imagen, el PDF se genera directamente, sin la pantalla de intercambio/confirmación.
- **Los márgenes no son configurables por el usuario** — El margen maestro es una constante (`MARGIN_MM`), ajustada en el código.

---

## 🗺️ Hoja de ruta (Roadmap)

- **Editor visual de PDF** — Permitir a los usuarios ajustar manualmente el PDF compuesto antes de imprimir.
- **Detección automática de esquinas** — Usar visión artificial para sugerir los límites del carnet sin necesidad de clics manuales.
- **Soporte para múltiples tipos de carnets** — Añadir carnets ONAT, licencias de conducir y tamaños personalizados.
- **Procesamiento por lotes** — Procesar múltiples carnets en una sola ejecución.
- **Integración con un Hub central** — Conectar con otras herramientas para imprentas a través de una CLI o API compartida.

---

## 📄 Licencia

Este proyecto está licenciado bajo la Licencia MIT — consulta el archivo [LICENSE](LICENSE) para más detalles.

---

## 👤 Autor

**Javier A. Vizcaino Garriga**
- GitHub: [@JavierVizGarriDev](https://github.com/JavierVizGarriDev)
- Email: [javieralejandrovizcainogarriga@gmail.com](mailto:javieralejandrovizcainogarriga@gmail.com)

---

*Mi cuarto proyecto. Construido para automatizar un flujo de trabajo real en una imprenta.*