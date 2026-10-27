const canvas = document.getElementById('main-canvas');
const ctx = canvas.getContext('2d');
const instructionBar = document.getElementById('instruction-bar');
const controlsBar = document.querySelector('.controls-bar');

let currentPoints = [];
let currentTask = 'idle';
let currentImageVersion = -1;
let cachedImageBase64 = "";

// 1. Enviar acciones al backend
async function sendAction(actionName, data = {}) {
    await fetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: actionName, ...data })
    });
}

// 2. Polling para detectar cambios en el estado
async function pollState() {
    try {
        const response = await fetch('/api/state');
        const state = await response.json();
        
        // Solo descargar la imagen si la versión cambió
        if (state.image_version !== currentImageVersion) {
            currentImageVersion = state.image_version;
            if (state.image_version > 0) {
                const imgRes = await fetch('/api/image');
                const imgData = await imgRes.json();
                cachedImageBase64 = imgData.image_b64;
            }
        }

        // Actualizar UI solo si la tarea cambió
        if (state.task !== currentTask) {
            currentTask = state.task;
            updateUIForTask(state);
        }
    } catch (error) {
        console.error("Error de conexión:", error);
    }
    setTimeout(pollState, 300);
}

// 3. Actualizar la pantalla según lo que pida Python
function updateUIForTask(state) {
    controlsBar.innerHTML = ''; // Limpiar botones anteriores
    instructionBar.textContent = state.prompt || "Cargando...";
    currentPoints = []; // Reiniciar puntos en cada cambio de tarea

    if (state.task === 'idle') {
        canvas.style.display = 'none';
        return;
    }

    canvas.style.display = 'block';
    
    // Dibujar la imagen base
    if (cachedImageBase64) {
        const img = new Image();
        img.onload = () => {
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);
        };
        img.src = `data:image/png;base64,${cachedImageBase64}`;
    }

    // Crear botones según la tarea
    if (state.task === 'select_corners') {
        controlsBar.appendChild(createButton('Reiniciar (R)', 'btn-secondary', () => {
            currentPoints = [];
            drawPoints();
        }));
        controlsBar.appendChild(createButton('Confirmar (ENTER)', 'btn-primary', () => {
            if (currentPoints.length === 4) {
                sendAction('corners', { corners: currentPoints });
            } else {
                alert("Debes seleccionar exactamente 4 puntos.");
            }
        }));
        
    } else if (state.task === 'preview_sheet') {
        controlsBar.appendChild(createButton('Intercambiar (S)', 'btn-secondary', () => sendAction('swap')));
        controlsBar.appendChild(createButton('Cancelar (ESC)', 'btn-danger', () => sendAction('cancel')));
        controlsBar.appendChild(createButton('Confirmar (ENTER)', 'btn-primary', () => sendAction('confirm')));

    } else if (state.task === 'show_issues' || state.task === 'show_error') {
        canvas.style.display = 'none'; // Ocultar imagen en errores
        if (state.task === 'show_issues') {
            controlsBar.appendChild(createButton('Volver a seleccionar', 'btn-secondary', () => sendAction('restart')));
            controlsBar.appendChild(createButton('Continuar de todos modos', 'btn-primary', () => sendAction('confirm')));
        } else {
            controlsBar.appendChild(createButton('Entendido', 'btn-primary', () => sendAction('confirm')));
        }
    }
}

function createButton(text, className, onClick) {
    const btn = document.createElement('button');
    btn.className = `btn ${className}`;
    btn.textContent = text;
    btn.onclick = onClick;
    return btn;
}

function drawPoints() {
    if (!cachedImageBase64) return;
    const img = new Image();
    img.onload = () => {
        ctx.drawImage(img, 0, 0);
        currentPoints.forEach((p, index) => {
            ctx.beginPath();
            ctx.arc(p[0], p[1], 8, 0, Math.PI * 2);
            ctx.fillStyle = '#00ff00';
            ctx.fill();
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 2;
            ctx.stroke();

            ctx.fillStyle = '#ffffff';
            ctx.font = '24px sans-serif';
            ctx.fillText(index + 1, p[0] + 15, p[1] - 10);
        });
    };
    img.src = `data:image/png;base64,${cachedImageBase64}`;
}

// Capturar clics en el canvas
canvas.addEventListener('mousedown', (e) => {
    if (currentTask !== 'select_corners' || currentPoints.length >= 4) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    
    currentPoints.push([(e.clientX - rect.left) * scaleX, (e.clientY - rect.top) * scaleY]);
    drawPoints();
});

// Atajos de teclado
window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        if (currentTask === 'select_corners') { currentPoints = []; drawPoints(); }
    } else if (e.key === 'Enter') {
        e.preventDefault();
        const btns = controlsBar.querySelectorAll('.btn-primary');
        if (btns.length > 0) btns[0].click();
    } else if (e.key === 's' || e.key === 'S') {
        e.preventDefault();
        if (currentTask === 'preview_sheet') {
            const btns = controlsBar.querySelectorAll('.btn-secondary');
            if (btns.length > 0) btns[0].click();
        }
    } else if (e.key === 'Escape') {
        e.preventDefault();
        if (currentTask === 'preview_sheet') {
            const btns = controlsBar.querySelectorAll('.btn-danger');
            if (btns.length > 0) btns[0].click();
        }
    }
});

// Iniciar ciclo
pollState();