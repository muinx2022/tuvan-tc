import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    // Trình duyệt gọi /api/v1/... trên cùng origin 5173 → Vite chuyển tiếp sang Django :8080
    // (tránh lệ thuộc CORS; backend vẫn thấy mọi request trong CLI)
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
})
