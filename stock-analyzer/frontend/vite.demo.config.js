// Construction de la démo : un seul fichier HTML (JS, CSS et polices intégrés), API simulée.
// Utilisation : npm run build:demo  → dist-demo/index.html
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

export default defineConfig({
  plugins: [react(), viteSingleFile()],
  define: { 'import.meta.env.VITE_DEMO': JSON.stringify('1') },
  build: { outDir: 'dist-demo', assetsInlineLimit: 100_000_000, chunkSizeWarningLimit: 5000 },
})
