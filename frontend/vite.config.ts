import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  build: {
    // Usamos import.meta.dirname en lugar de __dirname
    outDir: path.resolve(import.meta.dirname, '../src/id_card_corrector/ui/web/static'),
    emptyOutDir: true,
  }
})