import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Le frontend appelle "/api/..." : Vite relaie vers le backend.
// Le téléphone n'a donc besoin que du port 3000 de la machine.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backend = env.BACKEND_URL || 'http://localhost:8000'
  const proxy = {
    '/api': {
      target: backend,
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''),
    },
  }
  return {
    plugins: [react()],
    server: { host: true, port: 3000, strictPort: true, proxy },
    preview: { host: true, port: 3000, strictPort: true, proxy },
  }
})
