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

// Simular el estado inicial
instructionBar.textContent = "Haz clic en las 4 esquinas del carnet (Sup. Izq, Sup. Der, Inf. Der, Inf. Izq)";
draw();