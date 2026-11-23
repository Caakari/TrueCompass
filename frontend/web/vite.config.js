import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Em desenvolvimento o front chama /api/... e o Vite encaminha ao backend.
    // Assim não há CORS nem URL absoluta espalhada pelo código.
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND || 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
        rewrite: (caminho) => caminho.replace(/^\/api/, ''),
      },
    },
  },
})
