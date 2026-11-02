<template>
  <div class="app-container">
    <header class="top-bar">
      <p v-if="isBackendDisconnected" style="color: red; font-weight: bold;">
        Proceso finalizado o cancelado. Puedes cerrar esta pestaña.
      </p>
      <p v-else>Estado actual: {{ currentState }}</p>
    </header>

    <main 
      class="canvas-area" 
      :class="{ 'canvas-disabled': isBackendDisconnected }"
    >
      <!-- Envolvemos la imagen para poder posicionar los puntos encima -->
      <div class="image-wrapper">
        <img 
          :src="imageUrl" 
          alt="Carnet de identidad" 
          class="canvas-image" 
          @click="handleImageClick" 
          @load="handleImageLoad"
        />
        
        <!-- Recorremos el array de puntos con v-for -->
        <template v-if="currentState === 'select_corners'">
          <span 
            v-for="(punto, index) in puntos" 
            :key="index"
            class="punto-seleccion"
            :style="{ left: punto.xPantalla + 'px', top: punto.yPantalla + 'px' }"
          >
            {{ index + 1 }}
          </span>
        </template>
            <!-- Modal de Cancelación Transversal -->
        <div v-if="showCancelModal" class="modal-overlay">
          <div class="modal-content">
            <h2>¿Cancelar el proceso?</h2>
            <p>Se abortará el procesamiento actual y se perderán los datos.</p>
            <div class="modal-controls">
              <button @click="cerrarModalCancelacion">No, volver (ENTER)</button>
              <button @click="confirmarCancelacionTotal">Sí, cancelar todo (ESC)</button>
            </div>
          </div>
        </div>
      </div>
    </main>

    <footer class="bottom-bar">
      
      <!-- Controles para el Estado 1: Selección de esquinas -->
      <div v-if="currentState === 'select_corners'" class="controls">
        <button @click="reiniciarSeleccion" :disabled="isBackendDisconnected">Reiniciar (R)</button>
        <button @click="abrirModalCancelacion" :disabled="isBackendDisconnected">Cancelar (ESC)</button>
        <button 
          @click="enviarAccion('confirm', puntos)" 
          :disabled="puntos.length !== 4 || isBackendDisconnected"
        >
          Confirmar (ENTER)
        </button>
      </div>

      <!-- Controles para el Estado 2: Previsualización -->
      <div v-else-if="currentState === 'preview_sheet'" class="controls">
        <button :disabled="isBackendDisconnected">Intercambiar (S)</button>
        <button @click="abrirModalCancelacion" :disabled="isBackendDisconnected">Cancelar (ESC)</button>
        <button :disabled="isBackendDisconnected">Confirmar (ENTER)</button>
      </div>

    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';

// Definimos el tipo de nuestro objeto punto
interface Punto {
  xPantalla: number;
  yPantalla: number;
  xReal: number;
  yReal: number;
}

let pollingInterval: ReturnType<typeof setInterval> | null = null;

// Variables para controlar si el backend sigue vivo
let pollingFailures = 0;

const isBackendDisconnected = ref(false);

// Creamos una referencia reactiva para el estado de la UI
const currentState = ref('select_corners');

// Variable para rastrear la versión de la imagen que estamos mostrando
const currentImageVersion = ref(0)

// Variable para la URL de la imagen (usamos un placeholder por ahora)
const imageUrl = ref('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI4MDAiIGhlaWdodD0iNTAwIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtc2l6ZT0iNDAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGFsaWdubWVudC1iYXNlbGluZT0ibWlkZGxlIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiIgZmlsbD0iIzMzMyI+SW1hZ2VuIGRlIHBydWViYTwvdGV4dD48L3N2Zz4=');

// Array reactivo para guardar hasta 4 puntos
const puntos = ref<Punto[]>([]);

// Variables para guardar el tamaño real de la imagen
const dimensionesReales = ref({ ancho: 0, alto: 0 });

// Variable para controlar la visibilidad del modal de cancelación
const showCancelModal = ref(false);

// Abre el modal
function abrirModalCancelacion() {
  showCancelModal.value = true;
}

// Cierra el modal y vuelve al trabajo
function cerrarModalCancelacion() {
  showCancelModal.value = false;
}

async function confirmarCancelacionTotal() {
  showCancelModal.value = false;
  await enviarAccion('cancel');
}

// Función para pedir la imagen real al backend
async function fetchImage() {
  try {
    const response = await fetch('/api/image');
    const data = await response.json();
    
    if (data.image_b64) {
      // Añadimos el prefijo para que el navegador sepa que es un PNG en Base64
      imageUrl.value = `data:image/png;base64,${data.image_b64}`;
      
      //Si llega una imagen nueva, limpiamos los puntos anteriores
      puntos.value = [];
    }
  } catch (error) {
    console.error('Error al descargar la imagen:', error);
  }
}

async function enviarAccion(action: string, corners?: any[]) {
  try {
    const payload: any = { action: action };
    
    if (corners) {
      payload.corners = corners.map(p => [p.xReal, p.yReal]);
    }

    const response = await fetch('/api/action', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error('Error al enviar la acción');
    }

    // ¡NUEVO! Si la acción fue exitosa, limpiamos los puntos de la pantalla
    // Esto cubre el caso de las dos imágenes y evita clics accidentales.
    puntos.value = []; 

  } catch (error) {
    console.error('Error enviando acción:', error);
  }
}

// Función que se ejecuta cuando la imagen termina de cargar
function handleImageLoad(event: Event) {
  const img = event.target as HTMLImageElement;
  dimensionesReales.value = {
    ancho: img.naturalWidth,
    alto: img.naturalHeight
  };
}

function reiniciarSeleccion() {
  // Vaciamos el array asignándole un array vacío
  puntos.value = [];
}

async function checkState() {
  // Si ya sabemos que está desconectado, no hacemos nada
  if (isBackendDisconnected.value) return;

  try {
    const response = await fetch('/api/state');
    if (!response.ok) throw new Error('Error en la red');
    
    const data = await response.json();
    
    // Si llegamos aquí, el backend está vivo. Reiniciamos el contador.
    pollingFailures = 0;

    // Sincronizamos el estado (task)
    if (data.task && data.task !== currentState.value) {
      currentState.value = data.task;
    }

    // Sincronizamos la imagen
    if (data.image_version && data.image_version !== currentImageVersion.value) {
      currentImageVersion.value = data.image_version;
      await fetchImage();
    }

  } catch (error) {
    pollingFailures++;
    console.warn(`Fallo de conexión con el backend (${pollingFailures}/3)`);
    
    // Si falla 3 veces seguidas, asumimos que el backend ha muerto
    if (pollingFailures >= 3) {
      isBackendDisconnected.value = true;
      
      // Detenemos el polling para siempre
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    }
  }
}

// Esta función se ejecutará cada vez que se pulse una tecla
function handleKeydown(event: KeyboardEvent) {
    // Si el backend está muerto, ignoramos cualquier atajo de teclado
  if (isBackendDisconnected.value) return;
  
  if (event.key === 'Enter') {
    // Solo enviamos si hay 4 puntos
    if (puntos.value.length === 4) {
      enviarAccion('confirm', puntos.value); 
    }
  } else if (event.key === 'Escape') {
    abrirModalCancelacion();
  } else if (event.key.toLowerCase() === 'r') {
    reiniciarSeleccion();
  }
}

// Función que se ejecuta cada vez que se hace clic en la imagen
function handleImageClick(event: MouseEvent) {
  if (puntos.value.length >= 4) return;

  const img = event.target as HTMLImageElement;
  
  // 1. Tamaño en pantalla
  const anchoPantalla = img.clientWidth;
  const altoPantalla = img.clientHeight;

  // 2. Tamaño real
  const anchoReal = dimensionesReales.value.ancho;
  const altoReal = dimensionesReales.value.alto;

  // 3. Regla de tres
  const ratioX = anchoReal / anchoPantalla;
  const ratioY = altoReal / altoPantalla;

  // 4. Coordenadas reales
  const xReal = event.offsetX * ratioX;
  const yReal = event.offsetY * ratioY;

  // 5. Guardamos ambas
  puntos.value.push({
    xPantalla: event.offsetX,
    yPantalla: event.offsetY,
    xReal: Math.round(xReal),
    yReal: Math.round(yReal)
  });
}

// Le decimos al navegador que empiece a escuchar cuando el componente se monta
onMounted(() => {
  window.addEventListener('keydown', handleKeydown);
  // Arrancamos el polling cada 300ms
  pollingInterval = setInterval(checkState, 300);
  checkState(); // Hacemos una primera llamada inmediata
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown);
  // Limpiamos el temporizador al salir para no dejar procesos en segundo plano
  if (pollingInterval) {
    clearInterval(pollingInterval);
  }
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

/* Estilo cuando el botón está deshabilitado */
button:disabled {
  background-color: #f5f5f5;
  color: #999;
  border-color: #ddd;
  cursor: not-allowed; /* El cursor muestra un símbolo de prohibido */
  opacity: 0.7;
}

/* Evitamos que el hover funcione si está deshabilitado */
button:hover:not(:disabled) {
  background-color: #d0d0d0;
}

.canvas-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain; 
  border: 2px dashed #999; 
  cursor: crosshair; /* Añadimos la cruz del ratón */
}

/* El contenedor de la imagen debe ser relativo para que los puntos se posicionen respecto a él */
.image-wrapper {
  position: relative;
  display: flex;
  max-width: 100%;
  max-height: 100%;
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

/* El fondo oscuro que cubre todo */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(0, 0, 0, 0.5); /* Negro semitransparente */
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000; /* Asegura que esté por encima de todo */
}

/* La caja del modal */
.modal-content {
  background-color: white;
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  text-align: center;
  max-width: 400px;
}

.modal-content h2 {
  margin-bottom: 15px;
  color: #333;
}

.modal-content p {
  margin-bottom: 25px;
  color: #666;
}

.modal-controls {
  display: flex;
  gap: 15px;
  justify-content: center;
}

/* Estilos cuando el backend se ha desconectado */
.canvas-disabled {
  opacity: 0.3; /* Hace que se vea semitransparente */
  filter: grayscale(100%); /* Pone la imagen en blanco y negro */
  pointer-events: none; /* Bloquea los clics del ratón en toda esta zona */
  transition: all 0.5s ease; /* Hace que el cambio sea suave, no un golpe brusco */
}
</style>
