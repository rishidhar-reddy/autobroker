import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import process from 'node:process'

// Proxy API calls to the FastAPI backend (default :8000) so the browser makes
// same-origin requests — avoids CORS without touching the backend.
// Override the target with VITE_BACKEND_URL if the backend runs elsewhere.
const BACKEND = process.env.VITE_BACKEND_URL ?? 'http://localhost:8000'
const proxy = (path) => [path, { target: BACKEND, changeOrigin: true }]

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: Object.fromEntries(
      ['/negotiations', '/health', '/config', '/products', '/stats'].map(proxy),
    ),
  },
})
