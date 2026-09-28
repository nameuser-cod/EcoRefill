import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  css: { devSourcemap: true },
  ...(mode === 'kiosk' ? {
    build: { outDir: 'ecorefill-pi/kiosk-dist', rollupOptions: { input: 'kiosk.html' } },
  } : {}),
}))
