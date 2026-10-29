<template>
  <div class="app-container">
    <header class="top-bar">
      <p>Estado actual: {{ currentState }}</p>
    </header>

    <main class="canvas-area">
      <p>Área del canvas</p>
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

// Creamos una referencia reactiva para el estado de la UI
const currentState = ref('select_corners');

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
</style>
