import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: {
    port: 5173,
    host: true,
    proxy: {
      // Gọi /api/... từ frontend sẽ được chuyển tới backend, tránh vấn đề CORS khi dev
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
