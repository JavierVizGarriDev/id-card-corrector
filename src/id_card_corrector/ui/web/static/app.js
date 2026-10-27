const canvas = document.getElementById('main-canvas');
const ctx = canvas.getContext('2d');
const instructionBar = document.getElementById('instruction-bar');

let points = [];

// Configuración visual del canvas
canvas.width = 1000;
canvas.height = 700;

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Dibujar un fondo temporal para simular la imagen
    ctx.fillStyle = '#333';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#aaa';
    ctx.font = '30px sans-serif';
    ctx.fillText("Imagen cargada aquí", 350, 350);

    // Dibujar los puntos guardados
    points.forEach((p, index) => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 8, 0, Math.PI * 2);
        ctx.fillStyle = '#00ff00';
        ctx.fill();
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Número del punto
        ctx.fillStyle = '#ffffff';
        ctx.font = '24px sans-serif';
        ctx.fillText(index + 1, p.x + 15, p.y - 10);
    });
}

canvas.addEventListener('mousedown', (e) => {
    if (points.length >= 4) return; // Límite temporal

    const rect = canvas.getBoundingClientRect();
    // Escalar coordenadas del DOM al tamaño real del canvas
    const x = (e.clientX - rect.left) * (canvas.width / rect.width);
    const y = (e.clientY - rect.top) * (canvas.height / rect.height);

    points.push({ x, y });
    draw();
});

// Habilitar el botón de Confirmar (ya que estamos en modo prueba)
document.getElementById('btn-confirm').disabled = false;

// El evento del botón Confirmar
document.getElementById('btn-confirm').addEventListener('click', async () => {
    if (points.length !== 4) {
        alert("Necesitas hacer exactamente 4 clics.");
        return;
    }

    // Formatear los puntos como [[x, y], [x, y], ...]
    const coords = points.map(p => [p.x, p.y]);

    console.log("Enviando coordenadas a Python:", coords);

    // Enviar a FastAPI
    await fetch('/api/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ corners: coords })
    });
});

// El evento del botón Reiniciar
document.getElementById('btn-restart').disabled = false;
document.getElementById('btn-restart').addEventListener('click', () => {
    points = [];
    draw();
});

// --- Atajos de teclado ---
window.addEventListener('keydown', (e) => {
    // Si estamos escribiendo en un input (no aplica aquí, pero es buena práctica)
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    if (e.key === 'r' || e.key === 'R') {
        e.preventDefault(); // Evita que el navegador haga algo por defecto
        points = [];
        draw();
    } else if (e.key === 'Enter') {
        e.preventDefault();
        const confirmBtn = document.getElementById('btn-confirm');
        if (!confirmBtn.disabled) {
            confirmBtn.click(); // Simula el clic en el botón
        }
    }
});

// Simular el estado inicial
instructionBar.textContent = "Haz clic en las 4 esquinas del carnet (Sup. Izq, Sup. Der, Inf. Der, Inf. Izq)";
draw();