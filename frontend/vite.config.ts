
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ command }) => ({
  // Django/WhiteNoise serves production assets beneath STATIC_URL. Vite dev
  // uses the root path so /@vite/client and application modules resolve.
  // Vercel serves the Vite dist directory from the site root instead.
  base: command === 'build' && !process.env.VERCEL ? '/static/' : '/',
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
}))
