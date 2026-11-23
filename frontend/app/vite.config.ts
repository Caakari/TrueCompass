import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    // 5180, e não 5173: o front anterior (frontend/web) continua podendo rodar ao lado.
    port: 5180,
    // Em desenvolvimento o app chama /api/... e o Vite encaminha ao backend,
    // inclusive o WebSocket. Sem CORS e sem URL absoluta no código.
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
