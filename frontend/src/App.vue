<template>
  <div class="app-container">
    <header class="top-bar">
      <p>Estado actual: {{ currentState }}</p>
    </header>

    <main class="canvas-area">
      <!-- Envolvemos la imagen para poder posicionar los puntos encima -->
      <div class="image-wrapper">
        <img 
          :src="imageUrl" 
          alt="Carnet de identidad" 
          class="canvas-image" 
          @click="handleImageClick" 
        />
        
        <!-- Recorremos el array de puntos con v-for -->
        <span 
          v-for="(punto, index) in puntos" 
          :key="index"
          class="punto-seleccion"
          :style="{ left: punto.x + 'px', top: punto.y + 'px' }"
        >
          {{ index + 1 }}
        </span>
      </div>
    </main>

    <footer class="bottom-bar">
      
      <!-- Controles para el Estado 1: Selección de esquinas -->
      <div v-if="currentState === 'select_corners'" class="controls">
        <button>Reiniciar (R)</button>
        <button @click="simularCancelacion">Cancelar (ESC)</button>
        <button @click="simularConfirmacion">Confirmar (ENTER)</button>
      </div>

      <!-- Controles para el Estado 2: Previsualización -->
      <div v-else-if="currentState === 'preview_sheet'" class="controls">
        <button>Intercambiar (S)</button>
        <button @click="simularCancelacion">Cancelar (ESC)</button>
        <button>Confirmar (ENTER)</button>
      </div>

    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';

// Definimos el tipo de nuestro objeto punto
interface Punto {
  x: number;
  y: number;
}

// Creamos una referencia reactiva para el estado de la UI
const currentState = ref('select_corners');

// Variable para la URL de la imagen (usamos un placeholder por ahora)
const imageUrl = ref('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI4MDAiIGhlaWdodD0iNTAwIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtc2l6ZT0iNDAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGFsaWdubWVudC1iYXNlbGluZT0ibWlkZGxlIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiIgZmlsbD0iIzMzMyI+SW1hZ2VuIGRlIHBydWViYTwvdGV4dD48L3N2Zz4=');

// Array reactivo para guardar hasta 4 puntos
const puntos = ref<Punto[]>([]);

function simularConfirmacion() {
  currentState.value = 'preview_sheet';
}

function simularCancelacion() {
  currentState.value = 'select_corners';
}

// Esta función se ejecutará cada vez que se pulse una tecla

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') {
    simularConfirmacion();
  } else if (event.key === 'Escape') {
    simularCancelacion();
  }
}

// Función que se ejecuta cada vez que se hace clic en la imagen
function handleImageClick(event: MouseEvent) {
  // Si ya tenemos 4 puntos, no hacemos nada más
  if (puntos.value.length >= 4) return;

  // Añadimos el nuevo punto con las coordenadas relativas a la imagen
  puntos.value.push({
    x: event.offsetX,
    y: event.offsetY
  });
  
  console.log('Puntos actuales:', puntos.value); // Para debug
}


// Le decimos al navegador que empiece a escuchar cuando el componente se monta
onMounted(() => {
  window.addEventListener('keydown', handleKeydown);
});

// Le decimos que deje de escuchar cuando el componente se destruye
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown);
});
</script>


<style scoped>
/* Estilos para el contenedor de los controles */
.controls {
  display: flex;
  gap: 15px; /* Separación entre botones */
}

/* Estilos para los botones */
button {
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 600;
  color: #333;
  background-color: #e0e0e0;
  border: 1px solid #ccc;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s; /* Suaviza el cambio de color */
}

/* Efecto al pasar el ratón por encima */
button:hover {
  background-color: #d0d0d0;
}

.canvas-image {
  width: 100%;
  height: 100%;
  object-fit: contain; /* La magia: escala proporcionalmente sin recortar */
  /* Un borde temporal para que veas dónde empieza y acaba la imagen */
  border: 2px dashed #999; 
}

/* El contenedor de la imagen debe ser relativo para que los puntos se posicionen respecto a él */
.image-wrapper {
  position: relative;
  display: inline-flex;
  width: 100%;
  height: 100%;
}

/* El punto verde */
.punto-seleccion {
  position: absolute;
  width: 24px;
  height: 24px;
  background-color: #4CAF50; /* Verde */
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 12px;
  /* Transformamos el punto para que el centro del círculo coincida exactamente con el clic */
  transform: translate(-50%, -50%);
  pointer-events: none; /* Evita que el punto bloquee el siguiente clic */
  box-shadow: 0 2px 4px rgba(0,0,0,0.3);
}
</style>
