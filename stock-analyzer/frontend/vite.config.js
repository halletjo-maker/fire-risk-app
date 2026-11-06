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
  // Noms d'hôte autorisés en plus de localhost / IP (ex. ALLOWED_HOSTS=.lhr.life,monpc.local)
  const allowedHosts = env.ALLOWED_HOSTS ? env.ALLOWED_HOSTS.split(',').map((h) => h.trim()).filter(Boolean) : undefined
  return {
    plugins: [react()],
    // Version prête à l'emploi servie par le backend (plus besoin de Node.js sur le PC)
    build: { outDir: '../backend/web', emptyOutDir: true },
    server: { host: true, port: 3000, strictPort: true, proxy, allowedHosts },
    preview: { host: true, port: 3000, strictPort: true, proxy, allowedHosts },
  }
})
