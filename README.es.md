# id-card-corrector

Una herramienta modular para corregir la perspectiva de fotos de carnets de identidad y generar PDFs listos para imprimir.

> [English](README.md) · Español

---

## Resumen

En la imprenta donde trabajo, los clientes suelen enviar fotos de sus carnets de identidad para hacer copias o imprimirlas. Estas fotos casi siempre están tomadas en ángulo, mal encuadradas y necesitan ser redimensionadas a sus dimensiones físicas reales. El proceso manual en Photoshop (corregir la perspectiva, redimensionar, repetir para el reverso y acomodar ambas caras en una hoja carta) tomaba unos 5 minutos por documento.

**id-card-corrector** automatiza este flujo de trabajo. Abre una ventana donde haces clic en las cuatro esquinas del carnet, aplica una transformación de perspectiva, redimensiona el resultado al estándar exacto ID-1 (85.6 × 53.98 mm a 300 DPI) y compone ambas caras (anverso y reverso) en una sola hoja tamaño carta. La salida final es un PDF listo para imprimir.

Construido como la primera herramienta dentro de una visión a largo plazo de utilidades modulares para imprenta que eventualmente se integrarán en un Hub central (CLI o FastAPI).

---

## ✨ Características

- **Corrección manual de perspectiva** — Haz clic en las cuatro esquinas del carnet usando una ventana de OpenCV. La transformación endereza la imagen.
- **Tamaño real** — La salida se redimensiona a las dimensiones exactas del estándar ID-1 (1011 × 638 px a 300 DPI).
- **Composición inteligente de la hoja** — Coloca el anverso y el reverso lado a lado (o apilados) en una hoja carta de EE. UU., con márgenes iguales.
- **Previsualización con swap** — Antes de generar el PDF, puedes pulsar `S` para intercambiar el anverso y el reverso si están en el orden incorrecto.
- **Manejo de casos límite** — Si un carnet es demasiado grande para la hoja (incluso rotado), la herramienta guarda las imágenes corregidas como JPGs sueltos en lugar de fallar.
- **UI adaptable** *(actualmente basada en OpenCV, ver limitaciones)* — La ventana se escala para adaptarse a la pantalla, pero los elementos de la UI no son totalmente responsivos.

---

## 🛠️ Tecnologías

| Capa | Tecnología |
|---|---|
| Lógica central | Python 3.11+ |
| Procesamiento de imágenes | OpenCV, NumPy |
| Generación de PDF | Pillow |
| UI (MVP) | OpenCV HighGUI |
| Testing | pytest (más de 500 tests) |
| Empaquetado | PyInstaller |

Sin frameworks de frontend, sin pasos de compilación. Toda la aplicación se ejecuta desde la terminal.

---

## 🚀 Cómo ejecutar (Desde el código fuente)

1. Clona el repositorio y accede a la carpeta:
   ```bash
   git clone https://github.com/JavierVizGarriDev/id-card-corrector.git
   cd id-card-corrector
   ```

2. Crea y activa un entorno virtual:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1  # Windows
   ```

3. Instala el paquete en modo editable (incluyendo dependencias de desarrollo):
   ```bash
   pip install -e ".[dev]"
   ```

4. Prepara tu entrada:
   Crea una carpeta llamada `entrada/` en la raíz del proyecto y coloca dentro 1 o 2 fotos de carnets (`.jpg`, `.jpeg`, `.png`). El programa creará la carpeta `salida/` automáticamente.

5. Ejecuta la aplicación:
   ```bash
   python -m id_card_corrector
   ```

6. Sigue las instrucciones en pantalla:
   - Haz clic en las cuatro esquinas del carnet en orden (sup. izq., sup. der., inf. der., inf. izq.).
   - Pulsa `ENTER` para confirmar.
   - Si hay dos imágenes, pulsa `S` en la previsualización para intercambiarlas, o `ENTER` para confirmar.
   - El PDF se guardará en `salida/`.

---

## 📂 Estructura del proyecto

```text
id-card-corrector/
├── src/
│   └── id_card_corrector/
│       ├── config.py          # Especificaciones físicas (carnet, hoja, márgenes)
│       ├── geometry.py        # Transformación de perspectiva y validación geométrica
│       ├── io_utils.py        # Entrada/Salida de imágenes y PDFs
│       ├── composer.py        # Lógica de layout y renderizado de la hoja
│       ├── selector.py        # Selección interactiva de esquinas (UI)
│       ├── preview.py         # Previsualización con swap (UI)
│       ├── pipeline.py        # Orquestador
│       └── cli.py             # Punto de entrada por línea de comandos
├── tests/
├── entrada/                   # Fotos de entrada (ignorado por git)
├── salida/                    # PDFs generados (ignorado por git)
├── pyproject.toml
└── README.md
```

---

## 🧠 Notas de diseño

El proyecto sigue una arquitectura modular y por capas:

- Los **módulos de lógica pura** (`geometry`, `composer`) son independientes de la UI y del sistema de archivos, y están cubiertos por tests unitarios.
- La **entrada/salida y la orquestación** (`io_utils`, `pipeline`) conectan la lógica pura con el mundo real.
- Los **módulos de UI** (`selector`, `preview`) están aislados y serán reemplazados en un futuro refactor.

Esta separación hace que el núcleo sea testeable (más de 500 tests) y permite cambiar la UI sin reescribir la lógica de negocio.

---

## ⚠️ Limitaciones actuales

- **La UI de OpenCV no es responsiva** — Los tamaños de texto, las alturas de los banners y los radios de los puntos son fijos. En un monitor 4K, los elementos pueden verse pequeños; en una pantalla pequeña, pueden verse demasiado grandes. La ventana escala la imagen, pero los elementos de la UI no escalan dinámicamente.
- **Sin tests automatizados para la capa de UI** — Mockear `cv2.imshow` y `cv2.waitKey` es frágil. La máquina de estados (`selector.process_event`) está completamente testeada, pero el bucle de renderizado de OpenCV se valida manualmente.
- **Sin arrastrar y soltar** — La selección de esquinas requiere hacer clic en los cuatro puntos. No hay forma de ajustar un punto después de colocarlo (debes pulsar `R` para reiniciar).
- **El flujo de una sola tarjeta no tiene previsualización** — Con una sola imagen, el PDF se genera directamente, sin la pantalla de intercambio/confirmación.
- **Los márgenes no son configurables por el usuario** — El margen maestro es una constante (`MARGIN_MM`), ajustada en el código. Una futura UI podría exponerlo.

---

## 🗺️ Hoja de ruta (Roadmap)

- **Refactor de la UI (siguiente hito)** — Aislar la UI detrás de una interfaz `Protocol`. Construir una UI basada en web (FastAPI + HTML/JS) que sea totalmente responsiva, moderna y fácil de extender. Mantener la UI de OpenCV como respaldo para uso en terminal.
- **Detección automática de esquinas** — Usar visión por computadora (homografía, detección de bordes) para sugerir los límites del carnet sin clics manuales.
- **Soporte para múltiples tipos de carnet** — Añadir carnets de ONAT, licencias de conducir y tamaños personalizados al diccionario `SPECS`.
- **Procesamiento por lotes** — Procesar múltiples carnets en una sola ejecución (actualmente limitado a 1 o 2 imágenes).
- **Márgenes configurables por el usuario** — Exponer `MARGIN_MM` en la UI.
- **Integración con un Hub central** — Conectar `id-card-corrector` con otras herramientas de imprenta (ej. `printable-photo-grid`) a través de una CLI o API compartida.

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT — consulta el archivo [LICENSE](LICENSE) para más detalles.

---

## 👤 Autor

**Javier A. Vizcaino Garriga**
- GitHub: [@JavierVizGarriDev](https://github.com/JavierVizGarriDev)
- Email: [javieralejandrovizcainogarriga@gmail.com](mailto:javieralejandrovizcainogarriga@gmail.com)

---

*Mi cuarto proyecto. Creado para automatizar un flujo de trabajo real en una imprenta.*
