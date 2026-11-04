import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000', // El puerto donde corre tu FastAPI
        changeOrigin: true,
      }
    }
  },
  // --- NUEVO: Configuración de compilación para producción ---
  build: {
    // Evita que Vite genere una carpeta 'dist' que choque con la que crea PyInstaller
    outDir: 'frontend_dist', 
  }
})